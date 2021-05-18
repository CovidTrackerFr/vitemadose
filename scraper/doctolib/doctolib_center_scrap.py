import multiprocessing

from scraper.pattern.scraper_result import VACCINATION_CENTER
from utils.vmd_config import get_conf_platform, get_conf_inputs
from utils.vmd_utils import departementUtils, format_phone_number
from utils.vmd_logger import get_logger

from scraper.doctolib.conf import DoctolibConf
from scraper.doctolib.doctolib import DOCTOLIB_HEADERS
from scraper.doctolib.doctolib_filters import is_vaccination_center

from typing import Dict, List, Tuple
import requests
import json
from urllib import parse
import requests
import re
from unidecode import unidecode

DOCTOLIB_CONF = DoctolibConf(**get_conf_platform("doctolib"))
SCRAPER_CONF = DOCTOLIB_CONF.center_scraper

BASE_URL_DEPARTEMENT = DOCTOLIB_CONF.api.get("scraper_dep")
BOOKING_URL = DOCTOLIB_CONF.api.get("booking")

logger = get_logger()


def run_departement_scrap(departement: str):
    logger.info(f"[Doctolib centers] Parsing pages of departement {departement} through department SEO link")
    centers_departements = parse_pages_departement(departement)
    if centers_departements == 0:
        raise Exception("No Value found for department {}, crashing")
    return centers_departements


def parse_doctolib_centers(page_limit=None) -> List[dict]:
    centers = []
    unique_center_urls = []

    with multiprocessing.Pool(50) as pool:
        center_lists = pool.imap_unordered(run_departement_scrap, get_departements())
        centers = []

        for center_list in center_lists:
            centers.extend(center_list)
        centers = list(filter(is_vaccination_center, centers))  # Filter vaccination centers
        centers = list(map(center_reducer, centers))  # Remove fields irrelevant to the front

        for item in list(centers):
            if item.get("rdv_site_web") in unique_center_urls:
                centers.remove(item)
                continue
            unique_center_urls.append(item.get("rdv_site_web"))

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


def parse_pages_departement(departement):
    departement = doctolib_urlify(departement)
    page_id = 1
    page_has_centers = True
    liste_urls = []

    for weird_dep in SCRAPER_CONF.dep_conversion:
        if weird_dep == departement:
            departement = SCRAPER_CONF.dep_conversion[weird_dep]
            break
    centers = []
    while page_has_centers:
        logger.info(f"[Doctolib centers] Parsing page {page_id} of {departement}")
        centers_page, stop = parse_page_centers_departement(departement, page_id, liste_urls)
        centers += centers_page

        page_id += 1

        if len(centers_page) == 0 or stop:
            page_has_centers = False

    return centers


def parse_page_centers_departement(departement, page_id, liste_urls) -> Tuple[List[dict], bool]:
    try:
        r = requests.get(
            BASE_URL_DEPARTEMENT.format(doctolib_urlify(departement), page_id),
            headers=DOCTOLIB_HEADERS,
        )
        data = r.json()
    except:
        logger.warn(
            f"> Could not retrieve centers from department {departement} page_id {page_id}. Request status code: {r.status_code}"
        )
        return [], False

    centers_page = []

    # TODO parallelism can be put here
    for payload in data["data"]["doctors"]:
        # If the "doctor" hasn't already been checked
        if payload["link"] not in liste_urls:
            liste_urls.append(payload["link"])
            # One "doctor" can have multiple places, hence center_from_doctor_dict returns a list
            centers, stop = center_from_doctor_dict(payload)
            centers_page += centers
            if stop:
                return centers_page, True

    return centers_page, False


def doctolib_urlify(departement: str) -> str:
    departement = re.sub(r"\s+|\W", "-", departement).lower()
    return unidecode(departement)


def center_from_doctor_dict(doctor_dict) -> Tuple[dict, bool]:
    liste_centres = []
    dict_infos_browse_page = parse_doctor(doctor_dict)
    url_path = doctor_dict["link"]
    dict_infos_centers_page = get_dict_infos_center_page(url_path)

    for info_center in dict_infos_centers_page:
        info_center["rdv_site_web"] = f"https://www.doctolib.fr{url_path}?pid={info_center['place_id']}"
        # info center overrides the keys found in the SEO page if they are different
        # This is for when centers have multiple practice-ids which are also centers with different addresses
        liste_centres.append({**dict_infos_browse_page, **info_center})

    stop = not doctor_dict["exact_match"]
    return liste_centres, stop


