import json
import time
import logging
import os
import re
from datetime import timedelta, datetime
from math import floor
from typing import Dict, Iterator, List, Optional, Tuple, Set
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
import dateutil
import httpx
import pytz
import requests
from scraper.creneaux.creneau import Creneau, Lieu, Plateforme, PasDeCreneau
from scraper.doctolib.doctolib_filters import is_appointment_relevant, parse_practitioner_type, is_category_relevant
from scraper.pattern.vaccine import get_vaccine_name, Vaccine
from scraper.pattern.scraper_request import ScraperRequest
from scraper.error import Blocked403, DoublonDoctolib, RequestError
from utils.vmd_config import get_conf_outputs, get_conf_platform, get_config
from utils.vmd_utils import DummyQueue
from cachecontrol import CacheControl
from cachecontrol.caches.file_cache import FileCache

# PLATFORM MUST BE LOW, PLEASE LET THE "lower()" IN CASE OF BAD INPUT FORMAT.
PLATFORM = "doctolib".lower()

PLATFORM_CONF = get_conf_platform(PLATFORM)
PLATFORM_ENABLED = PLATFORM_CONF.get("enabled", True)

NUMBER_OF_SCRAPED_DAYS = get_config().get("scrape_on_n_days", 28)
PLATFORM_DAYS_PER_PAGE = PLATFORM_CONF.get("days_per_page", 7)
if NUMBER_OF_SCRAPED_DAYS % PLATFORM_DAYS_PER_PAGE == 0:
    PLATFORM_PAGES_NUMBER = NUMBER_OF_SCRAPED_DAYS / PLATFORM_DAYS_PER_PAGE
