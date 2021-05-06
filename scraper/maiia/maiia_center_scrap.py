import httpx
import json
import logging

from datetime import datetime, timedelta
from dateutil.parser import isoparse
from pathlib import Path
from utils.vmd_utils import departementUtils, format_phone_number
from scraper.pattern.center_info import get_vaccine_name
from scraper.pattern.scraper_result import DRUG_STORE, GENERAL_PRACTITIONER, VACCINATION_CENTER
from .maiia_utils import get_paged, MAIIA_LIMIT

timeout = httpx.Timeout(30.0, connect=30.0)
DEFAULT_CLIENT = httpx.Client(timeout=timeout)
logger = logging.getLogger("scraper")

MAIIA_URL = "https://www.maiia.com"
MAIIA_DAY_LIMIT = 50
CENTER_TYPES = ["centre-de-vaccination", "pharmacie", "centre-hospitalier-(ch)"]
MAIIA_DO_NOT_SCRAP_ID = ["603e4fae8c512e753fc49ba1"]
MAIIA_DO_NOT_SCRAP_NAME = ["test", "antigenique", "antigénique"]


def get_centers(speciality: str, client: httpx.Client = DEFAULT_CLIENT) -> list:
    result = get_paged(
        f"{MAIIA_URL}/api/pat-public/hcd?distanceMax=10000&AllVaccinationPlaces=true&speciality.shortName={speciality}",
        limit=50,
        client=client,
    )
    if "items" not in result:
        return []
    return result["items"]


def maiia_schedule_to_business_hours(opening_schedules) -> dict:
    business_hours = dict()
    days = {
        "Lundi": "MONDAY",
        "Mardi": "TUESDAY",
        "Mercredi": "WEDNESDAY",
        "Jeudi": "THURSDAY",
        "Vendredi": "FRIDAY",
        "Samedi": "SATURDAY",
        "Dimanche": "SUNDAY",
    }
    for key, value in days.items():
        schedules = opening_schedules[value]["schedules"]
        creneaux = list()
        for schedule in schedules:
            creneaux.append(f'{schedule["startTime"]}-{schedule["endTime"]}')
        if creneaux:
            business_hours[key] = " ".join(creneaux)
    return business_hours


def maiia_center_to_csv(center: dict, root_center: dict) -> dict:
    if "url" not in center:
        logger.warning(f"url not found - {center}")
    csv = dict()
    csv["gid"] = center.get("id")[:8]
    csv["nom"] = center.get("name")
    csv["rdv_site_web"] = f'{MAIIA_URL}{center["url"]}?centerid={center["id"]}'
    if "pharmacie" in center["url"]:
        csv["type"] = DRUG_STORE
    else:
        csv["type"] = VACCINATION_CENTER

    csv["vaccine_type"] = []
    for consultation_reason in root_center["consultationReasons"]:
        vaccine_name = get_vaccine_name(consultation_reason.get("name"))
        if vaccine_name and vaccine_name not in csv["vaccine_type"]:
            csv["vaccine_type"].append(vaccine_name)

    if "publicInformation" not in center:
        return csv

    if "address" in center["publicInformation"]:
        csv["com_insee"] = center["publicInformation"]["address"].get("inseeCode", "")
        if len(csv["com_insee"]) < 5:
            zip = center["publicInformation"]["address"].get("zipCode")
            csv["com_insee"] = departementUtils.cp_to_insee(zip)
        csv["address"] = center["publicInformation"]["address"].get("fullAddress")
        if "location" in center["publicInformation"]["address"]:
            csv["long_coor1"] = center["publicInformation"]["address"]["location"]["coordinates"][0]
            csv["lat_coor1"] = center["publicInformation"]["address"]["location"]["coordinates"][1]
        elif (
            "locality" in center["publicInformation"]["address"]
            and "location" in center["publicInformation"]["address"]["locality"]
        ):
            csv["long_coor1"] = center["publicInformation"]["address"]["locality"]["location"]["x"]
            csv["lat_coor1"] = center["publicInformation"]["address"]["locality"]["location"]["y"]
    if "officeInformation" in center["publicInformation"]:
        csv["phone_number"] = format_phone_number(
            center["publicInformation"]["officeInformation"].get("phoneNumber", "")
        )
        if "openingSchedules" in center["publicInformation"]["officeInformation"]:
            csv["business_hours"] = maiia_schedule_to_business_hours(
                center["publicInformation"]["officeInformation"]["openingSchedules"]
            )
    return csv


def main():
    centers = list()
    centers_ids = list()
    logger.info("Starting Maiia centers download")

    for speciality in CENTER_TYPES:
        logger.info(f"Fetching speciality {speciality}")
        result = get_centers(speciality)
        all_centers = list()
        for root_center in result:
            if root_center.get("type") != "CENTER":
                continue
            center = root_center["center"]
            if center["id"] in MAIIA_DO_NOT_SCRAP_ID:
                continue
            if not any(
                consultation_reason.get("injectionType") in ["FIRST"]
                and not any(keyword in consultation_reason.get("name").lower() for keyword in MAIIA_DO_NOT_SCRAP_NAME)
                for consultation_reason in root_center["consultationReasons"]
            ):
                continue
            if center["childCenters"]:
                continue
            centers.append(maiia_center_to_csv(center, root_center))
            centers_ids.append(center["id"])
            for child_center in center["childCenters"]:
                if (
                    child_center["speciality"]["code"] == "VAC01"
                    and "url" in child_center
                    and child_center["id"] not in centers_ids
                ):
                    centers.append(maiia_center_to_csv(child_center, root_center))
                    centers_ids.append(child_center["id"])

    output_path = Path("data", "output", "maiia_centers.json")
    with open(output_path, "w", encoding="utf8") as f:
        json.dump(centers, f, indent=2)
    logger.info(f"Saved {len(centers)} centers to {output_path}")


if __name__ == "__main__":
    main()