def get_coordinates(doctor_dict):
    longitude = doctor_dict["position"]["lng"]
    latitude = doctor_dict["position"]["lat"]
    if longitude:
        longitude = float(longitude)
    if latitude:
        latitude = float(latitude)
    return longitude, latitude


def parse_doctor(doctor_dict: Dict) -> Dict:
    nom = doctor_dict["name_with_title"]
    sub_addresse = doctor_dict["address"]
    ville = doctor_dict["city"]
    code_postal = doctor_dict["zipcode"].replace(" ", "").strip()
    addresse = f"{sub_addresse}, {code_postal} {ville}"
    url_path = doctor_dict["link"]
    _type = center_type(url_path, nom)
    longitude, latitude = get_coordinates(doctor_dict)
    return {
        "nom": nom,
        "ville": ville,
        "address": addresse,
        "long_coor1": longitude,
        "lat_coor1": latitude,
        "type": _type,
        "com_insee": departementUtils.cp_to_insee(code_postal),
    }


def get_dict_infos_center_page(url_path: str) -> list[dict]:
    internal_api_url = BOOKING_URL.format(centre=parse.urlsplit(url_path).path.split("/")[-1])
    logger.info(f"> Parsing {internal_api_url}")
    output = None

    try:
        req = requests.get(internal_api_url)
        req.raise_for_status()
        data = req.json()
        output = data.get("data", {})
    except:
        logger.warn(f"> Could not retrieve data from {internal_api_url}")
        return []

    return parse_center_places(output)


def parse_center_places(center_output: Dict) -> List[Dict]:
    places = center_output.get("places", {})
    gid = "d{0}".format(center_output.get("profile", {}).get("id", ""))
    extracted_visit_motives = [vm.get("name") for vm in center_output.get("visit_motives", [])]

    liste_infos_page = []
    for place in places:
        infos_page = parse_place(place)
        infos_page["gid"] = gid
        infos_page["visit_motives"] = extracted_visit_motives
        infos_page["booking"] = center_output
        liste_infos_page.append(infos_page)

    # Returns a list with data for each place
    return liste_infos_page


def parse_place(place: Dict) -> Dict:
    infos_page = {}
    # Parse place location
    infos_page["place_id"] = place["id"]
    infos_page["address"] = place["full_address"]
    infos_page["ville"] = place["city"]
    infos_page["long_coor1"] = place.get("longitude")
    infos_page["lat_coor1"] = place.get("latitude")
    infos_page["com_insee"] = departementUtils.cp_to_insee(place["zipcode"].replace(" ", "").strip())
    # Parse landline number
    if place.get("landline_number"):
        phone_number = place.get("landline_number")
    else:
        phone_number = place.get("phone_number")
    if phone_number:
        infos_page["phone_number"] = format_phone_number(phone_number)

    infos_page["business_hours"] = parse_doctolib_business_hours(place)
    return infos_page


def parse_doctolib_business_hours(place) -> dict:
    # Opening hours
    business_hours = dict()
    if not place["opening_hours"]:
        return None

    for opening_hour in place["opening_hours"]:
        format_hours = ""
        key_name = SCRAPER_CONF.business_days[opening_hour["day"] - 1]
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
    for key in SCRAPER_CONF.center_types:
        if key in nom.lower() or key in url_path:
            return SCRAPER_CONF.center_types[key]
    return SCRAPER_CONF.center_types.get("*", VACCINATION_CENTER)


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
    if DOCTOLIB_CONF.enabled:
        centers = parse_doctolib_centers()
        path_out = SCRAPER_CONF.result_path
        logger.info(f"Found {len(centers)} centers on Doctolib")
        if len(centers) < 2000:
            # for reference, on 13-05, there were 12k centers
            logger.error(f"[NOT SAVING RESULTS]{len(centers)} does not seem like enough Doctolib centers")
        else:
            logger.info(f"> Writing them on {path_out}")
            with open(path_out, "w") as f:
                f.write(json.dumps(centers))
    else:
        logger.error(f"Doctolib scraper is disabled in configuration file.")
        exit(1)
