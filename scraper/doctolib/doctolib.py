import json
import time
import logging
import os
import re
from datetime import timedelta, datetime
from math import floor
from typing import Dict, Iterator, List, Optional, Tuple
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

import httpx
import requests


from scraper.doctolib.conf import DoctolibConf
from scraper.doctolib.doctolib_filters import is_appointment_relevant, parse_practitioner_type, is_category_relevant
from scraper.pattern.center_info import INTERVAL_SPLIT_DAYS, CHRONODOSES
from scraper.pattern.vaccine import get_vaccine_name, Vaccine
from scraper.pattern.scraper_request import ScraperRequest
from scraper.error import BlockedByDoctolibError
from scraper.profiler import Profiling
from utils.vmd_config import get_conf_platform
from utils.vmd_utils import append_date_days


DOCTOLIB_CONF = DoctolibConf(**get_conf_platform("doctolib"))

timeout = httpx.Timeout(DOCTOLIB_CONF.timeout, connect=DOCTOLIB_CONF.timeout)

DOCTOLIB_HEADERS = {
    "User-Agent": os.environ.get("DOCTOLIB_API_KEY", ""),
}

if os.getenv("WITH_TOR", "no") == "yes":
    session = requests.Session()
    session.proxies = {  # type: ignore
        "http": "socks5://127.0.0.1:9050",
        "https": "socks5://127.0.0.1:9050",
    }
    DEFAULT_CLIENT = session  # type: ignore
else:
    DEFAULT_CLIENT = httpx.Client(timeout=timeout)

logger = logging.getLogger("scraper")


@Profiling.measure("doctolib_slot")
def fetch_slots(request: ScraperRequest) -> Optional[str]:
    if not DOCTOLIB_CONF.enabled:
        return None
    # Fonction principale avec le comportement "de prod".
    doctolib = DoctolibSlots(client=DEFAULT_CLIENT)
    return doctolib.fetch(request)


