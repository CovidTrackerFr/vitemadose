from time import sleep, time
from scraper.pattern.scraper_result import DRUG_STORE, GENERAL_PRACTITIONER, VACCINATION_CENTER
from utils.vmd_utils import departementUtils, format_phone_number
from utils.vmd_logger import get_logger
from scraper.doctolib.doctolib import DOCTOLIB_HEADERS

from typing import List
import requests
import json
from urllib import parse
import requests
import os
import re
from unidecode import unidecode

BASE_URL = 'http://www.doctolib.fr/vaccination-covid-19/france.json?page={0}'
BASE_URL_DEPARTEMENT = "http://www.doctolib.fr/vaccination-covid-19/{0}.json?page={1}"
BOOKING_URL = 'https://www.doctolib.fr/booking/{0}.json'

CENTER_TYPES = [
    'hopital-public',
    'centre-de-vaccinations-internationales',
    'centre-de-sante',
    'pharmacie',
    'medecin-generaliste',
    'centre-de-vaccinations-internationales',
    'centre-examens-de-sante'
]

DOCTOLIB_DOMAINS = [
    'https://partners.doctolib.fr',
    'https://www.doctolib.fr'
]


logger = get_logger()


def parse_doctolib_centers(page_limit=None) -> List[dict]:
    centers = []

    page_id = 1
    page_has_centers = True
    while (page_has_centers and not page_limit) or (page_limit and page_limit > page_id):
        logger.info(f"[Doctolib centers] Parsing page {page_id}")
        centers_page = parse_page_centers(page_id)
        centers += centers_page

        page_id += 1

        if len(centers_page) == 0:
            page_has_centers = False

    for problematic_departement in ["gers", "jura", "var", "paris"]:
        logger.info(
            f"[Doctolib centers] Parsing pages of departement {problematic_departement} through department SEO link")
        centers_departements = parse_pages_departement(
            problematic_departement)
        centers += centers_departements

    return centers


def parse_pages_departement(departement):
    departement = doctolib_urlify(departement)
    page_id = 1
    page_has_centers = True

    centers = []

    while page_has_centers:
        logger.info(
            f"[Doctolib centers] Parsing page {page_id} of {departement}")
        centers_page = parse_page_centers_departement(departement, page_id)
        centers += centers_page

        page_id += 1

        if len(centers_page) == 0:
            page_has_centers = False

    return centers


def parse_page_centers_departement(departement, page_id) -> List[dict]:
    r = requests.get(BASE_URL_DEPARTEMENT.format(
        doctolib_urlify(departement), page_id), headers=DOCTOLIB_HEADERS)
    data = r.json()

    # TODO parallelism can be put here
    centers_page = [center_from_doctor_dict(payload)
                    for payload in data["data"]["doctors"]]
    return centers_page


def doctolib_urlify(departement: str) -> str:
    departement = re.sub(r"[^\w\s\-]", '-', departement)
    departement = re.sub(r"\s+", '-', departement).lower()
    return unidecode(departement)


def parse_page_centers(page_id) -> List[dict]:
    r = requests.get(BASE_URL.format(page_id), headers=DOCTOLIB_HEADERS)
    data = r.json()

    # TODO parallelism can be put here
    centers_page = [center_from_doctor_dict(payload)
                    for payload in data["data"]["doctors"]]
    return centers_page


def center_from_doctor_dict(doctor_dict) -> dict:
    nom = doctor_dict['name_with_title']
    sub_addresse = doctor_dict["address"]
    ville = doctor_dict["city"]
    code_postal = doctor_dict["zipcode"]
    addresse = f"{sub_addresse}, {code_postal} {ville}"
    if doctor_dict.get('place_id'):
        url_path = f"{doctor_dict['link']}?pid={str(doctor_dict['place_id'])}"
    else:
        url_path = doctor_dict['link']
    rdv_site_web = f"https://partners.doctolib.fr{url_path}"
    type = center_type(url_path, nom)
    dict_infos_center_page = get_dict_infos_center_page(url_path)
    dict_infos_browse_page = {
        "nom": nom,
        "rdv_site_web": rdv_site_web,
        "ville": ville,
        "address": addresse,
        "long_coor1": float(doctor_dict["position"]["lng"]),
        "lat_coor1": float(doctor_dict["position"]["lat"]),
        "type": type,
        "com_insee": departementUtils.cp_to_insee(code_postal)
    }
    return {**dict_infos_center_page, **dict_infos_browse_page}


def get_dict_infos_center_page(url_path: str) -> dict:
    internal_api_url = BOOKING_URL.format(
        parse.urlsplit(url_path).path.split("/")[-1])
    logger.info(f"> Parsing {internal_api_url}")
    data = requests.get(internal_api_url)
    data.raise_for_status()
    output = data.json().get('data', {})

    # Parse place
    places = output.get('places', {})
    if places:
        place = find_place(places, url_path)

        # Parse place location
        infos_page = {}
        infos_page['gid'] = 'd{0}'.format(output.get('profile', {}).get('id', ''))
        infos_page['address'] = place['full_address']
        infos_page['long_coor1'] = place.get('longitude')
        infos_page['lat_coor1'] = place.get('latitude')
        infos_page["com_insee"] = departementUtils.cp_to_insee(
            place["zipcode"])

        # Parse landline number
        if place.get('landline_number'):
            phone_number = place.get('landline_number')
        else:
            phone_number = place.get('phone_number')
        if phone_number:
            infos_page['phone_number'] = format_phone_number(phone_number)

        infos_page["business_hours"] = parse_doctolib_business_hours(place)
        return infos_page
    else:
        return {}


def find_place(places, url_path):
    pid = get_pid(url_path)
    if pid:
        for place in places:
            if place["id"] == pid:
                return place
    return places[0]


def get_pid(url_path) -> str:
    split = url_path.split("?pid=")
    if len(split) == 1:
        return ""
    else:
        return split[1]


def parse_doctolib_business_hours(place) -> dict:
    # Opening hours
    business_hours = dict()
    keys = ["lundi", "mardi", "mercredi",
            "jeudi", "vendredi", "samedi", "dimanche"]
    if not place['opening_hours']:
        return None

    for opening_hour in place['opening_hours']:
        format_hours = ''
        key_name = keys[opening_hour['day'] - 1]
        if not opening_hour.get('enabled', False):
            business_hours[key_name] = None
            continue
        for range in opening_hour['ranges']:
            if len(format_hours) > 0:
                format_hours += ', '
            format_hours += f'{range[0]}-{range[1]}'
        business_hours[key_name] = format_hours

    return business_hours


def center_type(url_path: str, nom: str) -> str:
    if "pharmacie" in nom.lower() or "pharmacie" in url_path:
        return DRUG_STORE
    if "medecin" in url_path or "medecin" in nom.lower():
        return GENERAL_PRACTITIONER
    return VACCINATION_CENTER


if __name__ == "__main__":
    centers = parse_doctolib_centers()
    path_out = 'data/output/doctolib-centers.json'
    logger.info(f"Found {len(centers)} centers on Doctolib")
    logger.info(f"> Writing them on {path_out}")
    with open(path_out, 'w') as f:
        f.write(json.dumps(centers, indent=2))
