import httpx
import requests
import os
import re
from bs4 import BeautifulSoup
import csv
import json
import time

insee = {}


def search(max_page=1000):

    BASE_URL = "https://www.doctolib.fr"
    RECHERCHE_URL = "/vaccination-covid-19/france?"
    PARAMETRES = "ref_visit_motive_ids[]=6970&ref_visit_motive_ids[]=7005&ref_visit_motive_ids[]=7107"

    DOCTOLIB_SLOT_LIMIT = 50

    DOCTOLIB_HEADERS = {
        'X-Covid-Tracker-Key': os.environ.get('DOCTOLIB_API_KEY', ''),
    }

    DEFAULT_CLIENT: httpx.Client

    if os.getenv('WITH_TOR', 'no') == 'yes':
        session = requests.Session()
        session.proxies = {  # type: ignore
            'http': 'socks5://127.0.0.1:9050',
            'https': 'socks5://127.0.0.1:9050',
        }
        DEFAULT_CLIENT = session  # type: ignore
    else:
        DEFAULT_CLIENT = httpx.Client()

    page = 1
    liste_centres = []

    centres = True

    while centres and page <= max_page:

        url_recherche = BASE_URL + RECHERCHE_URL + "page=" + str(page) + "&" + PARAMETRES

        response = DEFAULT_CLIENT.get(url_recherche, headers=DOCTOLIB_HEADERS)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, "html.parser")

        centres = soup.find_all("div", {"class": "dl-search-result"})

        for _centre in centres:

            centre = {}

            centre['gid'] = _centre.get('id')[14:]

            nom = _centre.select_one(".dl-search-result-name").getText()
            centre['nom'] = nom

            rdv_site_web = BASE_URL + _centre.select_one('a[data-analytics-event-action="bookAppointmentButton"]')['href']
            centre['rdv_site_web'] = rdv_site_web


            adresse = _centre.select_one('.dl-text.dl-text-body.dl-text-s').getText().split(' ')
            centre["com_insee"] = cp_to_insee(recherche_cp(adresse))

            liste_centres.append(centre)

        print("page", page)
        page+=1

    with open("data/output/centres_doctolib.json", "w") as outfile:
        outfile.write(json.dumps(liste_centres, indent=2))



def recherche_cp(adresse):

    trouve = False
    i = len(adresse)

    while not trouve:
        code_postal = adresse[i-1]

        if code_postal.isnumeric():
            trouve = code_postal

        i-=1

    return trouve

def cp_to_insee(cp):
    insee_com = cp  # si jamais on ne trouve pas de correspondance...
    # on charge la table de correspondance cp/insee, une seule fois
    global insee
    if insee == {}:
        with open("data/input/codepostal_to_insee.json") as json_file:
            insee = json.load(json_file)
    if cp in insee:
        insee_com = insee.get(cp).get("insee")
    else:
        print('erreur cp:', cp)
    return insee_com

def centre_iterator(max_page=1000):

    BASE_URL = "https://www.doctolib.fr"
    RECHERCHE_URL = "/vaccination-covid-19/france?"
    PARAMETRES = "ref_visit_motive_ids[]=6970&ref_visit_motive_ids[]=7005&ref_visit_motive_ids[]=7107"

    DOCTOLIB_SLOT_LIMIT = 50

    DOCTOLIB_HEADERS = {
        'X-Covid-Tracker-Key': os.environ.get('DOCTOLIB_API_KEY', ''),
    }

    DEFAULT_CLIENT: httpx.Client

    if os.getenv('WITH_TOR', 'no') == 'yes':
        session = requests.Session()
        session.proxies = {  # type: ignore
            'http': 'socks5://127.0.0.1:9050',
            'https': 'socks5://127.0.0.1:9050',
        }
        DEFAULT_CLIENT = session  # type: ignore
    else:
        DEFAULT_CLIENT = httpx.Client()

    page = 1
    liste_centres = []

    centres = True

    while centres and page <= max_page:

        url_recherche = BASE_URL + RECHERCHE_URL + "page=" + str(page) + "&" + PARAMETRES

        response = DEFAULT_CLIENT.get(url_recherche, headers=DOCTOLIB_HEADERS)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, "html.parser")

        centres = soup.find_all("div", {"class": "dl-search-result"})

        for _centre in centres:

            centre = {}

            centre['gid'] = _centre.get('id')[14:]

            nom = _centre.select_one(".dl-search-result-name").getText()
            centre['nom'] = nom

            rdv_site_web = BASE_URL + _centre.select_one('a[data-analytics-event-action="bookAppointmentButton"]')['href']
            centre['rdv_site_web'] = rdv_site_web


            adresse = _centre.select_one('.dl-text.dl-text-body.dl-text-s').getText().split(' ')
            centre["com_insee"] = cp_to_insee(recherche_cp(adresse))

            yield centre

        print("page", page)
        page+=1