else:
    PLATFORM_PAGES_NUMBER = (NUMBER_OF_SCRAPED_DAYS // PLATFORM_DAYS_PER_PAGE) + 1

PLATFORM_TIMEOUT = PLATFORM_CONF.get("timeout", 10)
PLATFORM_REQUEST_SLEEP = PLATFORM_CONF.get("request_sleep", 0.1)
timeout = httpx.Timeout(PLATFORM_TIMEOUT, connect=PLATFORM_TIMEOUT)


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


#   @ShortCircuit("doctolib_slot", trigger=20, release=80, time_limit=40.0)
# @Profiling.measure("doctolib_slot")
def fetch_slots(request: ScraperRequest, creneau_q=DummyQueue) -> Optional[str]:
    if not PLATFORM_ENABLED:
        return None
    # Fonction principale avec le comportement "de prod".
    doctolib = DoctolibSlots(client=DEFAULT_CLIENT, creneau_q=creneau_q)
    return doctolib.fetch(request)


class DoctolibSlots:
    # Permet de passer un faux client HTTP,
    # pour éviter de vraiment appeler Doctolib lors des tests.

    def __init__(self, creneau_q=DummyQueue, client: httpx.Client = None, cooldown_interval=PLATFORM_REQUEST_SLEEP):
        self._cooldown_interval = cooldown_interval
        self.creneau_q = creneau_q
        self._client = DEFAULT_CLIENT if client is None else client
        self.lieu = None

    # @Profiling.measure("doctolib_found_creneau")
    def found_creneau(self, creneau):
        self.creneau_q.put(creneau)

    def fetch(self, request: ScraperRequest) -> Optional[str]:
        result = self._fetch(request)
        if result is None and self.lieu:
            self.found_creneau(PasDeCreneau(lieu=self.lieu, phone_only=request.appointment_by_phone_only))

        return result

    def _fetch(self, request: ScraperRequest) -> Optional[str]:

        doublon_responses = 0
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
            centre_api_url = PLATFORM_CONF.get("api").get("booking", "").format(centre=centre)
            request.increase_request_count("booking")
            try:
                response = self._client.get(centre_api_url, headers=DOCTOLIB_HEADERS)
                # response.raise_for_status()
                time.sleep(self._cooldown_interval)
                try:
                    data = response.json()
                    rdata = data.get("data", {})
                except:
                    request.increase_request_count("error")
                    if response.status_code == 403:
                        raise Blocked403(PLATFORM, centre_api_url)
                    if response.status_code == 404:
                        raise RequestError(centre_api_url, response.status_code)
                    return None

            except requests.exceptions.RequestException as e:
                request.increase_request_count("error")
                raise RequestError(centre_api_url)
                return None

        if not self.is_practice_id_valid(request, rdata):
            logger.warning(
                f"Invalid practice ID for this Doctolib center. Practice_id will be corrected: {request.get_url()}"
            )
            practice_id = self.correct_practice_id(request, rdata)
            if not practice_id:
                self.pop_practice_id(request)
                raise DoublonDoctolib(centre)

        if practice_id:
            practice_id, practice_same_adress = link_practice_ids(practice_id, rdata)
        if len(rdata.get("places", [])) > 1 and practice_id is None:
            practice_id = rdata.get("places")[0].get("practice_ids", None)

        if len(rdata.get("places", [])) == 0 and practice_id is None:
            return None

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
        visit_motive_ids_by_vaccine = _find_visit_motive_id(rdata, visit_motive_category_id=visit_motive_category_id)
        if visit_motive_ids_by_vaccine is None:
            return None

        all_agendas = parse_agenda_ids(rdata)
        first_availability = None

        start_date = request.get_start_date()

        self.lieu = Lieu(
            plateforme=Plateforme[PLATFORM.upper()],
            url=request.url,
            location=request.center_info.location,
            nom=request.center_info.nom,
            internal_id=request.internal_id,
            departement=request.center_info.departement,
            lieu_type=request.practitioner_type,
            metadata=request.center_info.metadata,
        )

        timetable_start_date = datetime.fromisoformat(start_date)

        for vaccine, visite_motive_ids in visit_motive_ids_by_vaccine.items():
            agenda_ids, practice_ids, doublon_responses = _find_agenda_and_practice_ids(
                rdata, visite_motive_ids, doublon_responses, practice_id_filter=practice_id
            )

            if not agenda_ids or not practice_ids:
                continue
            agenda_ids = self.sort_agenda_ids(all_agendas, agenda_ids)

            agenda_ids_q = "-".join(agenda_ids)
            practice_ids_q = "-".join(practice_ids)
            motive_ids_q = "-".join(list(map(lambda id: str(id), visite_motive_ids)))
            availability = self.get_timetables(
                request, vaccine, motive_ids_q, agenda_ids_q, practice_ids_q, timetable_start_date
            )
            if availability and (not first_availability or availability < first_availability):
                first_availability = availability

        if doublon_responses == 0:
            raise DoublonDoctolib(request.get_url())

        return first_availability

    def get_timetables(
        self,
        request: ScraperRequest,
        vaccine,
        motive_ids_q,
        agenda_ids_q: str,
        practice_ids_q: str,
        start_date: datetime,
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
        if page > PLATFORM_PAGES_NUMBER:
            return first_availability
        sdate, appt, ended, next_slot = self.get_appointments(
            request,
            start_date.date().strftime("%Y-%m-%d"),
            vaccine,
            motive_ids_q,
            agenda_ids_q,
            practice_ids_q,
            PLATFORM_DAYS_PER_PAGE,
        )
        if ended:
            return first_availability

        print(next_slot)
        if next_slot:
            """
            Optimize query count by jumping directly to the first availability date by using ’next_slot’ key
            """
            next_expected_date = start_date + timedelta(days=PLATFORM_DAYS_PER_PAGE)
            next_fetch_date = datetime.strptime(next_slot, "%Y-%m-%dT%H:%M:%S.%f%z")
            diff = next_fetch_date.astimezone(tz=pytz.timezone("Europe/Paris")) - next_expected_date.astimezone(
                tz=pytz.timezone("Europe/Paris")
            )
            if page > PLATFORM_PAGES_NUMBER:
                return first_availability
            return self.get_timetables(
                request,
                vaccine,
                motive_ids_q,
                agenda_ids_q,
                practice_ids_q,
                next_fetch_date,
                page=1 + max(0, floor(diff.days / PLATFORM_DAYS_PER_PAGE)) + page,
                first_availability=first_availability,
            )
        if not sdate:
            return first_availability
        if not first_availability or sdate < first_availability:
            first_availability = sdate
        request.update_appointment_count(request.appointment_count + appt)
        if page >= PLATFORM_PAGES_NUMBER:
            return first_availability
        return self.get_timetables(
            request,
            vaccine,
            motive_ids_q,
            agenda_ids_q,
            practice_ids_q,
            start_date + timedelta(days=PLATFORM_DAYS_PER_PAGE),
            1 + page,
            first_availability=first_availability,
        )

    def sort_agenda_ids(self, all_agendas, ids) -> List[str]:
        """
        On Doctolib front-side, agenda ids are sorted using the center.json order
        so we need to use all agendas in order to sort.

        Because: 429620-440654-434343-434052-434337-447048-434338-433994-415613-440655-415615
        won't give the same result as: 440654-429620-434343-434052-447048-434338-433994-415613-440655-415615-434337
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

    def correct_practice_id(self, request: ScraperRequest, rdata):
        """
        In some cases, practice id needs to be corrected after a change
        """
        correct_practice_id = None
        places = rdata.get("places", {})
        for place in places:
            if place["full_address"] == request.center_info.metadata["address"]:
                correct_practice_id = place["practice_ids"][0]
        if correct_practice_id:
            u = urlparse(request.get_url())
            query = parse_qs(u.query, keep_blank_values=True)
            query["pid"] = correct_practice_id
            u = u._replace(query=urlencode(query, True))
            request.url = urlunparse(u)
            return [correct_practice_id]

        else:
            return None

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
        vaccine: Vaccine,
        motive_ids_q: str,
        agenda_ids_q: str,
        practice_ids_q: str,
        limit: int,
    ):
        stop = False
        motive_availability = False
        first_availability = None
        appointment_count = 0
        slots_api_url = (
            PLATFORM_CONF.get("api")
            .get("slots", "")
            .format(
                start_date=start_date,
                motive_id=motive_ids_q,
                agenda_ids_q=agenda_ids_q,
                practice_ids_q=practice_ids_q,
                limit=limit,
            )
        )
        request.increase_request_count("slots")
        try:
            response = self._client.get(slots_api_url, headers=DOCTOLIB_HEADERS)
        except httpx.ReadTimeout:
            logger.warning(f"Doctolib returned error ReadTimeout for url {request.get_url()}")
            request.increase_request_count("time-out")
            raise Blocked403(PLATFORM, request.get_url())
        if response.status_code == 403 or response.status_code == 400:
            request.increase_request_count("error")
            raise Blocked403(PLATFORM, request.get_url())

        response.raise_for_status()
        time.sleep(self._cooldown_interval)
        slots = response.json()
        if slots.get("total"):
            appointment_count += int(slots.get("total", 0))

        for availability in slots["availabilities"]:
            slot_list = availability.get("slots", [])
            if len(slot_list) == 0:
                continue
            if isinstance(slot_list[0], str):
                if slot_list[0] < start_date:
                    continue
                if not first_availability or slot_list[0] < first_availability:
                    first_availability = slot_list[0]
                    motive_availability = True
                    self.found_creneau(
                        Creneau(
                            horaire=dateutil.parser.parse(slot_list[0]),
                            reservation_url=request.url,
                            type_vaccin=[vaccine],
                            lieu=self.lieu,
                        )
                    )

            for slot_info in slot_list:
                if isinstance(slot_info, str):
                    continue
                sdate = slot_info.get("start_date", None)
                if not sdate or sdate < start_date:
                    continue
                if not first_availability or sdate < first_availability:
                    first_availability = sdate
                    motive_availability = True
                self.found_creneau(
                    Creneau(
                        horaire=dateutil.parser.parse(sdate),
                        reservation_url=request.url,
                        type_vaccin=[vaccine],
                        lieu=self.lieu,
                    )
                )

        if motive_availability:
            request.add_vaccine_type(vaccine)
        # Sometimes Doctolib does not allow to see slots for next weeks
        # which is a weird move, but still, we have to stop here.

        if not first_availability and not slots.get("next_slot", None):
            stop = True
        return first_availability, appointment_count, stop, slots.get("next_slot")


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
    agendas = rdata.get("agendas")

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
                practice_id.append(int(place.get("practice_ids", [])[0]))
            base_place = place
            break
    if not base_place:
        return place_ids, same_adress

    for place in places:
        if place.get("id") == base_place.get("id"):
            continue
        if place.get("address") == base_place.get("address"):  # Tideous check
            valid_practice_id = 0
            for agenda in agendas:
                if agenda.get("practice_id") == int(re.findall(r"\d+", place.get("id"))[0]):
                    if (
                        int(re.findall(r"\d+", place.get("id"))[0])
                        in list(map(int, list(agenda["visit_motive_ids_by_practice_id"].keys())))
                        and len(agenda["visit_motive_ids_by_practice_id"][re.findall(r"\d+", place.get("id"))[0]]) > 0
                    ):
                        valid_practice_id += 1
            if valid_practice_id == 0:
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


def _find_visit_motive_id(rdata: dict, visit_motive_category_id: list = None) -> Dict[Vaccine, Set[int]]:
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

        # If it's not a first shot motive
        # TODO: filter system
        if (
            not visit_motive.get("first_shot_motive")
            and vaccine_name != Vaccine.JANSSEN
            and "injection unique" not in visit_motive["name"].lower()
        ):
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
        if (
            visit_motive_category_id is None
            or visit_motive.get("visit_motive_category_id") in visit_motive_category_id
            or visit_motive.get("visit_motive_category_id") is None
        ):
            ids = relevant_motives.get(vaccine_name, set())
            ids.add(visit_motive["id"])
            relevant_motives[vaccine_name] = ids
    return relevant_motives


def _find_agenda_and_practice_ids(
    data: dict, visit_motive_ids: Set[int], responses=0, practice_id_filter: list = None
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
        for practice_id in practice_id_filter:
            if practice_id in list(map(int, list(agenda["visit_motive_ids_by_practice_id"].keys()))) and any(
                [
                    vaccination_motive
                    for vaccination_motive in visit_motive_ids
                    if vaccination_motive in agenda["visit_motive_ids_by_practice_id"][str(practice_id)]
                ]
            ):
                responses += 1

        for pratice_id_agenda, visit_motive_list_agenda in agenda["visit_motive_ids_by_practice_id"].items():
            if (
                len(visit_motive_ids.intersection(visit_motive_list_agenda)) > 0
            ):  # Some motives are present in this agenda
                practice_ids.add(str(pratice_id_agenda))
                agenda_ids.add(str(agenda["id"]))
    return sorted(agenda_ids), sorted(practice_ids), responses


def is_allowing_online_appointments(rdata: dict) -> bool:
    """Check if online appointments are allowed for this center."""
    agendas = rdata.get("agendas", None)
    if not agendas:
        return False
    for agenda in agendas:
        if not agenda.get("booking_disabled", False):
            return True
    return False


class CustomStage:
    """Generic class to wrap serialization steps with consistent ``dumps()`` and ``loads()`` methods"""

    def __init__(self, obj, dumps: str = "dumps", loads: str = "loads"):
        self.obj = obj
        self.dumps = getattr(obj, dumps)
        self.loads = getattr(obj, loads)


def center_iterator(client=None) -> Iterator[Dict]:
    if not PLATFORM_ENABLED:
        logger.warning(f"{PLATFORM.capitalize()} scrap is disabled in configuration file.")
        return []

    session = CacheControl(requests.Session(), cache=FileCache("./cache"))

    if client:
        session = client
    try:
        url = f'{get_config().get("base_urls").get("github_public_path")}{get_conf_outputs().get("centers_json_path").format(PLATFORM)}'
        response = session.get(url)
        # Si on ne vient pas des tests unitaires
        if not client:
            if response.from_cache:
                logger.info(f"Liste des centres pour {PLATFORM} vient du cache")
            else:
                logger.info(f"Liste des centres pour {PLATFORM} est une vraie requête")

        data = response.json()
        logger.info(f"Found {len(data)} {PLATFORM.capitalize()} centers (external scraper).")
        for center in data:
            yield center
    except Exception as e:
        logger.warning(f"Unable to scrape {PLATFORM} centers: {e}")
