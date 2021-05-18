import os
import logging
from scraper.profiler import Profiling
from scraper.pattern.scraper_result import DRUG_STORE, GENERAL_PRACTITIONER
import httpx
import json

from datetime import datetime, timedelta
from dateutil.parser import isoparse
from pytz import timezone
from typing import Iterator, Optional, Tuple

from scraper.pattern.scraper_request import ScraperRequest
from scraper.pattern.center_info import (
    CenterInfo, CenterLocation, INTERVAL_SPLIT_DAYS, CHRONODOSES
)
from scraper.pattern.vaccine import get_vaccine_name
from utils.vmd_config import get_conf_platform
from utils.vmd_utils import departementUtils

AVECMONDOC_CONF = get_conf_platform("avecmondoc")
AVECMONDOC_API = AVECMONDOC_CONF.get("api", {})
AVECMONDOC_SCRAPER = AVECMONDOC_CONF.get("center_scraper", {})
AVECMONDOC_FILTERS = AVECMONDOC_CONF.get("filters", {})
AVECMONDOC_VALID_REASONS = AVECMONDOC_FILTERS.get("valid_reasons", [])
AVECMONDOC_HEADERS = {
    "User-Agent": os.environ.get("AVECMONDOC_API_KEY", ""),
}
timeout = httpx.Timeout(AVECMONDOC_CONF.get("timeout", 25), connect=AVECMONDOC_CONF.get("timeout", 25))
DEFAULT_CLIENT = httpx.Client(headers=AVECMONDOC_HEADERS, timeout=timeout)
logger = logging.getLogger("scraper")
paris_tz = timezone("Europe/Paris")

def search(client: httpx.Client = DEFAULT_CLIENT) -> Optional[list]:
    url = AVECMONDOC_API.get("search", "")
    payload = AVECMONDOC_API.get("search_filter", "")
    try:
        r = client.get(url, params=payload)
        r.raise_for_status()
    except httpx.TimeoutException as hex:
        logger.warning(f"request timed out for center: {url} (search)")
        return None
    except httpx.HTTPStatusError as hex:
        logger.warning(f"{url} returned error {hex.response.status_code}")
        logger.warning(r.content)
        return None
    return r.json()


def get_doctor_slug(slug: str, client: httpx.Client = DEFAULT_CLIENT,
    request: ScraperRequest = None) -> Optional[dict]:
    url = AVECMONDOC_API.get("get_doctor_slug", "").format(slug=slug)
    try:
        r = client.get(url)
        r.raise_for_status()
    except httpx.TimeoutException as hex:
        logger.warning(f"request timed out for center: {url} (get_slug)")
        return None
    except httpx.HTTPStatusError as hex:
        logger.warning(f"{url} returned error {hex.response.status_code}")
        logger.warning(r.content)
        return None
    if request:
        request.increase_request_count("cabinets")
    return r.json()


def get_organization_slug(slug: str, client: httpx.Client = DEFAULT_CLIENT,
    request: ScraperRequest = None) -> Optional[dict]:
    url = str(AVECMONDOC_API.get("get_organization_slug", "")).format(slug=slug)
    try:
        r = client.get(url)
        r.raise_for_status()
    except httpx.TimeoutException as hex:
        logger.warning(f"request timed out for center: {url} (get_slug)")
        return None
    except httpx.HTTPStatusError as hex:
        logger.warning(f"{url} returned error {hex.response.status_code}")
        logger.warning(r.content)
        return None
    if request:
        request.increase_request_count("cabinets")
    return r.json()


def get_by_doctor(doctor_id: int, client: httpx.Client = DEFAULT_CLIENT,
    request: ScraperRequest = None) -> Optional[list]:
    url = AVECMONDOC_API.get("get_by_doctor", "").format(id=doctor_id)
    try:
        r = client.get(url)
        r.raise_for_status()
    except httpx.TimeoutException as hex:
        logger.warning(f"request timed out for {url} (get_by_doctor)")
        return None
    except httpx.HTTPStatusError as hex:
        logger.warning(f"{url} returned error {hex.response.status_code}")
        logger.warning(r.content)
        return None
    if request:
        request.increase_request_count("resource")
    return r.json()


