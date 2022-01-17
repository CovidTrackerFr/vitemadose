import os
import logging
from scraper.profiler import Profiling
from scraper.pattern.scraper_result import DRUG_STORE, GENERAL_PRACTITIONER
import httpx
import json

from datetime import datetime, timedelta
from dateutil.parser import isoparse, parse
from pytz import timezone
from typing import Iterator, Optional, Tuple
from scraper.creneaux.creneau import Creneau, Lieu, Plateforme, PasDeCreneau
from scraper.pattern.scraper_request import ScraperRequest
from scraper.pattern.center_info import CenterInfo, CenterLocation
from scraper.pattern.vaccine import Vaccine, get_vaccine_name
from utils.vmd_config import get_conf_platform, get_config
from utils.vmd_utils import departementUtils, DummyQueue


AVECMONDOC_CONF = get_conf_platform("avecmondoc")
AVECMONDOC_ENABLED = AVECMONDOC_CONF.get("enabled", False)
AVECMONDOC_API = AVECMONDOC_CONF.get("api", {})
AVECMONDOC_SCRAPER = AVECMONDOC_CONF.get("center_scraper", {})
AVECMONDOC_FILTERS = AVECMONDOC_CONF.get("filters", {})
AVECMONDOC_VALID_REASONS = AVECMONDOC_FILTERS.get("valid_reasons", [])
AVECMONDOC_HEADERS = {
    "User-Agent": os.environ.get("AVECMONDOC_API_KEY", ""),
}

NUMBER_OF_SCRAPED_DAYS = get_config().get("scrape_on_n_days", 28)
AVECMONDOC_DAYS_PER_PAGE = AVECMONDOC_CONF.get("days_per_page", 7)

timeout = httpx.Timeout(AVECMONDOC_CONF.get("timeout", 25), connect=AVECMONDOC_CONF.get("timeout", 25))
DEFAULT_CLIENT = httpx.Client(headers=AVECMONDOC_HEADERS, timeout=timeout)
logger = logging.getLogger("scraper")
paris_tz = timezone("Europe/Paris")


def search(client: httpx.Client = DEFAULT_CLIENT) -> Optional[list]:
    url = AVECMONDOC_API.get("search", "")
    limit = AVECMONDOC_API.get("search_page_size", 10)
    page = 1
    result = {"data": [], "hasNextPage": True}
    while result["hasNextPage"]:
        payload = {"limit": limit, "page": page}
        try:
            r = client.get(url, params=payload)
            r.raise_for_status()
        except httpx.TimeoutException as hex:
            logger.warning(f"{url} timed out (search)")
            return None
        except httpx.HTTPStatusError as hex:
            logger.warning(f"{url} returned error {hex.response.status_code}")
            logger.warning(r.content)
            return None
        try:
            paged_result = r.json()
        except json.decoder.JSONDecodeError as jde:
            logger.warning(f"{url} raised {jde}")
            break
        page += 1
        if result["data"] == []:
            result = paged_result
            continue
        result["hasNextPage"] = paged_result["hasNextPage"]
        for item in paged_result["data"]:
            result["data"].append(item)
        # logger.info(f"Downloaded {j['page']}/{j['pages']}")
    return result


def get_organization_slug(
    slug: str, client: httpx.Client = DEFAULT_CLIENT, request: ScraperRequest = None
) -> Optional[dict]:
    url = str(AVECMONDOC_API.get("get_organization_slug", "")).format(slug=slug)
    try:
        r = client.get(url)
        r.raise_for_status()
    except httpx.TimeoutException as hex:
        logger.warning(f"request timed out for center: {url} (get_slug)")
        if request:
            request.increase_request_count("time-out")
        return None
    except httpx.HTTPStatusError as hex:
        logger.warning(f"{url} returned error {hex.response.status_code}")
        logger.warning(r.content)
        if request:
            request.increase_request_count("error")
        return None
    if request:
        request.increase_request_count("cabinets")
    return r.json()


def get_reasons(
    organization_id: int, doctor_id: int, client: httpx.Client = DEFAULT_CLIENT, request: ScraperRequest = None
) -> Optional[list]:
    url = AVECMONDOC_API.get("get_reasons", "").format(id=id)
    payload = {"params": json.dumps({"organizationId": organization_id, "doctorId": doctor_id})}
    try:
        r = client.get(url, params=payload)
        r.raise_for_status()
    except httpx.TimeoutException as hex:
        logger.warning(f"request timed out for center: {url} (get_reasons)")
        if request:
            request.increase_request_count("time-out")
        return None
    except httpx.HTTPStatusError as hex:
        logger.warning(f"{url} returned error {hex.response.status_code}")
        logger.warning(r.content)
        if request:
            request.increase_request_count("error")
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
    center.type = DRUG_STORE
    for speciality in organization.get("speciality", []):
        if speciality.get("professionId", 0) == 14:
            center.type = GENERAL_PRACTITIONER
        elif speciality.get("professionId", 0) == 24:
            center.type = DRUG_STORE
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


