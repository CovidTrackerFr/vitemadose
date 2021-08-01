import json
import logging
import httpx

from datetime import datetime, timedelta
from dateutil.parser import isoparse, parse as dateparse
from pytz import timezone
from typing import Dict, Iterator, List, Optional, Tuple, Set
from scraper.pattern.vaccine import get_vaccine_name
from scraper.pattern.scraper_request import ScraperRequest
from scraper.pattern.scraper_result import DRUG_STORE
from utils.vmd_config import get_conf_platform, get_config
from utils.vmd_utils import departementUtils, DummyQueue
from scraper.profiler import Profiling
from scraper.creneaux.creneau import Creneau, Lieu, Plateforme, PasDeCreneau
import requests
from cachecontrol import CacheControl
from cachecontrol.caches.file_cache import FileCache

logger = logging.getLogger("scraper")

ORDOCLIC_CONF = get_conf_platform("ordoclic")
ORDOCLIC_API = ORDOCLIC_CONF.get("api", {})
ORDOCLIC_ENABLED = ORDOCLIC_CONF.get("enabled", False)
NUMBER_OF_SCRAPED_DAYS = get_config().get("scrape_on_n_days", 28)

timeout = httpx.Timeout(ORDOCLIC_CONF.get("timeout", 25), connect=ORDOCLIC_CONF.get("timeout", 25))
session_pre = requests.Session()
DEFAULT_CLIENT =  CacheControl(session_pre, cache=FileCache('./cache'))
insee = {}
paris_tz = timezone("Europe/Paris")

# Filtre pour le rang d'injection
# Il faut rajouter 2 à la liste si l'on veut les 2èmes injections
ORDOCLIC_VALID_INJECTION = ORDOCLIC_CONF.get("filters", {}).get("valid_injections", [])

# get all slugs
def search(client: httpx.Client = DEFAULT_CLIENT):
    base_url = ORDOCLIC_API.get("scraper")

    payload = ORDOCLIC_CONF.get("scraper_payload")
    try:
        r = client.get(base_url, params=payload)
        r.raise_for_status()
    except httpx.TimeoutException as hex:
        logger.warning(f"request timed out for center: {base_url} (search)")
        return None
    except httpx.HTTPStatusError as hex:
        logger.warning(f"{base_url} returned error {hex.response.status_code}")
        return None
    return r.json()


def get_reasons(entityId, client: httpx.Client = DEFAULT_CLIENT, request: ScraperRequest = None):
    base_url = ORDOCLIC_API.get("motives").format(entityId=entityId)
    if request:
        request.increase_request_count("motives")
    try:
        r = client.get(base_url)
        r.raise_for_status()
    except httpx.TimeoutException as hex:
        logger.warning(f"request timed out for center: {base_url}")
        if request:
            request.increase_request_count("time-out")
        return None
    except httpx.HTTPStatusError as hex:
        logger.warning(f"{base_url} returned error {hex.response.status_code}")
        if request:
            request.increase_request_count("error")
        return None
    return r.json()


def is_reason_valid(reason: dict) -> bool:
    if reason.get("canBookOnline", False) is False:
        return False
    if reason.get("vaccineInjectionDose", -1) not in ORDOCLIC_VALID_INJECTION:
        return False
    return True


def count_appointements(appointments: list, start_date: datetime, end_date: datetime) -> int:
    count = 0

    if not appointments:
        return count
    for appointment in appointments:
        if "timeStart" not in appointment:
            continue
        slot_dt = isoparse(appointment["timeStart"]).astimezone(paris_tz)
        if start_date <= slot_dt < end_date:
            count += 1

    logger.debug(f"Slots count from {start_date} to {end_date}: {count}")
    return count


@Profiling.measure("ordoclic_slot")
def fetch_slots(request: ScraperRequest, creneau_q=DummyQueue, client=DEFAULT_CLIENT) -> Optional[str]:
    if not ORDOCLIC_ENABLED:
        return None
    # Fonction principale avec le comportement "de prod".

    ordoclic = OrdoclicSlots(client=client, creneau_q=creneau_q)
    return ordoclic.fetch(request)


