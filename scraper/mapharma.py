import httpx
from httpx import TimeoutException
import json
import logging
import urllib.parse as urlparse

from datetime import datetime, timedelta
from pytz import timezone
from urllib.parse import parse_qs
from bs4 import BeautifulSoup

from .pattern.scraper_request import ScraperRequest
from .pattern.scraper_result import DRUG_STORE

timeout = httpx.Timeout(30.0, connect=30.0)
DEFAULT_CLIENT = httpx.Client(timeout=timeout)
logger = logging.getLogger('scraper')

insee = {}
campagnes = {}

def getName(soup):
    name = soup.find('h3').text.strip()
    return name

def getAddress(soup):
    address = soup.find('div', {'class': 'mb-1 text-muted'}).text.strip()
    return address

def getReasons(soup):
    reasons = []
    divs = soup.find_all('div', {'class': 'js-campagne-data'})
    for div in divs:
        if 'data-campagne-id' in div.attrs and div.attrs['data-campagne-id'] != '0':
            campagneId = div.attrs['data-campagne-id']
            options = div.find_all('option')
            for option in options:
                if 'value' in option.attrs and option.attrs['value'] != '0':
                    optionId = option.attrs['value']
                    optionName = option.text.strip()
                    reasons.append( { 'campagneId': campagneId, 'optionId': optionId, 'optionName': optionName })
    return reasons

def getProfile(url, client: httpx.Client = DEFAULT_CLIENT):
    profile = {}
    profile['reasons'] = []
    try:
        r = client.get(url)
        r.raise_for_status()
        soup = BeautifulSoup(r.content, 'html.parser')
        reasons = getReasons(soup)
        if reasons != []:
            profile['reasons'] = reasons
        return profile
    except httpx.HTTPStatusError:
        return profile

def getProfiles(zip, client: httpx.Client = DEFAULT_CLIENT):
    index = 0
    loop = True
    result = []
    while True:
        base_url = f"https://mapharma.net/{zip}-{index}" if index > 0 else f'https://mapharma.net/{zip}'
        try:
            r = client.get(base_url)
            r.raise_for_status()
            soup = BeautifulSoup(r.content, 'html.parser')
            reasons = getReasons(soup)
            name = getName(soup)
            address = getAddress(soup)
            payload = { 'id': index, 'url': base_url, 'zip': zip, 'id': index, 'name': name, 'address': address, 'reasons': reasons}
            result.append(payload)
            index += 1
        except httpx.HTTPStatusError:
            if index == 0:
                index = 1
            else:
                return result

def bruteForce():
    profiles = dict()
    with open("data/input/codepostal_to_insee.json", "r") as json_file:
        zips = json.load(json_file)
        for zip in zips.keys():
            for profile in getProfiles(zip):
                if zip not in profiles:
                    profiles[zip] = [] 
                profiles[zip].append(profile)
    with open("data/input/mapharma.json", "w") as json_file:
        json.dump(profiles, json_file, indent = 4)

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
        logger.warning(f'Ordoclic unable to translate cp >{cp}< to insee')
    return insee_com

def getSlots(campagneId, optionId, start_date, client: httpx.Client = DEFAULT_CLIENT):
    #logger.debug((f'campagneId: {campagneId}, optionId: {optionId}, start_date: {start_date}')
    base_url = f'https://mapharma.net/api/public/calendar/{campagneId}/{start_date}/{optionId}'
    client.headers.update({'referer': 'https://mapharma.net/'})
    r = client.get(base_url)
    r.raise_for_status()
    return r.json()

def parseSlots(slots):
    first_availability = None
    for key in slots.keys():
        if 'first' not in key:
            date = key
            day = slots[key]
            for slot in day:
                time = slot['time']
                timestamp = datetime.strptime(f'{date} {time}', '%Y-%m-%d %H:%M')
                if first_availability is None or timestamp < first_availability:
                    first_availability = timestamp
    return first_availability

def fetch_slots(request: ScraperRequest, client: httpx.Client = DEFAULT_CLIENT):
    global campagnes
    slot_counts = 0
    if campagnes == {}:
        with open('data/input/mapharma_campagnes.json') as json_file:
            campagnes = json.load(json_file)
    first_availability = None
    profile = getProfile(request.get_url())
    for reason in profile['reasons']:
        for campagne in campagnes['vaccin']:
            if campagne['campagneId'] == reason['campagneId']:
                slots = getSlots(campagne['campagneId'], campagne['optionId'], request.start_date, client)
                slot_counts += len(slots)
                first_availability = parseSlots(slots)
    request.update_appointment_count(slot_counts)
    if first_availability is None:
        return None
    return first_availability.isoformat()

def centre_iterator():
    with open("data/input/mapharma.json") as json_file:
        mapharma = json.load(json_file)
        for zip in mapharma.keys():
            for profile in mapharma[zip]:
                address = dict()
                address["adr_num"] = ""
                address["adr_voie"] = profile['address']
                address["com_cp"] = ""
                address["com_nom"] = ""
                id = profile['id']
                centre = { 'gid': f'{zip}-{id}', 'rdv_site_web': profile['url'], 'com_insee': cp_to_insee(zip), 'nom': profile['name'], "location": { "zip": zip }, "address": profile['address'] , 'iterator': 'mapharma', 'type': DRUG_STORE } 
                yield centre
