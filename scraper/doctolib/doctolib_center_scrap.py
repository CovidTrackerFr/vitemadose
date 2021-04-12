import csv
import io
import json
import os
from urllib import parse
from pathlib import Path
from multiprocessing import Pool, freeze_support

import logging
import requests
from bs4 import BeautifulSoup

from utils.vmd_utils import departementUtils
from utils.vmd_logger import enable_logger_for_production

INFO_URL = "https://www.doctolib.fr{}.json"
SEARCH_URL = "https://www.doctolib.fr/vaccination-covid-19/france.json?page={}"
PARTNERS_URL = "https://partners.doctolib.fr"


DOCTOLIB_DOMAINS = [
    'https://partners.doctolib.fr',
    'https://www.doctolib.fr'
]

POOL_SIZE = int(os.getenv('POOL_SIZE', 15))

logger = logging.getLogger('scraper')


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
    response = requests.get(INFO_URL.format(url))
    response.raise_for_status()
    data = response.json()
    data = data["data"]
    

    etablissement["rdv_site_web"] = PARTNERS_URL + url
    etablissement['gid'] = "d" + str(data["profile"]["id"])
    etablissement["nom"] = data["profile"]["name_with_title"]
    etablissement['type'] = data["profile"]["subtitle"]
    # Parse place
    place = data["places"]

    # Parse practitioner type

    if not place:
        return etablissement
    place = place[0]  # for the moment

    # Parse place location 
    etablissement["address"] = place["full_address"]
    etablissement["long_coor1"] = place["longitude"]
    etablissement["lat_coor1"] = place["latitude"]
    etablissement["com_insee"] = place["zipcode"]


    # Parse landline number
    etablissement["phone_number"] = None

    if "landline_number" in place:
        etablissement['phone_number'] = place["landline_number"]

    return etablissement



def scrape_page(page_id=1, liste_ids=[]):
    liste_urls =[]
    try:
        response = requests.get(SEARCH_URL.format(page_id))
        response.raise_for_status()
        data = response.json()
        
    except Exception as e:
        logger.warning("Impossible de se connecter à Doctolib")
        data = {}

    etablissements = []
    
    if "data" in data:
        data = data["data"]
        # It even counts filtered URLs
        for doctor in data["doctors"]:
           
            if doctor["id"] not in liste_ids:
                liste_ids.append(doctor["id"])
                liste_urls.append(doctor["link"])

    return  liste_urls

def doctolib_iterator():

    liste_ids = []
    page = 1

    urls = True

    while urls:
        urls = scrape_page(page, liste_ids)

        for url in urls:
            yield url
        page += 1


def export_data(_etablissements):

    etablissements = []

    for etablissement in _etablissements:
        etablissements.append(etablissement)

    outpath = Path("data/output/doctolib-centers.json")
    with open(outpath, "w") as fichier:
        fichier.write(json.dumps(etablissements, indent=2))
                


def main():

    with Pool(POOL_SIZE) as pool:
        etablissements = pool.imap_unordered(
            get_infos_etablissement,
            doctolib_iterator(),
            1
        )

        export_data(etablissements)


if __name__ == "__main__":
    freeze_support()
    main()
