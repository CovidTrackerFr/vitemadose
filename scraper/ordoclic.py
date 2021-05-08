import json
import logging
import httpx

from datetime import datetime, timedelta
from dateutil.parser import isoparse
from pytz import timezone

from scraper.pattern.center_info import get_vaccine_name
from scraper.pattern.scraper_request import ScraperRequest
from scraper.pattern.scraper_result import DRUG_STORE, INTERVAL_SPLIT_DAYS
from utils.vmd_utils import departementUtils
from scraper.profiler import Profiling


logger = logging.getLogger("scraper")

timeout = httpx.Timeout(15.0, connect=15.0)
DEFAULT_CLIENT = httpx.Client(timeout=timeout)
insee = {}

# Filtre pour le rang d'injection
# Il faut rajouter 2 à la liste si l'on veut les 2èmes injections
ORDOCLIC_VALID_INJECTION = [1]

# get all slugs
def search(client: httpx.Client = DEFAULT_CLIENT):
    base_url = "https://api.ordoclic.fr/v1/public/search"
    # toutes les pharmacies
    # payload = {'page': '1', 'per_page': '10000', 'in.isPublicProfile': 'true'}
    # toutes les pharmacies faisant des vaccins
    # payload = {'page': '1', 'per_page': '10000', 'in.isPublicProfile': 'true', 'in.isCovidVaccineSupported': 'true'}
    # toutes les pharmacies faisant des vaccins avec des calendriers en ligne
    # payload = {'page': '1', 'per_page': '10000', 'in.isPublicProfile': 'true', 'in.isCovidVaccineSupported': 'true', 'in.covidOnlineBookingAvailabilities.covidInjection1': 'true' }
    # toutes les pharmacies faisant du Pfizer ou de l'AstraZeneca
    payload = {
        "page": "1",
        "per_page": "10000",
        "in.isPublicProfile": "true",
        "in.isCovidVaccineSupported": "true",
        "or.covidOnlineBookingAvailabilities.Vaccination Pfizer": "true",
        "or.covidOnlineBookingAvailabilities.Vaccination AstraZeneca": "true",
    }
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


def get_reasons(entityId, client: httpx.Client = DEFAULT_CLIENT):
    base_url = f"https://api.ordoclic.fr/v1/solar/entities/{entityId}/reasons"
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


def get_slots(entityId, medicalStaffId, reasonId, start_date, end_date, client: httpx.Client = DEFAULT_CLIENT):
    base_url = "https://api.ordoclic.fr/v1/solar/slots/availableSlots"
    payload = {
        "entityId": entityId,
        "medicalStaffId": medicalStaffId,
        "reasonId": reasonId,
        "dateEnd": f"{end_date}T00:00:00.000Z",
        "dateStart": f"{start_date}T23:59:59.000Z",
    }
    headers = {"Content-type": "application/json", "Accept": "text/plain"}
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
    if prof in ["pharmacien", "medecin"]:
        base_url = f"https://api.ordoclic.fr/v1/professionals/profile/{slug}"
    else:
        base_url = f"https://api.ordoclic.fr/v1/public/entities/profile/{slug}"
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


def count_appointements(appointments: list, start_date: str, end_date: str) -> int:
    paris_tz = timezone("Europe/Paris")
    start_dt = isoparse(start_date).astimezone(paris_tz)
    end_dt = isoparse(end_date).astimezone(paris_tz)
    count = 0

    for appointment in appointments:
        slot_dt = isoparse(appointment["timeStart"]).astimezone(paris_tz)
        if slot_dt >= start_dt and slot_dt < end_dt:
            count += 1

    logger.debug(f"Slots count from {start_date} to {end_date}: {count}")
    return count


def parse_ordoclic_slots(request: ScraperRequest, availability_data):
    start_date = request.get_start_date()
    first_availability = None
    if not availability_data:
        return None
    availabilities = availability_data.get("slots", None)
    availability_count = 0
    if type(availabilities) is list:
        availability_count = len(availabilities)
    request.update_appointment_count(availability_count)
    appointment_schedules = request.appointment_schedules
    for n in INTERVAL_SPLIT_DAYS:
        n_date = (isoparse(start_date) + timedelta(days=n)).isoformat()
        appointment_schedules[f"{n}_days"] += count_appointements(availabilities, start_date, n_date)
    request.update_appointment_schedules(appointment_schedules)
    logger.debug(f"appointment_schedules: {appointment_schedules}")
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
    profile = get_profile(request)
    slug = profile["profileSlug"]
    entityId = profile["entityId"]
    attributes = profile.get("attributeValues")
    for settings in attributes:
        if settings["label"] == "booking_settings" and settings["value"].get("option", "any") == "any":
            request.set_appointments_only_by_phone(True)
            return None
    appointment_schedules = {}
    for n in INTERVAL_SPLIT_DAYS:
        appointment_schedules[f"{n}_days"] = 0
        request.update_appointment_schedules(appointment_schedules)
    for professional in profile["publicProfessionals"]:
        medicalStaffId = professional["id"]
        name = professional["fullName"]
        zip = professional["zip"]
        reasons = get_reasons(entityId)
        for reason in reasons["reasons"]:
            if not is_reason_valid(reason):
                continue
            request.add_vaccine_type(get_vaccine_name(reason.get("name", "")))
            reasonId = reason["id"]
            date_obj = datetime.strptime(request.get_start_date(), "%Y-%m-%d")
            end_date = (date_obj + timedelta(days=50)).strftime("%Y-%m-%d")
            slots = get_slots(entityId, medicalStaffId, reasonId, request.get_start_date(), end_date, client)
            date = parse_ordoclic_slots(request, slots)
            if date is None:
                continue
            if first_availability is None or date < first_availability:
                first_availability = date
    if first_availability is None:
        return None
    logger.debug(f"appointment_schedules: {request.appointment_schedules}")
    return first_availability.isoformat()


def centre_iterator(client: httpx.Client = DEFAULT_CLIENT):
    items = search(client)
    for item in items["items"]:
        # plusieur types possibles (pharmacie, maison mediacle, pharmacien, medecin, ...), pour l'instant on filtre juste les pharmacies
        if "type" in item:
            t = item.get("type")
            if t == "Pharmacie":
                centre = {}
                slug = item["publicProfile"]["slug"]
                centre["gid"] = item["id"][:8]
                centre["rdv_site_web"] = f"https://app.ordoclic.fr/app/pharmacie/{slug}"
                centre["com_insee"] = departementUtils.cp_to_insee(item["location"]["zip"])
                centre["nom"] = item.get("name")
                centre["phone_number"] = item.get("phone")
                centre["location"] = item.get("location")
                centre["iterator"] = "ordoclic"
                centre["type"] = DRUG_STORE
                yield centre
