from time import sleep, time
from scraper.pattern.scraper_result import (
    DRUG_STORE,
    GENERAL_PRACTITIONER,
    VACCINATION_CENTER,
)
from utils.vmd_config import get_conf_platform, get_conf_inputs
from utils.vmd_utils import departementUtils, format_phone_number
from utils.vmd_logger import get_logger
from scraper.doctolib.doctolib import DOCTOLIB_HEADERS
from scraper.doctolib.doctolib_filters import is_vaccination_center

from typing import List, Union, Tuple
import requests
import json
from urllib import parse
import requests
import os
import re
from unidecode import unidecode

DOCTOLIB_CONF = get_conf_platform("doctolib")
DOCTOLIB_API = DOCTOLIB_CONF.get("api", {})
BASE_URL = DOCTOLIB_API.get("scraper")
BASE_URL_DEPARTEMENT = DOCTOLIB_API.get("scraper_dep")
BOOKING_URL = DOCTOLIB_API.get("booking")

SCRAPER_CONF = DOCTOLIB_CONF.get("center_scraper", {})
CENTER_TYPES = SCRAPER_CONF.get("categories", [])

DOCTOLIB_DOMAINS = DOCTOLIB_CONF.get("recognized_urls", [])

DOCTOLIB_WEIRD_DEPARTEMENTS = SCRAPER_CONF.get("dep_conversion", {})

logger = get_logger()

booking_requests = {}

def parse_doctolib_centers(page_limit=None) -> List[dict]:
    centers = []
    unique_urls = []

    for departement in get_departements():
        logger.info(f"[Doctolib centers] Parsing pages of departement {departement} through department SEO link")
        centers_departements, unique_urls = parse_pages_departement(departement, unique_urls)
        if centers_departements == 0:
            raise Exception("No Value found for department {}, crashing")
        centers += centers_departements

    centers = list(filter(is_vaccination_center, centers))  # Filter vaccination centers
    centers = list(map(center_reducer, centers))  # Remove fields irrelevant to the front

    return centers


def get_departements():
    import csv

    # Guyane uses Maiia and does not have doctolib pages
    NOT_INCLUDED_DEPARTEMENTS = ["Guyane"]
    with open(get_conf_inputs().get("departements"), encoding="utf8", newline="\n") as csvfile:
        reader = csv.DictReader(csvfile)
        departements = [str(row["nom_departement"]) for row in reader]
        [departements.remove(ndep) for ndep in NOT_INCLUDED_DEPARTEMENTS]
        return departements


def parse_pages_departement(departement, unique_urls: List[str]):
    departement = doctolib_urlify(departement)
    page_id = 1
    page_has_centers = True

    for weird_dep in DOCTOLIB_WEIRD_DEPARTEMENTS:
        if weird_dep == departement:
            departement = DOCTOLIB_WEIRD_DEPARTEMENTS[weird_dep]
            break
    centers = []
    while page_has_centers:
        logger.info(f"[Doctolib centers] Parsing page {page_id} of {departement}")
        centers_page, unique_urls = parse_page_centers_departement(departement, page_id, unique_urls)
        centers += centers_page

        page_id += 1

        if len(centers_page) == 0:
            page_has_centers = False

    return centers, unique_urls


def parse_page_centers_departement(departement: str, page_id: int,
                                   unique_urls: List[str]) -> Tuple[List[dict], List[str]]:
    try:
        url = doctolib_urlify(departement)
        if url in unique_urls:
            return [], unique_urls
        r = requests.get(
            BASE_URL_DEPARTEMENT.format(url, page_id),
            headers=DOCTOLIB_HEADERS,
        )
        data = r.json()
        unique_urls.append(url)
    except:
        logger.warning(f"Cannot reach {BASE_URL_DEPARTEMENT.format(doctolib_urlify(departement), page_id)}")
        return [], unique_urls

    return get_centers_info(data, unique_urls)


def get_centers_info(data: dict, unique_urls: List[str]) -> Tuple[List[dict], List[str]]:
    centers_page = []
    centers = []
    # TODO parallelism can be put here
    for payload in data["data"]["doctors"]:
        # If the "doctor" hasn't already been checked
        if payload["link"] not in unique_urls:
            unique_urls.append(payload["link"])
            # One "doctor" can have multiple places, hence center_from_doctor_dict returns a list
            centers, unique_urls = center_from_doctor_dict(payload, unique_urls)
            centers_page += centers
    return centers_page, unique_urls


def doctolib_urlify(departement: str) -> str:
    departement = re.sub(r"[^\w\s\-]", "-", departement)
    departement = re.sub(r"\s+", "-", departement).lower()
    return unidecode(departement)