def get_by_organization(organization_id: int, client: httpx.Client = DEFAULT_CLIENT,
    request: ScraperRequest = None) -> Optional[list]:
    url = AVECMONDOC_API.get("get_by_organization", "").format(id=organization_id)
    try:
        r = client.get(url)
        r.raise_for_status()
    except httpx.TimeoutException as hex:
        logger.warning(f"request timed out for {url} (get_by_doctor)")
        return None
    except httpx.HTTPStatusError as hex:
        logger.warning(f"{url} returned error {hex.response.status_code}")
        logger.warning(r.content)
        return None
    if request:
        request.increase_request_count("resource")
    return r.json()


def get_reasons(organization_id: int, doctor_id:int, client: httpx.Client = DEFAULT_CLIENT,
    request: ScraperRequest = None) -> Optional[list]:
    url = AVECMONDOC_API.get("get_reasons", "").format(id=id)
    payload = {
        "params": json.dumps({
            "organizationId": organization_id,
            "doctorId": doctor_id
        })
    }
    try:
        r = client.get(url, params=payload)
        r.raise_for_status()
    except httpx.TimeoutException as hex:
        logger.warning(f"request timed out for center: {url} (get_reasons)")
        return None
    except httpx.HTTPStatusError as hex:
        logger.warning(f"{url} returned error {hex.response.status_code}")
        logger.warning(r.content)
        return None
    if request:
        request.increase_request_count("motives")
    return r.json()


def organization_to_center(organization) -> Optional[CenterInfo]:
    if organization is None:
        return None
    url = AVECMONDOC_CONF.get("patient_url", "").format(slug=organization.get("slug"))
    id = organization["id"]
    zip = organization["zipCode"]
    dept = departementUtils.to_departement_number(departementUtils.cp_to_insee(zip))
    reasons = organization["consultationReasons"]
    if reasons is None:
        logger.warning(f"no reasons found in organization")
        return None
    if get_valid_reasons(reasons) == []:
        return None
    center = CenterInfo(dept, organization["name"], url)
    location = CenterLocation(0, 0, organization["city"], organization["zipCode"])
    if organization.get("coordinates") is not None:
        location.longitude = organization["coordinates"].get("lng", 0.0)
        location.latitude = organization["coordinates"].get("lat", 0.0)
    center.metadata = {
        "address": organization["address"],
        "phone_number": organization["phone"],
    }
    center.location = location
    center.internal_id = f"amd{id}"
    if "schedules" not in organization:
        return center
    business_hours = {}
    for day, day_name in AVECMONDOC_SCRAPER.get("business_days", {}).items():
        value = ""
        if organization["schedules"][day]["enabled"]:
            value = " ".join(f'{sc["start"]}-{sc["end"]}' for sc in organization["schedules"][day]["schedules"])
        business_hours[day_name] = value
    center.metadata["business_hours"] = business_hours
    return center


def get_valid_reasons(reasons: list) -> list:
    return [
        reason
        for reason in reasons
        if any(valid_reason.lower() in reason["reason"].lower() for valid_reason in AVECMONDOC_VALID_REASONS)
    ]


def get_availabilities_week(reason_id: int, organization_id: int,
    start_date: datetime, client: httpx.Client = DEFAULT_CLIENT) -> Optional[list]:
    url = AVECMONDOC_API.get("availabilities_per_day", "")
    week_size = AVECMONDOC_CONF.get("week_size", 5)
    payload = {
        "consultationReasonId": reason_id,
        "disabledPeriods": [],
        "fullDisplay": True,
        "organizationId": organization_id,
        "periodEnd": (start_date + timedelta(days=week_size)).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "periodStart": start_date.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "type":"inOffice"
    }
    headers = {"Content-type": "application/json", "Accept": "application/json"}
    try:
        r = client.post(url, data=json.dumps(payload), headers=headers)
        r.raise_for_status()
    except httpx.TimeoutException as hex:
        logger.warning(f"request timed out for center: {url}")
        return None
    except httpx.HTTPStatusError as hex:
        logger.warning(f"{url} returned error {hex.response.status_code}")
        logger.warning(payload)
        return None
    return r.json()


