import logging

import httpx
from httpx import TimeoutException
import json
from datetime import datetime, timedelta
from pytz import timezone

logger = logging.getLogger('scraper')

timeout = httpx.Timeout(15.0, connect=15.0)
session = httpx.Client(timeout=timeout)
insee = {}


# get all slugs
def search():
    base_url = 'https://api.ordoclic.fr/v1/public/search'
    # payload = {'page': '1', 'per_page': '10000', 'in.isCovidVaccineSupported': 'true', 'in.isPublicProfile': 'true' }
    payload = {'page': '1', 'per_page': '10000', 'in.isPublicProfile': 'true'}
    r = session.get(base_url, params=payload)
    r.raise_for_status()
    return r.json()


def getReasons(entityId):
    base_url = f'https://api.ordoclic.fr/v1/solar/entities/{entityId}/reasons'
    r = session.get(base_url)
    r.raise_for_status()
    return r.json()


def getSlots(entityId, medicalStaffId, reasonId, start_date, end_date):
    base_url = 'https://api.ordoclic.fr/v1/solar/slots/availableSlots'
    payload = {"entityId": entityId,
               "medicalStaffId": medicalStaffId,
               "reasonId": reasonId,
               "dateEnd": f"{end_date}T00:00:00.000Z",
               "dateStart": f"{start_date}T23:59:59.000Z"}
    headers = {'Content-type': 'application/json', 'Accept': 'text/plain'}
    r = session.post(base_url, data=json.dumps(payload), headers=headers)
    r.raise_for_status()
    return r.json()


def getProfile(rdv_site_web):
    slug = rdv_site_web.rsplit('/', 1)[-1]
    prof = rdv_site_web.rsplit('/', 2)[-2]
    if prof in ['pharmacien', 'medecin']:
        base_url = f'https://api.ordoclic.fr/v1/professionals/profile/{slug}'
    else:
        base_url = f'https://api.ordoclic.fr/v1/public/entities/profile/{slug}'
    r = session.get(base_url)
    r.raise_for_status()
    return r.json()


def parse_ordoclic_slots(availability_data):
    first_availability = None
    if not availability_data:
        return None
    if 'nextAvailableSlotDate' in availability_data:
        nextAvailableSlotDate = availability_data.get('nextAvailableSlotDate', None)
        if nextAvailableSlotDate != None:
            first_availability = datetime.strptime(nextAvailableSlotDate, '%Y-%m-%dT%H:%M:%S%z')
            first_availability += first_availability.replace(tzinfo=timezone('CET')).utcoffset()
            return first_availability

    availabilities = availability_data.get('slots', None)
    if availabilities is None:
        return None
    for slot in availabilities:
        timeStart = slot.get('timeStart', None)
        if not timeStart:
            continue
        date = datetime.strptime(timeStart, '%Y-%m-%dT%H:%M:%S%z')
        if 'timeStartUtcOffset' in slot:
            timeStartUtcOffset = slot["timeStartUtcOffset"]
            date += timedelta(minutes=timeStartUtcOffset)
        if first_availability is None or date < first_availability:
            first_availability = date
    return first_availability


def fetch_slots(rdv_site_web, start_date):
    first_availability = None
    profile = getProfile(rdv_site_web)
    slug = profile["profileSlug"]
    entityId = profile["entityId"]
    for professional in profile["publicProfessionals"]:
        medicalStaffId = professional["id"]
        name = professional["fullName"]
        zip = professional["zip"]
        reasons = getReasons(entityId)
        # reasonTypeId = 4 -> 1er Vaccin
        for reason in reasons["reasons"]:
            if reason["reasonTypeId"] == 4 and reason["canBookOnline"] == True:
                reasonId = reason["id"]
                date_obj = datetime.strptime(start_date, '%Y-%m-%d')
                end_date = (date_obj + timedelta(days=6)).strftime('%Y-%m-%d')
                slots = getSlots(entityId, medicalStaffId, reasonId, start_date, end_date)
                date = parse_ordoclic_slots(slots)
                if date is None:
                    continue
                if first_availability is None or date < first_availability:
                    first_availability = date
    if first_availability == None:
        return None
    return first_availability.isoformat()


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


def centre_iterator():
    items = search()
    for item in items["items"]:
        # plusieur types possibles (pharmacie, maison mediacle, pharmacien, medecin, ...), pour l'instant on filtre juste les pharmacies
        if 'type' in item:
            t = item.get("type")
            if t == "Pharmacie":
                centre = {}
                slug = item["publicProfile"]["slug"]
                centre["gid"] = item["id"][:8]
                centre["rdv_site_web"] = f"https://app.ordoclic.fr/app/pharmacie/{slug}"
                centre["com_insee"] = cp_to_insee(item["location"]["zip"])
                centre["nom"] = item.get("name")
                yield centre