def center_from_doctor_dict(doctor_dict, unique_urls: List[str]) -> Tuple[List[dict], List[str]]:
    liste_centres = []
    nom = doctor_dict["name_with_title"]
    sub_addresse = doctor_dict["address"]
    ville = doctor_dict["city"]
    code_postal = doctor_dict["zipcode"].replace(" ", "").strip()
    addresse = f"{sub_addresse}, {code_postal} {ville}"
    url_path = doctor_dict["link"]
    _type = center_type(url_path, nom)

    dict_infos_centers_page, unique_urls = get_dict_infos_center_page(url_path, unique_urls)
    if not dict_infos_centers_page:
        return [], unique_urls
    longitude, latitude = get_coordinates(doctor_dict)
    dict_infos_browse_page = {
        "nom": nom,
        "ville": ville,
        "address": addresse,
        "long_coor1": longitude,
        "lat_coor1": latitude,
        "type": _type,
        "com_insee": departementUtils.cp_to_insee(code_postal),
        "com_cp": code_postal,
    }

    for info_center in dict_infos_centers_page:
        info_center["rdv_site_web"] = f"https://www.doctolib.fr{url_path}?pid={info_center['place_id']}"
        liste_centres.append({**dict_infos_browse_page, **info_center})

    return liste_centres, unique_urls


def get_coordinates(doctor_dict):
    longitude = doctor_dict["position"]["lng"]
    latitude = doctor_dict["position"]["lat"]
    if longitude:
        longitude = float(longitude)
    if latitude:
        latitude = float(latitude)
    return longitude, latitude


def get_dict_infos_center_page(url_path: str, unique_urls: List[str]) -> Tuple[list, List[str]]:
    center_name = parse.urlsplit(url_path).path.split("/")[-1]
    internal_api_url = BOOKING_URL.format(centre=center_name)
    logger.info(f"> Parsing {internal_api_url}")
    liste_infos_page = []
    try:
        data = None
        if center_name in booking_requests:
            data = booking_requests.get(center_name)
        else:
            data = requests.get(internal_api_url)
            data.raise_for_status()
            booking_requests[center_name] = data
        output = data.json().get("data", {})
    except:
        logger.warning(f"> Could not retrieve data from {internal_api_url}")
        return liste_infos_page, unique_urls

    # Parse place
    places = output.get("places", {})
    for place in places:
        infos_page = {}
        # Parse place location
        infos_page["gid"] = "d{0}".format(output.get("profile", {}).get("id", ""))
        infos_page["place_id"] = place["id"]
        infos_page["nom"] = output.get("profile", {}).get("name_with_title", "")
        infos_page["ville"] = place.get("city", "")
        infos_page["address"] = place["full_address"]
        infos_page["long_coor1"] = place.get("longitude")
        infos_page["lat_coor1"] = place.get("latitude")
        cp = place["zipcode"].replace(" ", "").strip()
        infos_page["com_cp"] = cp
        infos_page["com_insee"] = departementUtils.cp_to_insee(cp)

        # Parse landline number
        if place.get("landline_number"):
            phone_number = place.get("landline_number")
        else:
            phone_number = place.get("phone_number")
        if phone_number:
            infos_page["phone_number"] = format_phone_number(phone_number)

        infos_page["business_hours"] = parse_doctolib_business_hours(place)

        # Parse visit motives, not sure it's the right place to do it, maybe this function should be refactored
        extracted_visit_motives = output.get("visit_motives", [])
        infos_page["visit_motives"] = list(map(lambda vm: vm.get("name"), extracted_visit_motives))
        liste_infos_page.append(infos_page)

    # Returns a list with data for each place
    return liste_infos_page, unique_urls


def parse_doctolib_business_hours(place) -> dict:
    # Opening hours
    business_hours = dict()
    keys = SCRAPER_CONF.get("business_days", [])
    if not place["opening_hours"]:
        return None

    for opening_hour in place["opening_hours"]:
        format_hours = ""
        key_name = keys[opening_hour["day"] - 1]
        if not opening_hour.get("enabled", False):
            business_hours[key_name] = None
            continue
        for range in opening_hour["ranges"]:
            if len(format_hours) > 0:
                format_hours += ", "
            format_hours += f"{range[0]}-{range[1]}"
        business_hours[key_name] = format_hours

    return business_hours


def center_type(url_path: str, nom: str) -> str:
    ctypes = SCRAPER_CONF.get("center_types", [])
    for key in ctypes:
        if key in nom.lower() or key in url_path:
            return ctypes[key]
    return ctypes.get("*", VACCINATION_CENTER)


def center_reducer(center: dict) -> dict:
    """This function should be used to remove fields that are irrelevant to the front,
    such as fields used to filter centers during scraping process.
    Removes following fields : visit_motives

    Parameters
    ----------
    center_dict : "Center" dict
        Center dict, output by the doctolib_center_scrap.center_from_doctor_dict

    Returns
    ----------
    center dict, without irrelevant fields to the front

    Example
    ----------
    >>> center_reducer({'gid': 'd257554', 'visit_motives': ['1re injection vaccin COVID-19 (Pfizer-BioNTech)', '2de injection vaccin COVID-19 (Pfizer-BioNTech)', '1re injection vaccin COVID-19 (Moderna)', '2de injection vaccin COVID-19 (Moderna)']})
    {'gid': 'd257554'}
    """
    center.pop("visit_motives", "place_id")

    return center


if __name__ == "__main__":  # pragma: no cover
    if DOCTOLIB_CONF.get("enabled", False):
        centers = parse_doctolib_centers()
        path_out = SCRAPER_CONF.get("result_path")
        logger.info(f"Found {len(centers)} centers on Doctolib")
        logger.info(f"> Writing them on {path_out}")
        with open(path_out, "w") as f:
            f.write(json.dumps(centers, indent=2))
    else:
        logger.error(f"Doctolib scraper is disabled in configuration file.")
        exit(1)
