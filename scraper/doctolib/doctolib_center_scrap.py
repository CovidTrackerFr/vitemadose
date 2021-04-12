import csv
import io
import json
from urllib import parse
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from scraper.doctolib.doctolib_filters import get_etablissement_type
from utils.vmd_utils import departementUtils, format_phone_number
from utils.vmd_logger import enable_logger_for_production

BASE_URL = 'https://www.doctolib.fr/vaccination-covid-19/france?page={0}'
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


def get_csv():
    url = "https://www.data.gouv.fr/fr/datasets/r/5cb21a85-b0b0-4a65-a249-806a040ec372"
    response = requests.get(url)
    response.raise_for_status()

    reader = io.StringIO(response.content.decode('utf8'))
    csvreader = csv.DictReader(reader, delimiter=';')
    for row in csvreader:
        yield row


def get_doctolib_csv_urls():
    urls = []
    for center in get_csv():
        url = center['rdv_site_web']
        if len(url) == 0:
            continue
        is_doctolib_url = False
        for domain in DOCTOLIB_DOMAINS:
            if url.startswith(domain):
                is_doctolib_url = True
        if not is_doctolib_url:
            continue
        uri_info = parse.urlsplit(url)
        urls.append(uri_info.path)
    return urls


def is_url_in_csv(url, list):
    uri_info = parse.urlsplit(url)
    path = uri_info.path

    return path in list


def parse_doctolib_business_hours(url_data, place):
    # Opening hours
    business_hours = dict()
    keys = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
    if not place['opening_hours']:
        return url_data

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

    if business_hours:
        url_data['business_hours'] = business_hours
    return url_data


def get_infos_etablissement(url):

    etablissement = {}

    try:
        response = requests.get(BOOKING_URL.format(url))
        response.raise_for_status()
        data = response.json()
        
    except Exception as e:
            data = {}
    
    if "data" in data:
        data = data["data"]
        
        etablissement['gid'] = "d" + str(data["profile"]["id"])
        etablissement["nom"] = data["profile"]["name_with_title"]
        # Parse place
        place = data["places"]

        # Parse practitioner type

        if not place:
            return etablissement
        place = place[0]  # for the moment

        # Parse place location 
        etablissement['address'] = place['full_address']
        etablissement['long_coor1'] = place['longitude']
        etablissement['lat_coor1'] = place['latitude']
        etablissement["com_insee"] = place["zipcode"]
        etablissement["ville"] = place["city"]


        # Parse landline number
        etablissement["phone_number"] = None

        if "landline_number" in place:
            etablissement['phone_number'] = place["landline_number"]


        specialite = data["profile"]["speciality"]
        etablissement['type'] = get_etablissement_type(etablissement['nom'], specialite)

    return etablissement


def scrape_page(page_id=1, liste_ids=[]):

    try:
        response = requests.get(BASE_URL.format(page_id))
        response.raise_for_status()
        data = response.json()
        
    except Exception as e:
        data = {}

    etablissements = []
    
    if "data" in data:
        data = data["data"]
        # It even counts filtered URLs

        for doctor in data["doctors"]:
           
            if doctor["id"] not in liste_ids:
                liste_ids.append(doctor["id"])

                internal_api_url = doctor["link"].split('/')[-1]
                etablissement = get_infos_etablissement(internal_api_url)
                etablissement["rdv_site_web"] = PARTNERS_URL + doctor["link"]

            etablissements.append(etablissement)

    return etablissements


def main():

    liste_etablissements = []
    liste_ids = []
    page = 1

    etablissements_trouves = True

    while etablissements_trouves and page < 3:
    
        etablissements = scrape_page(page, liste_ids)
        if len(etablissements) == 0:
            etablissements_trouves = False
        else:
            liste_etablissements = liste_etablissements + etablissements
            page += 1

    outpath = Path("data/output/doctolib-centers.json")
    with open(outpath, "w") as fichier:
        fichier.write(json.dumps(liste_etablissements, indent=2))


if __name__ == "__main__":
    main()