class OrdoclicSlots:
    def __init__(self, creneau_q=DummyQueue, client: httpx.Client = None):
        self.creneau_q = creneau_q
        self._client = DEFAULT_CLIENT if client is None else client
        self.lieu = None

    def found_creneau(self, creneau):
        self.creneau_q.put(creneau)

    def parse_ordoclic_slots(self, request: ScraperRequest, availability_data, vaccine):
        first_availability = None
        if not availability_data:
            return None
        availabilities = availability_data.get("slots", None)
        availability_count = 0
        if type(availabilities) is list:
            availability_count = len(availabilities)

        request.update_appointment_count(request.appointment_count + availability_count)
        if "nextAvailableSlotDate" in availability_data:
            nextAvailableSlotDate = availability_data.get("nextAvailableSlotDate", None)
            if nextAvailableSlotDate is not None:
                first_availability = datetime.strptime(nextAvailableSlotDate, "%Y-%m-%dT%H:%M:%S%z")
                first_availability += first_availability.replace(tzinfo=timezone("CET")).utcoffset()
                return first_availability

        if availabilities is None:
            return None
        for slot in availabilities:
            timeStart = slot.get("timeStart", None)
            if not timeStart:
                continue
            date = datetime.strptime(timeStart, "%Y-%m-%dT%H:%M:%S%z")
            if "timeStartUtcOffset" in slot:
                timeStartUtcOffset = slot["timeStartUtcOffset"]
                date += timedelta(minutes=timeStartUtcOffset)
                self.found_creneau(
                    Creneau(
                        horaire=date,
                        reservation_url=request.url,
                        type_vaccin=[vaccine],
                        lieu=self.lieu,
                    )
                )

            if first_availability is None or date < first_availability:
                first_availability = date

            if self.lieu and first_availability is None:
                self.found_creneau(PasDeCreneau(lieu=self.lieu))
        return first_availability

    def get_slots(
        self,
        entityId,
        medicalStaffId,
        reasonId,
        start_date,
        end_date,
        request: ScraperRequest = None,
    ):
        base_url = ORDOCLIC_API.get("slots")
        payload = {
            "entityId": entityId,
            "medicalStaffId": medicalStaffId,
            "reasonId": reasonId,
            "dateEnd": f"{end_date}T00:00:00.000Z",
            "dateStart": f"{start_date}T23:59:59.000Z",
        }
        headers = {"Content-type": "application/json", "Accept": "text/plain"}
        if request:
            request.increase_request_count("slots")
        try:
            r = self._client.post(base_url, data=json.dumps(payload), headers=headers)
            r.raise_for_status()
        except httpx.TimeoutException as hex:
            logger.warning(f"request timed out for center: {base_url}")
            if request:
                request.increase_request_count("time-out")
            return False
        except httpx.HTTPStatusError as hex:
            logger.warning(f"{base_url} returned error {hex.response.status_code}")
            if request:
                request.increase_request_count("error")
            return None
        return r.json()

    def get_profile(self, request: ScraperRequest):
        slug = request.get_url().rsplit("/", 1)[-1]
        prof = request.get_url().rsplit("/", 2)[-2]
        if prof in ["pharmacien", "medecin"]:  # pragma: no cover
            base_url = ORDOCLIC_API.get("profile_professionals").format(slug=slug)
        else:
            base_url = ORDOCLIC_API.get("profile_public_entities").format(slug=slug)
        request.increase_request_count("booking")
        try:
            r = self._client.get(base_url)
            r.raise_for_status()
        except httpx.TimeoutException as hex:
            logger.warning(f"request timed out for center: {base_url}")
            request.increase_request_count("time-out")
            return False
        except httpx.HTTPStatusError as hex:
            logger.warning(f"{base_url} returned error {hex.response.status_code}")
            request.increase_request_count("error")
            return None
        return r.json()

    def fetch(
        self,
        request: ScraperRequest,
    ):
        first_availability = None
        profile = self.get_profile(request=request)
        if not profile:
            return None

        self.lieu = Lieu(
            plateforme=Plateforme.ORDOCLIC,
            url=request.url,
            location=request.center_info.location,
            nom=request.center_info.nom,
            internal_id=f"ordoclic{request.internal_id}",
            departement=request.center_info.departement,
            lieu_type=request.practitioner_type,
            metadata=request.center_info.metadata,
        )

        entityId = profile["entityId"]
        attributes = profile.get("attributeValues")
        for settings in attributes:
            if settings["label"] == "booking_settings" and settings["value"].get("option", "any") == "any":
                request.set_appointments_only_by_phone(True)
                return None

        for professional in profile["publicProfessionals"]:
            medicalStaffId = professional["id"]
            reasons = get_reasons(entityId, request=request)
            for reason in reasons["reasons"]:
                if not is_reason_valid(reason):
                    continue
                vaccine = get_vaccine_name(reason.get("name", ""))
                request.add_vaccine_type(vaccine)
                reasonId = reason["id"]
                date_obj = datetime.strptime(request.get_start_date(), "%Y-%m-%d")
                end_date = (date_obj + timedelta(days=NUMBER_OF_SCRAPED_DAYS)).strftime("%Y-%m-%d")
                slots = self.get_slots(entityId, medicalStaffId, reasonId, request.get_start_date(), end_date, request)
                date = self.parse_ordoclic_slots(request, slots, vaccine)
                if date is None:
                    continue

                if first_availability is None or date < first_availability:
                    first_availability = date
        if first_availability is None:
            if self.lieu:
                self.found_creneau(PasDeCreneau(lieu=self.lieu, phone_only=request.appointment_by_phone_only))
            return None
        return first_availability.isoformat()


def centre_iterator(client: httpx.Client = DEFAULT_CLIENT):
    if not ORDOCLIC_ENABLED:
        logger.warning("Ordoclic scrap is disabled in configuration file.")
        return []
    items = search(client)
    if items is None:
        return []
    for item in items["items"]:
        # plusieur types possibles (pharmacie, maison mediacle, pharmacien, medecin, ...), pour l'instant on filtre juste les pharmacies
        if "type" in item:
            t = item.get("type")
            if t == "Pharmacie":
                centre = {}
                slug = item["publicProfile"]["slug"]
                centre["gid"] = item["id"][:8]
                centre["rdv_site_web"] = ORDOCLIC_CONF.get("build_url").format(slug=slug)
                centre["com_cp"] = item["location"]["zip"]
                centre["com_insee"] = departementUtils.cp_to_insee(item["location"]["zip"])
                centre["nom"] = item.get("name")
                centre["phone_number"] = item.get("phone")
                centre["location"] = item.get("location")
                centre["iterator"] = "ordoclic"
                centre["type"] = DRUG_STORE
                yield centre
