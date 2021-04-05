import json
import logging

import requests
from datetime import datetime, timedelta
from dateutil.parser import isoparse
from pytz import timezone
from bs4 import BeautifulSoup

DEBUG = True
BASE_AVAILIBILITY_URL = "https://www.maiia.com/api/pat-public/availability-closests"

session = requests.Session()
logger = logging.getLogger('scraper')

def fetch_slots(rdv_site_web, start_date):
    response = session.get(rdv_site_web)
    soup = BeautifulSoup(response.text, 'html.parser')
    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        logger.error(f"Requête pour {rdv_site_web} a levé une erreur : {e}")
        return None

    rdv_form = soup.find(id="__NEXT_DATA__")
    if rdv_form:
        return get_slots_from(rdv_form, rdv_site_web, start_date)

    return None


def get_slots_from(rdv_form, rdv_url, start_date):
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

    availability = get_any_availibility_from(center_id, start_date)
    if availability["availabilityCount"] == 0:
        return None

    if "firstPhysicalStartDateTime" in availability:
        dt = isoparse(availability['firstPhysicalStartDateTime'])
        dt = dt + dt.replace(tzinfo=timezone('CET')).utcoffset()
        dt = dt.isoformat()
        return dt

    # Ne sachant pas si 'firstPhysicalStartDateTime' est un attribut par défault dans
    # la réponse, je préfère faire des tests sur l'existence des attributs
    if "closestPhysicalAvailability" in availability and "startDateTime" in availability["closestPhysicalAvailability"]:
        dt = isoparse(availability['closestPhysicalAvailability']["startDateTime"])
        dt = dt + dt.replace(tzinfo=timezone('CET')).utcoffset()
        dt = dt.isoformat()
        return dt


    return None


def get_any_availibility_from(center_id, start_date):
    request_params = {
        "date_str": start_date.isoformat(),
        "centerId": center_id,
        "limit": 200,
        "page": 0,
    }

    availability = session.get(BASE_AVAILIBILITY_URL, params=request_params)
    return availability.json()