class DoctolibSlots:
    # Permet de passer un faux client HTTP,
    # pour éviter de vraiment appeler Doctolib lors des tests.

    def __init__(self, client: httpx.Client = None, cooldown_interval=DOCTOLIB_CONF.request_sleep):
        self._cooldown_interval = cooldown_interval
        self._client = DEFAULT_CLIENT if client is None else client

    def fetch(self, request: ScraperRequest) -> Optional[str]:

        centre = _parse_centre(request.get_url())

        # Doctolib fetches multiple vaccination centers sometimes
        # so if a practice id is present in query, only related agendas
        # should be selected.
        practice_id = _parse_practice_id(request.get_url())

        practice_same_adress = False

        rdata = None
        # We already have rdata
        if request.input_data:
            rdata = request.input_data
        else:
            centre_api_url = DOCTOLIB_CONF.api.get("booking", "").format(centre=centre)
            request.increase_request_count("booking")
            response = self._client.get(centre_api_url, headers=DOCTOLIB_HEADERS)
            if response.status_code == 403:
                raise BlockedByDoctolibError(centre_api_url)

            response.raise_for_status()
            time.sleep(self._cooldown_interval)
            data = response.json()
            rdata = data.get("data", {})

        if not self.is_practice_id_valid(request, rdata):
            logger.warning(f"Invalid practice ID for this Doctolib center: {request.get_url()}")
            practice_id = None
            self.pop_practice_id(request)
        if practice_id:
            practice_id, practice_same_adress = link_practice_ids(practice_id, rdata)
        if len(rdata.get("places", [])) > 1 and practice_id is None:
            practice_id = rdata.get("places")[0].get("practice_ids", None)

        request.update_practitioner_type(parse_practitioner_type(centre, rdata))
        set_doctolib_center_internal_id(request, rdata, practice_id, practice_same_adress)
        # Check if  appointments are allowed
        if not is_allowing_online_appointments(rdata):
            request.set_appointments_only_by_phone(True)
            return None

        # visit_motive_categories
        # example: https://partners.doctolib.fr/hopital-public/tarbes/centre-de-vaccination-tarbes-ayguerote?speciality_id=5494&enable_cookies_consent=1
        visit_motive_category_id = _find_visit_motive_category_id(rdata)
        # visit_motive_id
        visit_motive_ids = _find_visit_motive_id(rdata, visit_motive_category_id=visit_motive_category_id)
        if visit_motive_ids is None:
            return None

        all_agendas = parse_agenda_ids(rdata)
        first_availability = None

        appointment_schedules = request.get_appointment_schedules()

        start_date = request.get_start_date()

        for interval in INTERVAL_SPLIT_DAYS:
            chronodose = False
            if interval == CHRONODOSES["Interval"]:
                chronodose = True

            appointment_schedules = build_appointment_schedules(
                request,
                interval,
                append_date_days(start_date, 0),
                append_date_days(start_date, days=interval, seconds=-1),
                0,
                appointment_schedules,
                chronodose,
            )
        request.update_appointment_schedules(appointment_schedules)

        timetable_start_date = datetime.now()  # shouldn't be datetime.now()!!
        for visit_motive_id in visit_motive_ids:
            agenda_ids, practice_ids = _find_agenda_and_practice_ids(
                rdata, visit_motive_id, practice_id_filter=practice_id
            )
            if not agenda_ids or not practice_ids:
                continue
            agenda_ids = self.sort_agenda_ids(all_agendas, agenda_ids)

            agenda_ids_q = "-".join(agenda_ids)
            practice_ids_q = "-".join(practice_ids)
            availability = self.get_timetables(
                request,
                visit_motive_ids,
                visit_motive_id,
                agenda_ids_q,
                practice_ids_q,
                timetable_start_date,
                appointment_schedules,
            )
            if availability and (not first_availability or availability < first_availability):
                first_availability = availability
        return first_availability

    def get_timetables(
        self,
        request: ScraperRequest,
        visit_motive_ids,
        visit_motive_id,
        agenda_ids_q: str,
        practice_ids_q: str,
        start_date: datetime,
        appointment_schedules: list,
        page: int = 1,
        first_availability: Optional[str] = None,
    ) -> Optional[str]:
        """
        Get timetables recursively with `doctolib.pagination.days` as the number of days to query.
        Recursively limited by `doctolib.pagination.pages` and appends new availabilities to a ’timetable’,
        freshly initialized at the beginning.
        Uses next_slot as a reference for next availability and in order to avoid useless requests when
        we already know if a timetable is empty.
        """
        if page > DOCTOLIB_CONF.pagination["pages"]:
            return first_availability
        sdate, appt, schedules, ended, next_slot = self.get_appointments(
            request,
            start_date.strftime("%Y-%m-%d"),
            visit_motive_ids,
            visit_motive_id,
            agenda_ids_q,
            practice_ids_q,
            DOCTOLIB_CONF.pagination["days"],
            request.get_start_date(),
            appointment_schedules,
        )
        if ended:
            return first_availability
        if next_slot:
            """
            Optimize query count by jumping directly to the first availability date by using ’next_slot’ key
            """
            next_expected_date = start_date + timedelta(days=DOCTOLIB_CONF.pagination["days"])
            next_fetch_date = datetime.strptime(next_slot, "%Y-%m-%d")
            diff = next_fetch_date.replace(tzinfo=None) - next_expected_date.replace(tzinfo=None)

            if page > DOCTOLIB_CONF.pagination["pages"]:
                return first_availability
            return self.get_timetables(
                request,
                visit_motive_ids,
                visit_motive_id,
                agenda_ids_q,
                practice_ids_q,
                next_fetch_date,
                appointment_schedules,
                page=1 + max(0, floor(diff.days / DOCTOLIB_CONF.pagination["days"])) + page,
                first_availability=first_availability,
            )
        if not sdate:
            return first_availability
        if not first_availability or sdate < first_availability:
            first_availability = sdate
        request.update_appointment_count(request.appointment_count + appt)
        if schedules:
            request.update_appointment_schedules(schedules)
        if page >= DOCTOLIB_CONF.pagination["pages"]:
            return first_availability
        return self.get_timetables(
            request,
            visit_motive_ids,
            visit_motive_id,
            agenda_ids_q,
            practice_ids_q,
            start_date + timedelta(days=DOCTOLIB_CONF.pagination["days"]),
            appointment_schedules,
            1 + page,
            first_availability=first_availability,
        )

    def sort_agenda_ids(self, all_agendas, ids) -> List[str]:
        """
        On Doctolib front-side, agenda ids are sorted using the center.json order
        so we need to use all agendas in order to sort.

        Because: 429620-440654-434343-434052-434337-447048-434338-433994-415613-440655-415615
        don't give the same result as: 440654-429620-434343-434052-447048-434338-433994-415613-440655-415615-434337
        -> seems to be a doctolib issue
        """
        new_agenda_list = []
        for agenda in all_agendas:
            if str(agenda) in ids:
                new_agenda_list.append(str(agenda))
        return new_agenda_list

    def pop_practice_id(self, request: ScraperRequest):
        """
        In some cases, practice id needs to be deleted
        """
        u = urlparse(request.get_url())
        query = parse_qs(u.query, keep_blank_values=True)
        query.pop("pid", None)
        u = u._replace(query=urlencode(query, True))
        request.url = urlunparse(u)

    def is_practice_id_valid(self, request: ScraperRequest, rdata: dict) -> bool:
        """
        Some practice IDs are wrong and prevent people from booking an appointment.
        So if the practice id is invalid, this center does not seems to exist anymore.
        """
        pid = _parse_practice_id(request.get_url())

        # Not practice ID found
        if not pid:
            return True
        pid = int(pid[0])
        places = rdata.get("places", {})
        for place in places:
            practice_id = int(re.findall(r"\d+", place.get("id", ""))[0])
            if pid == practice_id:
                return True
        return False

    def get_appointments(
        self,
        request: ScraperRequest,
        start_date: str,
        visit_motive_ids,
        motive_id: str,
        agenda_ids_q: str,
        practice_ids_q: str,
        limit: int,
        start_date_original: str,
        appointment_schedules: list,
    ):
        stop = False
        motive_availability = False
        first_availability = None
        appointment_count = 0
        slots_api_url = DOCTOLIB_CONF.api.get("slots", "").format(
            start_date=start_date,
            motive_id=motive_id,
            agenda_ids_q=agenda_ids_q,
            practice_ids_q=practice_ids_q,
            limit=limit,
        )
        request.increase_request_count("slots")
        try:
            response = self._client.get(slots_api_url, headers=DOCTOLIB_HEADERS)
        except httpx.ReadTimeout:
            logger.warning(f"Doctolib returned error ReadTimeout for url {request.get_url()}")
            raise BlockedByDoctolibError(request.get_url())
        if response.status_code == 403 or response.status_code == 400:
            raise BlockedByDoctolibError(request.get_url())

        response.raise_for_status()
        time.sleep(self._cooldown_interval)
        slots = response.json()
        if slots.get("total"):
            appointment_count += int(slots.get("total", 0))

        for availability in slots["availabilities"]:
            slot_list = availability.get("slots", None)
            if not slot_list or len(slot_list) == 0:
                continue
            if isinstance(slot_list[0], str):
                if not first_availability or slot_list[0] < first_availability:
                    first_availability = slot_list[0]
                    motive_availability = True

            for slot_info in slot_list:
                if isinstance(slot_info, str):
                    continue
                sdate = slot_info.get("start_date", None)
                if not sdate:
                    continue
                if not first_availability or sdate < first_availability:
                    first_availability = sdate
                    motive_availability = True

            if visit_motive_ids[motive_id]:
                visite_motive_vaccine = visit_motive_ids[motive_id]
            else:
                visite_motive_vaccine = None

            for interval in INTERVAL_SPLIT_DAYS:
                chronodose = False
                if visite_motive_vaccine in CHRONODOSES["Vaccine"] and interval == CHRONODOSES["Interval"]:
                    chronodose = True
                appointment_schedules = build_appointment_schedules(
                    request,
                    interval,
                    append_date_days(start_date_original, 0),
                    append_date_days(start_date_original, days=interval, seconds=-1),
                    0,
                    appointment_schedules,
                    chronodose,
                )
                if append_date_days(start_date_original, 0) <= append_date_days(start_date_original, interval):
                    if availability.get("date"):
                        if append_date_days(availability.get("date"), 0) < append_date_days(
                            start_date_original, interval
                        ):
                            appointment_schedules = build_appointment_schedules(
                                request,
                                interval,
                                append_date_days(start_date_original, 0),
                                append_date_days(start_date_original, days=interval, seconds=-1),
                                len(availability.get("slots", [])),
                                appointment_schedules,
                                chronodose,
                            )

        if motive_availability:
            request.add_vaccine_type(visit_motive_ids[motive_id])
        # Sometimes Doctolib does not allow to see slots for next weeks
        # which is a weird move, but still, we have to stop here.

        if not first_availability and not slots.get("next_slot", None):
            stop = True
        return first_availability, appointment_count, appointment_schedules, stop, slots.get("next_slot")