def get_availabilities(reason_id: int, organization_id: int,
    start_date: datetime, end_date: datetime, 
    client: httpx.Client = DEFAULT_CLIENT,
    request: ScraperRequest = None) -> list:
    availabilities = []
    week_size = AVECMONDOC_CONF.get("week_size", 5)
    page_date = start_date
    while page_date < end_date:
        week_availabilities = get_availabilities_week(reason_id, organization_id, page_date, client)
        if request:
            request.increase_request_count("slots" if page_date == start_date else "next-slots")
        page_date = page_date + timedelta(days=week_size)
        for week_availability in week_availabilities:
            if "slots" in week_availability:
                availabilities.append(week_availability)
            elif "nextAvailableBusinessHour" in week_availability:
                next_available_business_hour_in_current_week = week_availability.get(
                    "nextAvailableBusinessHourInCurrentWeek", False
                )
                next_available_business_hour = week_availability.get("nextAvailableBusinessHour", False)
                # pas de date cette semaine ni plus tard -> on arrête
                if (next_available_business_hour_in_current_week or next_available_business_hour) == False:
                    page_date = end_date
                    break
                # ce champ peut être False ou un dict
                if next_available_business_hour is False:
                    continue
                if "start" not in next_available_business_hour:
                    continue
                # on a trouvé la date du prochain slot, on se positionne à cette date
                page_date = isoparse(next_available_business_hour["start"]).replace(tzinfo=None)
    return availabilities


def count_appointements(availabilities: list, start_date: datetime, end_date: datetime) -> int:
    count = 0

    for availability in availabilities:
        for slot in availability["slots"]:
            if slot["businessHours"] is None:
                continue
            slot_dt = paris_tz.localize(isoparse(slot["businessHours"]["start"]).replace(tzinfo=None))
            if start_date <= slot_dt < end_date:
                count += 1
    return count


def parse_availabilities(availabilities: list) -> Tuple[Optional[datetime], int]:
    first_appointment = None
    appointment_count = 0
    for availability in availabilities:
        if "slots" not in availability:
            continue
        slots = availability["slots"]
        for slot in slots:
            if not slot["isAvailable"]:
                continue
            appointment_count += 1
            date = isoparse(slot["businessHours"]["start"])
            if first_appointment is None or date < first_appointment:
                first_appointment = date
    return first_appointment, appointment_count


