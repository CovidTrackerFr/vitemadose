import httpx
from httpx import TimeoutException
import json
import logging
import urllib.parse as urlparse

from datetime import datetime, timedelta
from pytz import timezone
from urllib.parse import parse_qs

from scraper.pattern.scraper_request import ScraperRequest
from scraper.pattern.scraper_result import DRUG_STORE
from utils.vmd_utils import departementUtils

timeout = httpx.Timeout(30.0, connect=30.0)
DEFAULT_CLIENT = httpx.Client(timeout=timeout)
logger = logging.getLogger('scraper')


geo = {}
items = {}
insee = {}
FILTRE_VACCINS = ['Première injection – Vaccin covid AstraZeneca']


def get_schedules(pharmacyId, practitionerId, reasonId, client: httpx.Client = DEFAULT_CLIENT):
    base_url = f"https://diapatient-api.diatelic.net/public/v1/appointment/schedule/{pharmacyId}"
    payload = {"serviceProvider": "ICT",
               "practitionerId": practitionerId,
               "reasonId": reasonId}
    try:
        headers = {'Content-type': 'application/json', 'Accept': '*/*'}
        r = client.post(base_url, data=json.dumps(payload), headers=headers)
        r.raise_for_status()
        return r.json()
    except httpx.HTTPStatusError as hex:
        logger.warning(hex)
        return []


def get_reasons(pharmacyId, client: httpx.Client = DEFAULT_CLIENT):
    base_url = f"https://diapatient-api.diatelic.net/public/v1/appointment/ict/practitioner/{pharmacyId}/reasons"
    try:
        r = client.get(base_url)
        r.raise_for_status()
        return r.json()
    except httpx.HTTPStatusError as hex:
        if hex.response.status_code == 404:
            logger.info(
                f'pharmacyId {pharmacyId} ne renvoit aucun type de rdv')
        else:
            logger.exception(hex)
        return []


def get_practitioner_id(finessGeo, client: httpx.Client = DEFAULT_CLIENT):
    base_url = f"https://diapatient-api.diatelic.net/public/v1/appointment/ict/pharmacy/{finessGeo}"
    try:
        r = client.get(base_url)
        r.raise_for_status()
        return r.json()
    except httpx.HTTPStatusError as hex:
        logger.exception(hex)
        return []


def ict_to_center(ict):
    """Mapping du payload json récupéré sur l'api pandalab vers le format de centre avec meta"""
    center = dict()
    center["nom"] = ict["name"]
    center["com_insee"] = departementUtils.cp_to_insee(ict["address"]["zip"].strip().zfill(5))
    center["phone_number"] = ict.get("phoneNumber")
    address = dict()
    address["adr_num"] = ""
    address["adr_voie"] = ict["address"]["street"]
    address["com_cp"] = ict["address"]["zip"]
    address["com_nom"] = ict["address"]["city"]
    center["address"] = address
    center["long_coor1"] = ict.get("longitude")
    center["lat_coor1"] = ict.get("latitude")
    center["iterator"] = "pandalab"
    center["type"] = DRUG_STORE
    business_hours = dict()
    schedule = ict.get("schedule")
    if "monday" in schedule:
        business_hours["Lundi"] = schedule.get("monday")
    if "tuesday" in schedule:
        business_hours["Mardi"] = schedule.get("tuesday")
    if "wednesday" in schedule:
        business_hours["Mercredi"] = schedule.get("wednesday")
    if "thursday" in schedule:
        business_hours["Jeudi"] = schedule.get("thursday")
    if "friday" in schedule:
        business_hours["Vendredi"] = schedule.get("friday")
    if "saturday" in schedule:
        business_hours["Samedi"] = schedule.get("saturday")
    if "sunday" in schedule:
        business_hours["Dimanche"] = schedule.get("sunday")
    center["business_hours"] = business_hours
    return center


def centre_iterator():
    dict_ict = {}
    with open("data/input/pandalab.json", "r") as json_file:
        dict_ict = json.load(json_file)
    for key, ict in dict_ict.items():
        if not ict.get("availability", False):
            continue
        center = ict_to_center(ict)
        pharmacyId = ict.get("id")
        finessGeo = ict.get("finessGeo")
        practitionerId = get_practitioner_id(finessGeo).get("id")
        reasons = get_reasons(practitionerId)
        for reason in reasons:
            reasonId = reason["id"]
            # on ne remonte pas les 2ndes injections ou les rdv d'autre type
            if reason["label"] not in FILTRE_VACCINS:
                continue
            new_center = center
            new_center["gid"] = key
            new_center[
                "rdv_site_web"] = f"https://masante.pandalab.eu/medical-team/medical-team-result-pharmacy/new/org/details/{key}?pharmacyId={pharmacyId}&practitionerId={practitionerId}&reasonId={reasonId}"
            yield new_center


def fetch_slots(request: ScraperRequest, client: httpx.Client = DEFAULT_CLIENT):
    parsed = urlparse.urlparse(request.get_url())
    pharmacyId = parse_qs(parsed.query)["pharmacyId"][0]
    practitionerId = parse_qs(parsed.query)["practitionerId"][0]
    reasonId = parse_qs(parsed.query)["reasonId"][0]
    schedules = get_schedules(pharmacyId, practitionerId, reasonId)
    first_slot = None
    for schedule in schedules:
        begin = datetime.strptime(schedule.get("begin"), "%Y-%m-%dT%H:%M:%S")
        if first_slot is None or first_slot > begin:
            first_slot = begin
    if first_slot is None:
        return None
    return first_slot.isoformat()