def set_doctolib_center_internal_id(
    request: ScraperRequest, data: dict, practice_ids: Optional[List[int]], practice_same_adress: bool
):
    profile = data.get("profile")

    if not profile:
        return
    profile_id = profile.get("id", None)
    if not profile_id:
        return
    profile_id = int(profile_id)

    if not practice_ids or len(practice_ids) == 0:
        request.update_internal_id(f"doctolib{profile_id}")

    if practice_ids and len(practice_ids) == 1:
        request.update_internal_id(f"doctolib{profile_id}pid{practice_ids[0]}")

    if practice_ids and len(practice_ids) > 1:
        if practice_same_adress == True:
            request.update_internal_id(f"doctolib{profile_id}pid{practice_ids[0]}")
        else:
            request.update_internal_id(f"doctolib{profile_id}")


def _parse_centre(rdv_site_web: str) -> Optional[str]:
    """
    Etant donné l'URL de la page web correspondant au centre de vaccination,
    renvoie le nom du centre de vaccination, en lowercase.
    """
    match = re.search(r"\/([^`\/]+)\?", rdv_site_web)
    if match:
        # nouvelle URL https://partners.doctolib.fr/...
        return match.group(1)

    # ancienne URL https://www.doctolib.fr/....
    # centre doit être en minuscule
    centre = rdv_site_web.split("/")[-1].lower()
    if centre == "":
        return None
    return centre


