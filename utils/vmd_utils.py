import re
import csv
import json
import logging
from typing import List
from urllib.parse import urlparse, urlencode, urlunparse, parse_qs, unquote
import datetime as dt
import pytz
import requests

import time
from datetime import date, timedelta, datetime

from pathlib import Path
from unidecode import unidecode

RESERVED_CENTERS = [
    'réservé',
    'reserve',
    'professionnel'
]


def load_insee() -> dict:
    with open("data/input/codepostal_to_insee.json") as json_file:
        return json.load(json_file)


def load_cedex_to_insee() -> dict:
    with open("data/input/cedex_to_insee.json") as json_file:
        return json.load(json_file)


logger = logging.getLogger('scraper')
insee = load_insee()
cedex_to_insee = load_cedex_to_insee()


def is_reserved_center(center):
    if not center:
        return False
    name = center.nom.lower().strip()
    for reserved_names in RESERVED_CENTERS:
        if reserved_names in name:
            return True
    return False


def urlify(s):
    s = re.sub(r"[^\w\s\-]", '', s)
    s = re.sub(r"\s+", '-', s).lower()
    return unidecode(s)


class departementUtils:

    @staticmethod
    def import_departements() -> List[str]:
        """
                Renvoie la liste des codes départements.

                >>> departements = import_departements()
                >>> len(departements)
                101
                >>> departements[:3]
                ['01', '02', '03']
                >>> departements[83]
                '83'
                >>> departements.index('2A')
                28
                >>> sorted(departements) == departements
                True
                """
        with open("data/input/departements-france.csv", newline="\n") as csvfile:
            reader = csv.DictReader(csvfile)
            return [str(row["code_departement"]) for row in reader]

    @staticmethod
    def to_departement_number(insee_code: str) -> str:
        """
                Renvoie le numéro de département correspondant au code INSEE d'une commune.

                Le code INSEE est un code à 5 chiffres, qui est typiquement différent du code postal,
                mais qui commence (en général) aussi par les 2 chiffres du département.

                >>> to_departement_number('59350')  # Lille
                '59'
                >>> to_departement_number('75106')  # Paris 6e arr
                '75'
                >>> to_departement_number('97701')  # Saint-Barthélémy
                '971'
                """
        if len(insee_code) == 4:
            # Quand le CSV des centres de vaccinations est édité avec un tableur comme Excel,
            # il est possible que le 1er zéro soit retiré si la colonne est interprétée comme
            # un nombre (par ex 02401 devient 2401, mais on veut 02401 au complet).
            insee_code = insee_code.zfill(5)

        if len(insee_code) != 5:
            raise ValueError(f'Code INSEE non-valide : {insee_code}')

        with open("data/input/insee_to_codepostal_and_code_departement.json") as json_file:
            insee_to_code_departement_table = json.load(json_file)

        if insee_code in insee_to_code_departement_table:
            return insee_to_code_departement_table[insee_code]["departement"]

        else:
            raise ValueError(
                f'Code INSEE absent de la base des codes INSEE : {insee_code}')

    @staticmethod
    def get_city(address: str) -> str:
        """
        Récupère la ville depuis l'adresse complète
        >>> get_city("2 avenue de la République, 75005 PARIS")
        'PARIS'
        """
        if(search := re.search(r'(?<=\s\d{5}\s)(?P<com_nom>.*?)\s*$', address)):
            return search.groupdict().get('com_nom')
        return None

    @staticmethod
    def cp_to_insee(cp: str) -> str:
        # Split for when when CP is like 'XXXX CEDEX'
        cp = format_cp(cp)
        if cp in insee:
            return insee[cp]["insee"]
        elif cp in cedex_to_insee:
            cedex = cp
            return cedex_to_insee[cedex]["insee"]
        else:
            logger.warning(f'Unable to translate cp >{cp}< to insee')
            return cp


def format_cp(cp: str) -> str:
    formatted_cp = str(cp).strip().split()[0]
    if len(formatted_cp) == 4:
        return f"0{formatted_cp}"
    return formatted_cp

def format_phone_number(_phone_number: str) -> str:
    phone_number = _phone_number
    if not phone_number:
        return ""

    phone_number = phone_number.replace(" ", "")
    phone_number = phone_number.replace(".", "")

    if not phone_number[0] == "+":
        if phone_number[0] == "0":
            phone_number = "+33" + phone_number[1:]
        else:
            phone_number = "+33" + phone_number

    return phone_number


def fix_scrap_urls(url):
    url = unquote(url.strip())

    # Fix Keldoc
    if url.startswith("https://www.keldoc.com/"):
        url = url.replace("https://www.keldoc.com/",
                          "https://vaccination-covid.keldoc.com/")
    # Clean Doctolib
    if url.startswith('https://partners.doctolib.fr') or url.startswith('https://www.doctolib.fr'):
        if '?speciality_id' in url:
            url = "&".join(url.rsplit("?", url.count("?") - 1))
        u = urlparse(url)
        query = parse_qs(u.query, keep_blank_values=True)
        to_remove = []
        for query_name in query:
            if query_name.startswith('highlight') or query_name == 'enable_cookies_consent':
                to_remove.append(query_name)
        [query.pop(rm, None) for rm in to_remove]
        query.pop('speciality_id', None)
        u = u._replace(query=urlencode(query, True))
        url = urlunparse(u)
    return url


def get_last_scans(centres):
    url ='https://vitemadose.gitlab.io/vitemadose/info_centres.json'
    last_scans = {}
    liste_centres = []

    for centre in centres:
        liste_centres.append(centre)

    try:
        response = requests.get(url)
        response.raise_for_status()
        info_centres = response.json()

    except Exception as e:
        logger.warning(f"Impossible de récupérer le fichier info_centres: {e}")
        info_centres = {}

    for last_centres in info_centres.values():
        for centre in last_centres["centres_disponibles"] + last_centres["centres_indisponibles"]:
            if "last_scan_with_availabilities" in centre:
                last_scans[centre["url"]]  = centre["last_scan_with_availabilities"]

    for centre in liste_centres:
        if not centre.prochain_rdv:
            if centre.url in last_scans:
                centre.last_scan_with_availabilities = last_scans[centre.url] 
        else:
            centre.last_scan_with_availabilities = dt.datetime.now(tz=pytz.timezone('Europe/Paris')).isoformat()

    return liste_centres

def append_date_days(mydate: str, days: int):
    if not mydate or not days:
        return
    mydate = date.fromisoformat(mydate)
    newdate = mydate + timedelta(days = days)
    return newdate.isoformat()
