import json
import logging
from datetime import datetime, timedelta

import httpx
from pytz import timezone

from scraper.pattern.scraper_request import ScraperRequest
from scraper.pattern.scraper_result import DRUG_STORE
from utils.vmd_utils import departementUtils
from scraper.profiler import Profiling



logger = logging.getLogger('scraper')

timeout = httpx.Timeout(15.0, connect=15.0)
DEFAULT_CLIENT = httpx.Client(timeout=timeout)
insee = {}


# get all slugs
def search(client: httpx.Client = DEFAULT_CLIENT):
    base_url = 'https://api.ordoclic.fr/v1/public/search'
    # toutes les pharmacies
    # payload = {'page': '1', 'per_page': '10000', 'in.isPublicProfile': 'true'}
    # toutes les pharmacies faisant des vaccins
    # payload = {'page': '1', 'per_page': '10000', 'in.isPublicProfile': 'true', 'in.isCovidVaccineSupported': 'true'}
    # toutes les pharmacies faisant des vaccins avec des calendriers en ligne
    payload = {'page': '1', 'per_page': '10000', 'in.isPublicProfile': 'true', 'in.isCovidVaccineSupported': 'true', 'in.covidOnlineBookingAvailabilities.covidInjection1': 'true' }
    r = client.get(base_url, params=payload)
    r.raise_for_status()
    return r.json()


def getReasons(entityId, client: httpx.Client = DEFAULT_CLIENT):
    base_url = f'https://api.ordoclic.fr/v1/solar/entities/{entityId}/reasons'
    r = client.get(base_url)
    r.raise_for_status()
    return r.json()


def getSlots(entityId, medicalStaffId, reasonId, start_date, end_date, client: httpx.Client = DEFAULT_CLIENT):
    base_url = 'https://api.ordoclic.fr/v1/solar/slots/availableSlots'
    payload = {"entityId": entityId,
               "medicalStaffId": medicalStaffId,
               "reasonId": reasonId,
               "dateEnd": f"{end_date}T00:00:00.000Z",
               "dateStart": f"{start_date}T23:59:59.000Z"}
    headers = {'Content-type': 'application/json', 'Accept': 'text/plain'}
    r = client.post(base_url, data=json.dumps(payload), headers=headers)
    r.raise_for_status()
    return r.json()


def getProfile(request: ScraperRequest, client: httpx.Client = DEFAULT_CLIENT):
    slug = request.get_url().rsplit('/', 1)[-1]
    prof = request.get_url().rsplit('/', 2)[-2]
    if prof in ['pharmacien', 'medecin']:
        base_url = f'https://api.ordoclic.fr/v1/professionals/profile/{slug}'
    else:
        base_url = f'https://api.ordoclic.fr/v1/public/entities/profile/{slug}'
    r = client.get(base_url)
    r.raise_for_status()
    return r.json()


def parse_ordoclic_slots(request: ScraperRequest, availability_data):
    first_availability = None
    if not availability_data:
        return None
    availabilities = availability_data.get('slots', None)
    availability_count = 0
    if type(availabilities) is list:
        availability_count = len(availabilities)
    request.update_appointment_count(availability_count)
    if 'nextAvailableSlotDate' in availability_data:
        nextAvailableSlotDate = availability_data.get('nextAvailableSlotDate', None)
        if nextAvailableSlotDate is not None:
            first_availability = datetime.strptime(nextAvailableSlotDate, '%Y-%m-%dT%H:%M:%S%z')
            first_availability += first_availability.replace(tzinfo=timezone('CET')).utcoffset()
            return first_availability

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


@Profiling.measure('ordoclic_slot')
def fetch_slots(request: ScraperRequest, client: httpx.Client = DEFAULT_CLIENT):
    first_availability = None
    profile = getProfile(request)
    slug = profile["profileSlug"]
    entityId = profile["entityId"]
    attributes = profile.get('attributeValues')
    for settings in attributes:
        if settings['label'] == 'booking_settings' and settings['value'].get('option', 'any') == 'any':
            request.set_appointments_only_by_phone(True)
            return None
    for professional in profile["publicProfessionals"]:
        medicalStaffId = professional["id"]
        name = professional["fullName"]
        zip = professional["zip"]
        reasons = getReasons(entityId)
        # reasonTypeId = 4 -> 1er Vaccin
        for reason in reasons["reasons"]:
            if reason["reasonTypeId"] == 4 and reason["canBookOnline"] is True:
                reasonId = reason["id"]
                date_obj = datetime.strptime(request.get_start_date(), '%Y-%m-%d')
                end_date = (date_obj + timedelta(days=50)).strftime('%Y-%m-%d')
                slots = getSlots(entityId, medicalStaffId, reasonId, request.get_start_date(), end_date, client)
                date = parse_ordoclic_slots(request, slots)
                if date is None:
                    continue
                if first_availability is None or date < first_availability:
                    first_availability = date
    if first_availability is None:
        return None
    return first_availability.isoformat()


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
                centre["com_insee"] = departementUtils.cp_to_insee(item["location"]["zip"])
                centre["nom"] = item.get("name")
                centre["phone_number"] = item.get("phone")
                centre["location"] = item.get("location")
                centre["iterator"] = "ordoclic"
                centre["type"] = DRUG_STORE
                yield centre
