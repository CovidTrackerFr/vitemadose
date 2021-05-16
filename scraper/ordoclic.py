import json
import logging
import httpx

from datetime import datetime, timedelta
from dateutil.parser import isoparse
from pytz import timezone

from scraper.pattern.center_info import INTERVAL_SPLIT_DAYS, CHRONODOSES
from scraper.pattern.vaccine import get_vaccine_name
from scraper.pattern.scraper_request import ScraperRequest
from scraper.pattern.scraper_result import DRUG_STORE
from utils.vmd_config import get_conf_platform
from utils.vmd_utils import departementUtils
from scraper.profiler import Profiling


logger = logging.getLogger("scraper")

ORDOCLIC_CONF = get_conf_platform("ordoclic")
ORDOCLIC_API = ORDOCLIC_CONF.get("api", {})
ORDOCLIC_ENABLED = ORDOCLIC_CONF.get("enabled", False)

timeout = httpx.Timeout(ORDOCLIC_CONF.get("timeout", 25), connect=ORDOCLIC_CONF.get("timeout", 25))
DEFAULT_CLIENT = httpx.Client(timeout=timeout)
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
        return None
    except httpx.HTTPStatusError as hex:
        logger.warning(f"{base_url} returned error {hex.response.status_code}")
        return None
    return r.json()


def get_slots(
    entityId,
    medicalStaffId,
    reasonId,
    start_date,
    end_date,
    client: httpx.Client = DEFAULT_CLIENT,
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
        r = client.post(base_url, data=json.dumps(payload), headers=headers)
        r.raise_for_status()
    except httpx.TimeoutException as hex:
        logger.warning(f"request timed out for center: {base_url}")
        return False
    except httpx.HTTPStatusError as hex:
        logger.warning(f"{base_url} returned error {hex.response.status_code}")
        return None
    return r.json()


def get_profile(request: ScraperRequest, client: httpx.Client = DEFAULT_CLIENT):
    slug = request.get_url().rsplit("/", 1)[-1]
    prof = request.get_url().rsplit("/", 2)[-2]
    if prof in ["pharmacien", "medecin"]:  # pragma: no cover
        base_url = ORDOCLIC_API.get("profile_professionals").format(slug=slug)
    else:
        base_url = ORDOCLIC_API.get("profile_public_entities").format(slug=slug)
    request.increase_request_count("booking")
    try:
        r = client.get(base_url)
        r.raise_for_status()
    except httpx.TimeoutException as hex:
        logger.warning(f"request timed out for center: {base_url}")
        return False
    except httpx.HTTPStatusError as hex:
        logger.warning(f"{base_url} returned error {hex.response.status_code}")
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
        if not "timeStart" in appointment:
            continue
        slot_dt = isoparse(appointment["timeStart"]).astimezone(paris_tz)
        if slot_dt >= start_date and slot_dt < end_date:
            count += 1

    logger.debug(f"Slots count from {start_date} to {end_date}: {count}")
    return count


def parse_ordoclic_slots(request: ScraperRequest, availability_data):
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
        if first_availability is None or date < first_availability:
            first_availability = date
    return first_availability


@Profiling.measure("ordoclic_slot")
def fetch_slots(request: ScraperRequest, client: httpx.Client = DEFAULT_CLIENT):
    first_availability = None
    if not ORDOCLIC_ENABLED:
        return first_availability
    profile = get_profile(request, client)
    if not profile:
        return None
    entityId = profile["entityId"]
    attributes = profile.get("attributeValues")
    for settings in attributes:
        if settings["label"] == "booking_settings" and settings["value"].get("option", "any") == "any":
            request.set_appointments_only_by_phone(True)
            return None
    # create appointment_schedules array with names and dates
    appointment_schedules = []
    start_date = paris_tz.localize(isoparse(request.get_start_date()) + timedelta(days=0))
    end_date = start_date + timedelta(days=CHRONODOSES["Interval"], seconds=-1)
    appointment_schedules.append(
        {"name": "chronodose", "from": start_date.isoformat(), "to": end_date.isoformat(), "total": 0}
    )
    for n in INTERVAL_SPLIT_DAYS:
        end_date = start_date + timedelta(days=n, seconds=-1)
        appointment_schedules.append(
            {"name": f"{n}_days", "from": start_date.isoformat(), "to": end_date.isoformat(), "total": 0}
        )
    for professional in profile["publicProfessionals"]:
        medicalStaffId = professional["id"]
        reasons = get_reasons(entityId, request=request)
        for reason in reasons["reasons"]:
            if not is_reason_valid(reason):
                continue
            request.add_vaccine_type(get_vaccine_name(reason.get("name", "")))
            reasonId = reason["id"]
            date_obj = datetime.strptime(request.get_start_date(), "%Y-%m-%d")
            end_date = (date_obj + timedelta(days=50)).strftime("%Y-%m-%d")
            slots = get_slots(entityId, medicalStaffId, reasonId, request.get_start_date(), end_date, client, request)
            date = parse_ordoclic_slots(request, slots)
            if date is None:
                continue
            # add counts to appointment_schedules
            availabilities = slots.get("slots", None)
            for i in range(0, len(appointment_schedules)):
                start_date = isoparse(appointment_schedules[i]["from"])
                end_date = isoparse(appointment_schedules[i]["to"])
                # do not count chronodose if wrong vaccine
                if (
                    appointment_schedules[i]["name"] == "chronodose"
                    and get_vaccine_name(reason.get("name", "")) not in CHRONODOSES["Vaccine"]
                ):
                    continue
                appointment_schedules[i]["total"] += count_appointements(availabilities, start_date, end_date)
            request.update_appointment_schedules(appointment_schedules)
            logger.debug(f"appointment_schedules: {appointment_schedules}")
            if first_availability is None or date < first_availability:
                first_availability = date
    request.update_appointment_schedules(appointment_schedules)
    if first_availability is None:
        return None
    logger.debug(f"appointment_schedules: {request.appointment_schedules}")
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
