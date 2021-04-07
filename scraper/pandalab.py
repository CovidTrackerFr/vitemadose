import httpx
from httpx import TimeoutException
import json
import logging
import urllib.parse as urlparse

from datetime import datetime, timedelta
from pytz import timezone
from urllib.parse import parse_qs

timeout = httpx.Timeout(30.0, connect=30.0)
session = httpx.Client(timeout=timeout)
logger = logging.getLogger('scraper')

geo = {}
items = {}
insee = {}

def getSchedules(pharmacyId, practitionerId, reasonId):
    base_url = f"https://diapatient-api.diatelic.net/public/v1/appointment/schedule/{pharmacyId}"
    payload = {"serviceProvider": "ICT", 
               "practitionerId": practitionerId, 
               "reasonId": reasonId}
    try:
        headers = {'Content-type': 'application/json', 'Accept': '*/*'}
        r = session.post(base_url, data=json.dumps(payload), headers=headers)
        r.raise_for_status()
        return(r.json())
    except httpx.HTTPStatusError as hex:
        return([])

def getReasons(pharmacyId):
    base_url = f"https://diapatient-api.diatelic.net/public/v1/appointment/ict/practitioner/{pharmacyId}/reasons"
    try:
        r = session.get(base_url)
        r.raise_for_status()
        return(r.json())
    except httpx.HTTPStatusError as hex:
        return([])

def getPractitionerId(finessGeo):
    base_url = f"https://diapatient-api.diatelic.net/public/v1/appointment/ict/pharmacy/{finessGeo}"
    r = session.get(base_url)
    r.raise_for_status()
    return(r.json())

def cp_to_insee(cp):
    insee_com = cp # si jamais on ne trouve pas de correspondance...
    # on charge la table de correspondance cp/insee, une seule fois
    global insee
    if insee == {}:
        with open("data/input/codepostal_to_insee.json") as json_file:
            insee = json.load(json_file)
    if cp in insee:
        insee_com = insee.get(cp).get("insee")
    else:
        logger.warning(f'Pandalab unable to translate cp >{cp}< to insee')
    return insee_com

def centre_iterator():
    with open("data/input/pandalab.json", "r") as json_file:
        dict_ict = json.load(json_file)
        for key in dict_ict.keys():
            ict = dict_ict[key]
            if ict.get("availability") == True: # pris de rdv en ligne possible
                centre = {}
                centre["nom"] = ict["name"]
                centre["com_insee"] = cp_to_insee(ict["address"]["zip"].strip().zfill(5))
                pharmacyId = ict.get("id")
                finessGeo = ict.get("finessGeo")
                practitionerId = getPractitionerId(finessGeo).get("id")
                reasons = getReasons(practitionerId)
                for reason in reasons:
                    reasonId = reason["id"]
                    if reason["label"] == "Première injection – Vaccin covid AstraZeneca": # on ne remonte pas les 2ndes injections
                        new_centre = centre
                        new_centre["gid"] = key
                        new_centre["rdv_site_web"] = f"https://masante.pandalab.eu/medical-team/medical-team-result-pharmacy/new/org/details/{key}?pharmacyId={pharmacyId}&practitionerId={practitionerId}&reasonId={reasonId}"
                        yield(new_centre)

def fetch_slots(rdv_site_web, start_date):
    parsed = urlparse.urlparse(rdv_site_web)
    pharmacyId = parse_qs(parsed.query)["pharmacyId"][0]
    practitionerId = parse_qs(parsed.query)["practitionerId"][0]
    reasonId = parse_qs(parsed.query)["reasonId"][0]
    schedules = getSchedules(pharmacyId, practitionerId, reasonId)
    first_slot = None
    for schedule in schedules:
        begin = datetime.strptime(schedule.get("begin"), "%Y-%m-%dT%H:%M:%S")
        if first_slot == None or first_slot > begin:
            first_slot = begin
    if first_slot == None:
        return None
    return(first_slot.isoformat())