def link_practice_ids(practice_id: list, rdata: dict) -> Tuple[list, bool]:
    same_adress = False
    if not practice_id:
        return practice_id, same_adress
    places = rdata.get("places")
    if not places:
        return practice_id, same_adress
    base_place = None
    place_ids = []
    for place in places:
        place_id = place.get("id", None)
        if not place_id:
            continue
        place_ids.append(int(re.findall(r"\d+", place_id)[0]))
        if int(re.findall(r"\d+", place_id)[0]) == int(practice_id[0]):
            # Indispensable pour eviter une erreur si le pid est en establishment-xxx
            # En effet, dans ce cas le pid change dans practice_ids et c'est lui qui est correct
            if practice_id[0] not in place.get("practice_ids", []):
                practice_id.clear()
                practice_id.append(int(place.get("practice_ids", [])[0]))
            base_place = place
            break
    if not base_place:
        return place_ids, same_adress

    for place in places:
        if place.get("id") == base_place.get("id"):
            continue
        if place.get("address") == base_place.get("address"):  # Tideous check
            practice_id.append(int(re.findall(r"\d+", place.get("id"))[0]))
            same_adress = True
    return practice_id, same_adress


def parse_agenda_ids(rdata: dict) -> List[int]:
    return [agenda_id for agenda in rdata.get("agendas", []) if (agenda_id := agenda.get("id"))]


def _parse_practice_id(rdv_site_web: str) -> Optional[List[int]]:
    # Doctolib fetches multiple vaccination centers sometimes
    # so if a practice id is present in query, only related agendas
    # will be selected.
    params = httpx.QueryParams(httpx.URL(rdv_site_web).query)

    if "pid" not in params:
        return None

    # QueryParams({'pid': 'practice-164984'}) -> 'practice-164984'
    # /!\ Some URL query strings look like this:
    # 1) ...?pid=practice-162589&?speciality_id=5494&enable_cookies_consent=1
    # 2) ...?pid=practice-162589?speciality_id=5494&enable_cookies_consent=1
    # Notice the weird &?speciality_id or ?speciality_id.
    # Case 1) is handled correctly by `httpx.QueryParams`: in that
    # case, 'pid' contains 'practice-164984'.
    # Case 2), 'pid' contains 'pid=practice-162589?speciality_id=5494'
    # which must be handled manually.
    pid = params.get("pid")
    if pid is None:
        return None

    try:
        # -> '164984'
        pid = pid.split("-")[-1]
        # May be '164984?specialty=13' due to a weird format, drop everything after '?'
        pid, _, _ = pid.partition("?")
        # -> 164984
        return [int(pid)]
    except (ValueError, TypeError, IndexError):
        logger.error(f"failed to parse practice ID: {pid=}")
        return None


def build_appointment_schedules(
    request,
    interval: int,
    start_date: str,
    end_date: str,
    count: int,
    appointment_schedules: Optional[List[dict]],
    chronodose=False,
) -> List[dict]:
    if appointment_schedules is None:
        appointment_schedules = []
    if isinstance(appointment_schedules, list) and len(appointment_schedules) > 0:
        for appointment in appointment_schedules:
            if appointment["name"] == f"{interval}_days":
                appointment["total"] += count

    if not any(appointment["name"] == f"{interval}_days" for appointment in appointment_schedules):
        appointment_schedules.append(
            {
                "name": f"{interval}_days",
                "from": start_date,
                "to": end_date,
                "total": count,
            }
        )

    if chronodose:
        if isinstance(appointment_schedules, list) and len(appointment_schedules) > 0:
            for appointment in appointment_schedules:
                if appointment["name"] == "chronodose":
                    appointment["total"] += count

        if not any(appointment["name"] == "chronodose" for appointment in appointment_schedules):
            appointment_schedules.append(
                {
                    "name": "chronodose",
                    "from": start_date,
                    "to": end_date,
                    "total": count,
                }
            )

    return appointment_schedules


