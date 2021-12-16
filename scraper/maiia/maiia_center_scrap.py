import httpx
import json
import logging

from pathlib import Path

from utils.vmd_config import get_conf_platform, get_conf_inputs
from utils.vmd_utils import departementUtils, format_phone_number
from scraper.pattern.vaccine import get_vaccine_name
from scraper.pattern.scraper_result import DRUG_STORE, VACCINATION_CENTER
from .maiia_utils import get_paged
from utils.vmd_utils import get_departements_numbers
import time
from urllib import parse
import requests

MAIIA_CONF = get_conf_platform("maiia")
MAIIA_API = MAIIA_CONF.get("api", {})
MAIIA_ENABLED = MAIIA_CONF.get("enabled", False)
MAIIA_SCRAPER = MAIIA_CONF.get("center_scraper", {})

timeout = httpx.Timeout(MAIIA_CONF.get("timeout", 25), connect=MAIIA_CONF.get("timeout", 25))
DEFAULT_CLIENT = httpx.Client(timeout=timeout)
logger = logging.getLogger("scraper")

MAIIA_URL = MAIIA_CONF.get("base_url")
CENTER_TYPES = MAIIA_SCRAPER.get("categories")
MAIIA_DO_NOT_SCRAP_ID = MAIIA_SCRAPER.get("excluded_ids", [])
MAIIA_DO_NOT_SCRAP_NAME = MAIIA_SCRAPER.get("excluded_names", [])


def get_atlas_correct_match(infos_page, atlas_center_list):
    data = requests.get(
        "https://api-adresse.data.gouv.fr/search/",
        params=[("q", infos_page["address"]), ("postcode", infos_page["com_cp"])],
    ).json()
    correct_atlas_gid = None

    try:
        id_adr = data["features"][0]["properties"]["id"]
        matching_atlas_for_id = [
            center_id for center_id, center_data in atlas_center_list.items() if center_data["id_adresse"] == id_adr
        ]
        if matching_atlas_for_id:
            correct_atlas_gid = matching_atlas_for_id[0]
    except:
        return None
    return correct_atlas_gid


def parse_atlas():
    url = get_conf_inputs().get("from_data_gouv_website").get("centers_gouv")
    data = requests.get(url).json()
    maiia_gouv_centers = {}
    for center in data["features"]:
        centre_pro = center["properties"].get("c_reserve_professionels_sante", False)
        url = center["properties"].get("c_rdv_site_web", None)
        id_adresse = center["properties"].get("c_id_adr", None)
        gid = center["properties"].get("c_gid", None)

        if centre_pro:
            continue
        if not url:
            continue
        if not gid:
            continue
        if not "maiia" in url:
            continue
        end_url = f'{parse.urlsplit(url).path.split("/")[-1]}'

        maiia_gouv_centers[gid] = {"url_end": end_url, "id_adresse": id_adresse}
    return maiia_gouv_centers


def get_centers(speciality: str, client: httpx.Client = DEFAULT_CLIENT, department=None) -> list:
    result = get_paged(
        MAIIA_API.get("scraper").format(speciality=speciality, department=department),
        limit=50,
        client=client,
    )
    return result["items"]


def maiia_schedule_to_business_hours(opening_schedules) -> dict:
    business_hours = dict()
    days = MAIIA_SCRAPER.get("business_days")
    for key, value in days.items():
        schedules = opening_schedules[value]["schedules"]
        creneaux = list()
        for schedule in schedules:
            creneaux.append(f'{schedule["startTime"]}-{schedule["endTime"]}')
        if creneaux:
            business_hours[key] = " ".join(creneaux)
    return business_hours


def maiia_center_to_csv(center: dict, root_center: dict, atlas_centers: dict) -> dict:
    if "url" not in center:
        logger.warning(f"url not found - {center}")

    atlas_matches = [
        center_id
        for center_id, center_data in atlas_centers.items()
        if center["url"].split("/")[-1] in center_data["url_end"]
    ]

    if len(atlas_matches) == 0:
        atlas_gid = None
    if len(atlas_matches) == 1:
        atlas_gid = max(atlas_matches)

    csv = dict()
    csv["gid"] = center.get("id")[:8]

    csv["nom"] = center.get("name")
    csv["rdv_site_web"] = f'{MAIIA_URL}{center["url"]}?centerid={center["id"]}'
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
        zip = center["publicInformation"]["address"].get("zipCode")
        csv["com_cp"] = zip
        csv["com_insee"] = center["publicInformation"]["address"].get("inseeCode", "")
        if len(csv["com_insee"]) < 5:
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
    if len(atlas_matches) > 1:
        atlas_gid = get_atlas_correct_match(csv, atlas_centers)
    csv["atlas_gid"] = atlas_gid

    return csv


def maiia_scrap(client: httpx.Client = DEFAULT_CLIENT, save=False):
    atlas_center_list = parse_atlas()
    centers = list()
    centers_ids = list()
    logger.info("Starting Maiia centers download")

    for speciality in CENTER_TYPES:

        logger.info(f"Fetching speciality {speciality}")
        result = []
        for department in get_departements_numbers():
            logger.info(f"Fetching department {department}")
            result_dep = get_centers(speciality, client, department)
            result += result_dep

        for root_center in result:

            if root_center.get("type") != "CENTER":
                continue
            center = root_center["center"]

            if center["id"] in MAIIA_DO_NOT_SCRAP_ID:
                continue

            # Si l'intégralité des motifs du centre sont des motifs exclus
            if sum(
                1 if keyword in consultation_reason.get("name").lower() else 0
                for keyword in MAIIA_DO_NOT_SCRAP_NAME
                for consultation_reason in root_center["consultationReasons"]
            ) == len(root_center["consultationReasons"]):
                continue

            if center["childCenters"]:
                continue

            centers.append(maiia_center_to_csv(center, root_center, atlas_center_list))
            centers_ids.append(center["id"])
            for child_center in center["childCenters"]:
                if (
                    child_center["speciality"]["code"] == MAIIA_SCRAPER.get("specialities")[0]
                    and "url" in child_center
                    and child_center["id"] not in centers_ids
                ):
                    centers.append(maiia_center_to_csv(child_center, root_center, atlas_center_list))
                    centers_ids.append(child_center["id"])
    if not save:
        return centers
    # pragma: no cover
    output_path = Path(MAIIA_SCRAPER.get("result_path"))
    with open(output_path, "w", encoding="utf8") as f:
        json.dump(centers, f, indent=2)
    logger.info(f"Saved {len(centers)} centers to {output_path}")
    return centers


def main():
    if not MAIIA_ENABLED:
        logger.error("Maiia scraper is disabled in configuration file.")
        return
    maiia_scrap(save=True)


if __name__ == "__main__":
    main()