@Profiling.measure("avecmondoc_slot")
def fetch_slots(request: ScraperRequest, client: httpx.Client = DEFAULT_CLIENT) -> Optional[str]:
    url = request.get_url()
    slug = url.split('/')[-1]
    organization = get_organization_slug(slug, client, request)
    if organization is None:
        return None
    if "error" in organization:
        logger.warning(organization["error"])   
    for speciality in organization["speciality"]:
        request.update_practitioner_type(DRUG_STORE if speciality["id"] == 190 else GENERAL_PRACTITIONER)
    organization_id = organization.get("id")
    reasons = organization.get("consultationReasons")
    if reasons is None:
        logger.warning(f"unable to get reasons from organization {organization_id}")
        return None
    if not get_valid_reasons(reasons):
        return None
    first_availability = None

    appointment_schedules = []
    s_date = paris_tz.localize(isoparse(request.get_start_date()) + timedelta(days=0))
    n_date = s_date + timedelta(days=CHRONODOSES["Interval"], seconds=-1)
    appointment_schedules.append(
        {"name": "chronodose", "from": s_date.isoformat(), "to": n_date.isoformat(), "total": 0}
    )
    for n in INTERVAL_SPLIT_DAYS:
        n_date = s_date + timedelta(days=n, seconds=-1)
        appointment_schedules.append(
            {
                "name": f"{n}_days",
                "from": s_date.isoformat(),
                "to": n_date.isoformat(),
                "total": 0
            }
        )

    for reason in get_valid_reasons(reasons):
        start_date = isoparse(request.get_start_date())
        end_date = start_date + timedelta(days=AVECMONDOC_CONF.get("slot_limit", 50))
        request.add_vaccine_type(get_vaccine_name(reason["reason"]))
        availabilities = get_availabilities(reason["id"], reason["organizationId"],
            start_date, end_date, client, request)
        date, appointment_count = parse_availabilities(availabilities)
        if date is None:
            continue
        request.appointment_count += appointment_count
        for appointment_schedule in appointment_schedules:
            s_date = isoparse(appointment_schedule["from"])
            n_date = isoparse(appointment_schedule["to"])
            name = appointment_schedule["name"]
            if name == "chronodose" and get_vaccine_name(reason["reason"]) not in CHRONODOSES["Vaccine"]:
                continue
            appointment_schedule["total"] += count_appointements(availabilities, s_date, n_date)
        request.appointment_schedules = appointment_schedules
        if first_availability is None or first_availability > date:
            first_availability = date
    if first_availability is None:
        return None
    return first_availability.isoformat()


def center_to_centerdict(center: CenterInfo) -> dict:
    center_dict = {}
    center_dict["rdv_site_web"] = center.url
    center_dict["nom"] = center.nom
    center_dict["type"] = DRUG_STORE
    center_dict["business_hours"] = center.metadata["business_hours"]
    center_dict["phone_number"] = center.metadata["phone_number"]
    center_dict["address"] = f'{center.metadata["address"]}, {center.location.cp} {center.location.city}' 
    center_dict["long_coor1"] = center.location.longitude
    center_dict["lat_coor1"] = center.location.latitude
    center_dict["com_nom"] = center.location.city
    center_dict["com_cp"] = center.location.cp
    center_dict["com_insee"] = departementUtils.cp_to_insee(center.location.cp)
    center_dict["gid"] = center.internal_id
    return center_dict


def has_valid_zipcode(organization : dict) -> bool: 
   return organization["zipCode"] is not None and len(organization["zipCode"]) == 5


def center_iterator(client: httpx.Client = DEFAULT_CLIENT) -> Iterator[dict]:
    organization_slugs = []
    # l'api fait parfois un timeout au premier appel
    for _ in range(0, AVECMONDOC_CONF.get("search_tries", 2)):
        search_result = search(client)
        if search_result:
            break
    if search_result is None:
        return []
    if "data" not in search_result:
        return []
    for slug in search_result["data"]:
        organizations = []
        slug_type = slug["type"]
        if slug_type == "doctor":
            doctor_id = slug["id"]
            organizations = [
                get_organization_slug(doctor_organization["slug"], client) 
                for doctor_organization in get_by_doctor(doctor_id, client)
            ]
        elif slug_type == "organization":
            organizations = [get_organization_slug(slug["organizationSlug"], client)]
        valid_organizations = [organization for organization in organizations if has_valid_zipcode(organization)]
        for organization in valid_organizations:
            organization_slug = organization["slug"]
            if organization_slug in organization_slugs:
                continue
            organization_slugs.append(organization_slug)
            center = organization_to_center(organization)
            if center is None:
                continue
            yield center_to_centerdict(center)


def main():  #  pragma: no cover
    for center in center_iterator():
        request = ScraperRequest(center["rdv_site_web"], datetime.now().strftime("%Y-%m-%d"))
        availability = fetch_slots(request)
        logger.info(f'{center["nom"]:48}: {availability}')

if __name__ == "__main__":  #  pragma: no cover
    main()