def get_availabilities_week(
    reason_id: int, organization_id: int, start_date: datetime, client: httpx.Client = DEFAULT_CLIENT
) -> Optional[list]:
    url = AVECMONDOC_API.get("availabilities_per_day", "")
    payload = {
        "consultationReasonId": reason_id,
        "disabledPeriods": [],
        "fullDisplay": True,
        "organizationId": organization_id,
        "periodEnd": (start_date + timedelta(days=(AVECMONDOC_DAYS_PER_PAGE - 1))).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "periodStart": start_date.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "type": "inOffice",
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


def get_availabilities(
    reason_id: int,
    organization_id: int,
    start_date: datetime,
    end_date: datetime,
    client: httpx.Client = DEFAULT_CLIENT,
    request: ScraperRequest = None,
) -> list:
    availabilities = []
    page_date = start_date
    while page_date < end_date:
        week_availabilities = get_availabilities_week(reason_id, organization_id, page_date, client)
        if request:
            request.increase_request_count("slots" if page_date == start_date else "next-slots")
        page_date = page_date + timedelta(days=(AVECMONDOC_DAYS_PER_PAGE - 1))

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


@Profiling.measure("avecmondoc_slot")
def fetch_slots(
    request: ScraperRequest, creneau_q=DummyQueue(), client: httpx.Client = DEFAULT_CLIENT
) -> Optional[str]:
    if not AVECMONDOC_ENABLED:
        return None
    # Fonction principale avec le comportement "de prod".
    avecmondoc = AvecmonDoc(client=DEFAULT_CLIENT, creneau_q=creneau_q)
    return avecmondoc.fetch(request, client)


class AvecmonDoc:
    def __init__(self, creneau_q=DummyQueue, client: httpx.Client = DEFAULT_CLIENT):
        self.creneau_q = creneau_q
        self.lieu = None

    def found_creneau(self, creneau):
        self.creneau_q.put(creneau)

    def parse_availabilities(
        self, availabilities: list, request: ScraperRequest, vaccine: Vaccine, dose: Optional[list] = None
    ) -> Tuple[Optional[datetime], int]:
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
                self.found_creneau(
                    Creneau(
                        horaire=parse(slot["businessHours"]["start"]),
                        reservation_url=request.url,
                        type_vaccin=[vaccine],
                        lieu=self.lieu,
                        dose=dose,
                    )
                )
                if first_appointment is None or date < first_appointment:
                    first_appointment = date
        return first_appointment, appointment_count

    def fetch(self, request, client):
        url = request.get_url()
        slug = url.split("/")[-1]
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

        self.lieu = Lieu(
            plateforme=Plateforme.AVECMONDOC,
            url=request.url,
            location=request.center_info.location,
            nom=request.center_info.nom,
            internal_id=request.internal_id,
            departement=request.center_info.departement,
            lieu_type=request.practitioner_type,
            metadata=request.center_info.metadata,
        )

        for reason in get_valid_reasons(reasons):
            start_date = isoparse(request.get_start_date())
            end_date = start_date + timedelta(days=NUMBER_OF_SCRAPED_DAYS)
            vaccine = get_vaccine_name(reason["reason"])
            dose = get_vaccine_dose(reason["reason"])
            request.add_vaccine_type(vaccine)
            availabilities = get_availabilities(
                reason["id"], reason["organizationId"], start_date, end_date, client, request
            )
            date, appointment_count = self.parse_availabilities(availabilities, request, vaccine, dose)
            if date is None:
                continue
            request.appointment_count += appointment_count
            if first_availability is None or first_availability > date:
                first_availability = date
        if first_availability is None:
            if self.lieu:
                self.found_creneau(PasDeCreneau(lieu=self.lieu, phone_only=request.appointment_by_phone_only))
            return None
        return first_availability.isoformat()

def get_vaccine_dose(motive_name: str) -> Optional[list]:
    if not motive_name:
        return None
    dose = []
    motive_low = motive_name.lower()
    if (
        "première" in motive_low 
        or "premiere" in motive_low
        or "1è" in motive_low
    ):
        dose.append(1)
    if (
        "deuxième" in motive_low
        or "deuxieme" in motive_low
        or "seconde" in motive_low
        or "2è" in motive_low
    ):
        dose.append(2)
    if (
        "rappel" in motive_low
        or "troisième" in motive_low
        or "troisieme" in motive_low
        or "3è" in motive_low
    ):
        dose.append(3)
    return dose

def center_to_centerdict(center: CenterInfo) -> dict:
    center_dict = {}
    center_dict["rdv_site_web"] = center.url
    center_dict["nom"] = center.nom
    center_dict["type"] = center.type
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


def has_valid_zipcode(organization: dict) -> bool:
    return (
        organization is not None and organization.get("zipCode", None) is not None and len(organization["zipCode"]) == 5
    )


def center_iterator(client: httpx.Client = DEFAULT_CLIENT) -> Iterator[dict]:
    if not AVECMONDOC_ENABLED:
        logger.warning("Avecmondoc scrap is disabled in configuration file.")
        return []
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
    for structure in search_result["data"]:
        if structure.get("businessHoursCovidCount", 0) == 0:
            continue
        slug = structure["url"].split("/")[-1]
        organizations = [get_organization_slug(slug, client)]
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
        count = request.appointment_count
        logger.info(f'{center["nom"]:48}: {availability} ({count})')


if __name__ == "__main__":  #  pragma: no cover
    main()
