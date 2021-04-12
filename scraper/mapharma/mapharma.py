import httpx
from httpx import TimeoutException
import json
import logging
import urllib.parse as urlparse

from datetime import datetime, timedelta
from pytz import timezone
from urllib.parse import parse_qs
from bs4 import BeautifulSoup

from scraper.pattern.scraper_request import ScraperRequest
from scraper.pattern.scraper_result import DRUG_STORE
from utils.vmd_utils import departementUtils
from scraper.pattern.center_location import CenterLocation
from scraper.pattern.center_info import CenterInfo


timeout = httpx.Timeout(30.0, connect=30.0)
DEFAULT_CLIENT = httpx.Client(timeout=timeout)
logger = logging.getLogger('scraper')

insee = {}
campagnes = {}

def get_name(soup):
    name = soup.find(class_='pharma-block').find('h3').text.strip()
    return name

def get_address(soup):
    address = soup.find('div', {'class': 'mb-1 text-muted'}).text.strip()
    return address

def get_reasons(soup):
    reasons = []
    divs = soup.find_all('div', {'class': 'js-campagne-data'})
    for div in divs:
        if 'data-campagne-id' not in div.attrs or div.attrs['data-campagne-id'] == '0':
            continue
        campagneId = div.attrs['data-campagne-id']
        options = div.find_all('option')
        for option in options:
            if 'value' not in option.attrs or option.attrs['value'] == '0':
                continue
            optionId = option.attrs['value']
            optionName = option.text.strip()
            reasons.append( { 'campagneId': campagneId, 'optionId': optionId, 'optionName': optionName })
    return reasons

    
def get_profile(url: str, client: httpx.Client = DEFAULT_CLIENT):
    profile = {}
    profile['reasons'] = []
    try:
        r = client.get(url)
        r.raise_for_status()
    except httpx.HTTPStatusError:
        return profile
    soup = BeautifulSoup(r.content, 'html.parser')
    reasons = get_reasons(soup)
    if reasons != []:
        profile['reasons'] = reasons
    return profile

def get_slots(campagneId: str, optionId: str, start_date: str, client: httpx.Client = DEFAULT_CLIENT):
    base_url = f'https://mapharma.net/api/public/calendar/{campagneId}/{start_date}/{optionId}'
    client.headers.update({'referer': 'https://mapharma.net/'})
    try:
        r = client.get(base_url)
        r.raise_for_status()
    except httpx.HTTPStatusError as hex: 
        logger.warning(f'{base_url} returned error {hex.response.status_code}')
        return {}
    return r.json()

def parse_slots(slots):
    first_availability = None
    for date, day_slots in slots.items():
        if 'first' not in date:
            for day_slot in day_slots:
                time = day_slot['time']
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
    profile = get_profile(request.get_url())
    for reason in profile['reasons']:
        for campagne in campagnes['vaccin']:
            if campagne['campagneId'] == reason['campagneId']:
                day_slots = get_slots(campagne['campagneId'], campagne['optionId'], request.start_date, client)
                day_slots.pop('first', None)
                day_slots.pop('first_text', None)
                for day_slot in day_slots:
                    slot_counts += len(day_slot)
                first_availability = parse_slots(day_slots)
    request.update_appointment_count(slot_counts)
    if first_availability is None:
        return None
    return first_availability.isoformat()

def centre_iterator():
    with open("data/output/mapharma-centers.json") as json_file:
        mapharma = json.load(json_file)
        for zip in mapharma.keys():
            for profile in mapharma[zip]:
                yield(profile)
                """
                id = profile['id']
                #centre = {'gid': f'{zip}-{id}', 'rdv_site_web': profile['url'], 'com_insee': departementUtils.cp_to_insee(zip), 'nom': profile['name'], 'location': profile.get('location'), "address": profile['address'] , 'iterator': 'mapharma', 'type': DRUG_STORE} 
                #centre = profile
                centre['gid'] = f'{zip}-{id}'
                centre['rdv_site_web'] = profile.get('url')
                centre['com_insee'] = profile.get('com_insee')
                centre['nom'] = profile.get('name')
                centre['location'] = profile.get('location')
                centre['address'] = profile['address']
                centre['iterator'] = 'mapharma'
                centre['type'] = DRUG_STORE
                print(centre)
                yield centre
"""