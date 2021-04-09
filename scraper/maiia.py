import json
import logging

import requests
from datetime import datetime, timedelta
from dateutil.parser import isoparse
from bs4 import BeautifulSoup

from scraper.pattern.scraper_request import ScraperRequest

BASE_AVAILIBILITY_URL = "https://www.maiia.com/api/pat-public/availability-closests"
MAIIA_DAY_LIMIT = 50
MAIIA_LIMIT = 10000

session = requests.Session()
logger = logging.getLogger('scraper')


def get_availability_count(center_id, request: ScraperRequest):
    now = datetime.now()
    start_date = datetime.strftime(now, '%Y-%m-%dT%H:%M:%S.%f%zZ')
    end_date = (now + timedelta(days=MAIIA_DAY_LIMIT)).strftime('%Y-%m-%dT%H:%M:%S.%f%zZ')

    url = f'https://www.maiia.com/api/pat-public/availabilities?centerId={center_id}&from={start_date}&to={end_date}&page=0&limit={MAIIA_LIMIT}'
    req = session.get(url)
    req.raise_for_status()
    data = req.json()
    if not data.get('total'):
        return 0
    return int(data.get('total', 0))


def fetch_slots(request: ScraperRequest):
    response = session.get(request.get_url())
    soup = BeautifulSoup(response.text, 'html.parser')
    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        logger.error(f"Requête pour {request.get_url()} a levé une erreur : {e}")
        return None

    rdv_form = soup.find(id="__NEXT_DATA__")
    if rdv_form:
        return get_slots_from(rdv_form, request)

    return None


def get_slots_from(rdv_form, request: ScraperRequest):
    json_form = json.loads(rdv_form.contents[0])

    rdv_form_attributes = ['props', 'initialState', 'cards', 'item', 'center']
    tmp = json_form

    # Étant donné que l'arbre des attributs est assez cossu / profond, il est préférable
    # d'itérer et de vérifier à chaque fois que les attributs recherchés sont bien
    # présents dans l'arbre afin de ne pas avoir d'erreurs inattendues.
    for attr in rdv_form_attributes:
        if tmp is not None and attr in tmp:
            tmp = tmp[attr]
        else:
            return None

    center_infos = tmp
    center_id = center_infos['id']

    availability = get_any_availibility_from(center_id, request.get_start_date())
    if not availability or availability["availabilityCount"] == 0:
        return None

    # Update availability count
    availability_count = get_availability_count(center_id, request)
    request.update_appointment_count(availability_count)
    if "firstPhysicalStartDateTime" in availability:
        dt = isoparse(availability['firstPhysicalStartDateTime'])
        dt = dt + timedelta(hours=2)
        dt = dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        return dt

    # Ne sachant pas si 'firstPhysicalStartDateTime' est un attribut par défault dans
    # la réponse, je préfère faire des tests sur l'existence des attributs
    if (
            "closestPhysicalAvailability" in availability and
            "startDateTime" in availability["closestPhysicalAvailability"]
    ):
        dt = isoparse(availability['closestPhysicalAvailability']["startDateTime"])
        dt = dt + timedelta(hours=2)
        dt = dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        return dt

    return None


def get_any_availibility_from(center_id, start_date):
    start_date = datetime.strptime(start_date, '%Y-%m-%d')
    start_date = start_date.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    request_params = {
        "date_str": start_date,
        "centerId": center_id,
        "limit": 200,
        "page": 0,
    }

    availability = session.get(BASE_AVAILIBILITY_URL, params=request_params)
    return availability.json()