def _find_visit_motive_category_id(rdata: dict) -> List[int]:
    """
    Etant donnée une réponse à /booking/<centre>.json, renvoie le cas échéant
    l'ID de la catégorie de motif correspondant à 'Non professionnels de santé'
    (qui correspond à la population civile).
    """
    categories = []

    if not rdata.get("visit_motive_categories"):
        return None
    for category in rdata.get("visit_motive_categories", []):
        if is_category_relevant(category["name"]):
            categories.append(category["id"])
    return categories


def _find_visit_motive_id(rdata: dict, visit_motive_category_id: list = None) -> Dict[int, str]:
    """
    Etant donnée une réponse à /booking/<centre>.json, renvoie le cas échéant
    l'ID du 1er motif de visite disponible correspondant à une 1ère dose pour
    la catégorie de motif attendue.
    """
    relevant_motives = {}
    for visit_motive in rdata.get("visit_motives", []):
        vaccine_name = repr(get_vaccine_name(visit_motive["name"]))
        # On ne gère que les 1ère doses (le RDV pour la 2e dose est en général donné
        # après la 1ère dose, donc les gens n'ont pas besoin d'aide pour l'obtenir).
        if not is_appointment_relevant(visit_motive["name"]):
            continue

        vaccine_name = get_vaccine_name(visit_motive["name"])

        # If this motive isn't related to vaccination
        if not visit_motive.get("first_shot_motive") and vaccine_name != Vaccine.JANSSEN:
            continue
        # If it's not a first shot motive
        # TODO: filter system
        if not visit_motive.get("first_shot_motive") and vaccine_name != Vaccine.JANSSEN:
            continue
        # Si le lieu de vaccination n'accepte pas les nouveaux patients
        # on ne considère pas comme valable.
        if "allow_new_patients" in visit_motive and not visit_motive["allow_new_patients"]:
            continue
        # NOTE: 'visit_motive_category_id' agit comme un filtre. Il y a 2 cas :
        # * visit_motive_category_id=None : pas de filtre, et on veut les motifs qui ne
        # sont pas non plus rattachés à une catégorie
        # * visit_motive_category_id=<id> : filtre => on veut les motifs qui
        # correspondent à la catégorie en question.
        if visit_motive_category_id is None or visit_motive.get("visit_motive_category_id") in visit_motive_category_id:
            relevant_motives[visit_motive["id"]] = vaccine_name
    return relevant_motives


def _find_agenda_and_practice_ids(
    data: dict, visit_motive_id: str, practice_id_filter: list = None
) -> Tuple[list, list]:
    """
    Etant donné une réponse à /booking/<centre>.json, renvoie tous les
    "agendas" et "pratiques" (jargon Doctolib) qui correspondent au motif de visite.
    On a besoin de ces valeurs pour récupérer les disponibilités.
    """
    agenda_ids = set()
    practice_ids = set()
    for agenda in data.get("agendas", []):
        if (
            "practice_id" in agenda
            and practice_id_filter is not None
            and agenda["practice_id"] not in practice_id_filter
        ):
            continue
        if agenda["booking_disabled"]:
            continue
        agenda_id = str(agenda["id"])
        for pratice_id_agenda, visit_motive_list_agenda in agenda["visit_motive_ids_by_practice_id"].items():
            if visit_motive_id in visit_motive_list_agenda:
                practice_ids.add(str(pratice_id_agenda))
                agenda_ids.add(agenda_id)
    return sorted(agenda_ids), sorted(practice_ids)


def is_allowing_online_appointments(rdata: dict) -> bool:
    """Check if online appointments are allowed for this center."""
    agendas = rdata.get("agendas", None)
    if not agendas:
        return False
    for agenda in agendas:
        if not agenda.get("booking_disabled", False):
            return True
    return False


def center_iterator() -> Iterator[Dict]:
    if not DOCTOLIB_CONF.enabled:
        return
    try:
        center_path = "data/output/doctolib-centers.json"
        url = f"https://raw.githubusercontent.com/CovidTrackerFr/vitemadose/data-auto/{center_path}"
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        file = open(center_path, "w")
        file.write(json.dumps(data, indent=2))
        file.close()
        logger.info(f"Found {len(data)} Doctolib centers (external scraper).")
        for center in data:
            yield center
    except Exception as e:
        logger.warning(f"Unable to scrape doctolib centers: {e}")
