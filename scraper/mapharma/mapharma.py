import os

import httpx
from httpx import TimeoutException
import json
import logging

from datetime import date, datetime, timedelta
from pytz import timezone
from urllib.parse import parse_qs
from bs4 import BeautifulSoup
from pathlib import Path
from urllib import parse

from scraper.pattern.scraper_request import ScraperRequest
from scraper.pattern.scraper_result import DRUG_STORE
from utils.vmd_utils import departementUtils

MAPHARMA_HEADERS = {
    'User-Agent': os.environ.get('MAPHARMA_API_KEY', ''),
}

timeout = httpx.Timeout(30.0, connect=30.0)
DEFAULT_CLIENT = httpx.Client(timeout=timeout, headers=MAPHARMA_HEADERS)
logger = logging.getLogger('scraper')

campagnes_valides = []
campagnes_inconnues = []
opendata = []


def campagne_to_centre(pharmacy: dict, campagne: dict) -> dict() :
    insee = departementUtils.cp_to_insee(pharmacy.get('code_postal'))
    departement = departementUtils.to_departement_number(insee)
    centre = dict()
    centre['nom'] = pharmacy.get('nom')
    centre['type'] = DRUG_STORE
    centre['long_coor1'] = pharmacy.get('longitude')
    centre['lat_coor1'] = pharmacy.get('latitude')
    centre['com_nom'] = pharmacy.get('ville')
    adr_voie = pharmacy.get('adresse')
    adr_cp = pharmacy.get('code_postal')
    adr_nom = pharmacy.get('ville')
    centre['address'] = f'{adr_voie}, {adr_cp} {adr_nom}'
    business_hours = dict()
    horaires = pharmacy.get('horaires')
    days = ['lundi', 'mardi', 'mercredi',
            'jeudi', 'vendredi', 'samedi', 'dimanche']
    for day in days:
        for line in horaires.splitlines():
            if day not in line:
                continue
            business_hours[day] = line.replace(f'{day}: ', '')
    centre['business_hours'] = business_hours
    centre['phone_number'] = pharmacy.get('telephone')
    centre['rdv_site_web'] = campagne.get('url')
    centre['com_insee'] = departementUtils.cp_to_insee(pharmacy.get('code_postal'))
    centre['gid'] = campagne.get('url').encode('utf8').hex()[40:][:8]
    centre['internal_id'] = campagne.get('url').encode('utf8').hex()[40:][:8]
    centre['vaccine_type'] = 'AstraZeneca'
    return centre


def get_mapharma_opendata(client: httpx.Client = DEFAULT_CLIENT) -> dict:
    base_url = 'https://mapharma.net/opendata/rdv'
    result = dict()
    try:
        request = client.get(base_url, headers=MAPHARMA_HEADERS)
        request.raise_for_status()
        return request.json()
        return 
    except httpx.HTTPStatusError as hex:
        logger.warning(f'{base_url} returned error {hex.response.status_code}')
    try:
        with open(Path('data', 'output', 'mapharma_open_data.json'), 'r', encoding='utf8') as f:
            result = json.load(f)
    except IOError as ioex:
        logger.warning('Reading mapharma_open_data.json returned error {ioex}')
    return result


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
    slot_count = 0
    for date, day_slots in slots.items():
        if 'first' not in date:
            for day_slot in day_slots:
                time = day_slot['time']
                timestamp = datetime.strptime(
                    f'{date} {time}', '%Y-%m-%d %H:%M')
                slot_count += day_slot['places_dispo']
                if first_availability is None or timestamp < first_availability:
                    first_availability = timestamp
    return first_availability, slot_count


def fetch_slots(request: ScraperRequest, client: httpx.Client = DEFAULT_CLIENT):
    url = request.get_url()
    # on récupère les paramètres c (id_campagne) & l (id_type)
    params = dict(parse.parse_qsl(parse.urlsplit(url).query))
    id_campagne = params.get('c')
    id_type = params.get('l')
    day_slots = {}
    # l'api ne renvoie que 7 jours, on parse un peu plus loin dans le temps
    start_date = date.fromisoformat(request.get_start_date())
    for delta in range(0, 30, 6):
        new_date = start_date + timedelta(days=delta)
        slots = get_slots(id_campagne, id_type, new_date.isoformat(), client)
        for day, day_slot in slots.items():
            if day in day_slots:
                continue
            day_slots[day] = day_slot
    if not day_slots:
        return
    day_slots.pop('first', None)
    day_slots.pop('first_text', None)
    first_availability, slot_count = parse_slots(day_slots)
    request.update_appointment_count(slot_count)
    request.update_practitioner_type(DRUG_STORE)
    request.update_internal_id(url.encode('utf8').hex()[40:][:8])
    request.add_vaccine_type('AstraZeneca')
    if first_availability is None:
        return None
    return first_availability.isoformat()

def is_campagne_valid(campagne: dict) -> bool:
    global campagnes_inconnues
    global campagnes_valides
    if not campagne.get('url'):
        return False
    if not campagnes_valides:
        # on charge la liste des campagnes valides (vaccination)
        with open(Path('data', 'input', 'mapharma_campagnes_valides.json'), 'r', encoding='utf8') as f:
            campagnes_valides = json.load(f)
    if not campagnes_inconnues:
        # on charge la liste des campagnes non valides (tests, ...)
        with open(Path('data', 'output', 'mapharma_campagnes_inconnues.json'), 'r', encoding='utf8') as f:
            campagnes_inconnues = json.load(f)
    for campagne_valide in campagnes_valides:
        if campagne.get('url') == campagne_valide.get('url'):
            return True
    # la campagne n'existe pas dans la liste des valides, on l'ajoute aux inconnues
    for campagne_inconnue in campagnes_inconnues:
        if campagne.get('url') == campagne_inconnue.get('url'):
            # on a trouvé la campagne inconnue dans la liste
            # pas la peine de l'ajouter
            return False
    campagnes_inconnues.append(campagne)
    return False


def centre_iterator():
    global opendata
    global campagnes_inconnues
    campagnes = []
    opendata = get_mapharma_opendata()
    if not opendata:
        logger.error('Mapharma unable to get centre list')
        return
    # on sauvegarde le payload json reçu si jamais panne du endpoint
    with open(Path('data', 'output', 'mapharma_open_data.json'), 'w', encoding='utf8') as f:
        json.dump(opendata, f, indent=2)
    for pharmacy in opendata:
        for campagne in pharmacy.get('campagnes'):
            if not is_campagne_valid(campagne):
                continue
            centre = campagne_to_centre(pharmacy, campagne)
            yield centre
    # on sauvegarde la liste des campagnes inconnues pour review
    with open(Path('data', 'output', 'mapharma_campagnes_inconnues.json'), 'w', encoding='utf8') as f:
        json.dump(campagnes_inconnues, f, indent=2)
