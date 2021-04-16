import json
import logging
import httpx

from datetime import datetime, timedelta
from dateutil.parser import isoparse
from pathlib import Path
from urllib.parse import quote

from scraper.profiler import Profiling
from scraper.pattern.scraper_request import ScraperRequest
from scraper.pattern.center_info import get_vaccine_name
from utils.vmd_utils import departementUtils

#BASE_AVAILIBILITY_URL = "https://www.maiia.com/api/pat-public/availability-closests"
MAIIA_URL = 'https://www.maiia.com'
MAIIA_DAY_LIMIT = 50
MAIIA_LIMIT = 1000
MAIIA_SPECIALITIES = ['VAC01']

timeout = httpx.Timeout(30.0, connect=30.0)
DEFAULT_CLIENT = httpx.Client(timeout=timeout)
logger = logging.getLogger('scraper')


# region utils
def get_paged(url: str, limit: MAIIA_LIMIT, client: httpx.Client = DEFAULT_CLIENT) -> dict:
    result = dict()
    result['items'] = []
    result['total'] = 0
    page = 0
    while True:
        base_url = f'{url}&limit={limit}&page={page}'
        try:
            r = client.get(base_url)
            r.raise_for_status()
        except httpx.HTTPStatusError as hex:
            logger.warning(
                f'{base_url} returned error {hex.response.status_code}')
            break
        payload = r.json()
        result['total'] = payload['total']
        if not payload['items']:
            break
        for item in payload.get('items'):
            result['items'].append(item)
        if len(result['items']) >= result['total']:
            break
        page += 1
    return result
# endregion


# region fetch
def parse_slots(slots: list) -> datetime:
    if not slots:
        return
    first_availability = None
    for slot in slots:
        start_date_time = isoparse(slot['startDateTime'])
        if first_availability == None or start_date_time < first_availability:
            first_availability = start_date_time
    return first_availability


def get_next_slot_date(center_id: str, consultation_reason_name: str, start_date: str, client: httpx.Client = DEFAULT_CLIENT) -> str:
    url = f'{MAIIA_URL}/api/pat-public/availability-closests?centerId={center_id}&consultationReasonName={consultation_reason_name}&from={start_date}'
    try:
        r = client.get(url)
        r.raise_for_status()
    except httpx.HTTPStatusError as hex:
        logger.warning(f'{url} returned error {hex.response.status_code}')
        return
    result = r.json()
    if 'firstPhysicalStartDateTime' in result:
        return result['firstPhysicalStartDateTime']
    return


def get_slots(center_id: str, consultation_reason_name: str, start_date: str, end_date: str, limit = MAIIA_LIMIT, client: httpx.Client = DEFAULT_CLIENT) -> list:
    url = f'{MAIIA_URL}/api/pat-public/availabilities?centerId={center_id}&consultationReasonName={consultation_reason_name}&from={start_date}&to={end_date}'
    availabilities = get_paged(url, limit=limit, client=client)['items']
    if not availabilities:
        next_slot_date = get_next_slot_date(
            center_id, consultation_reason_name, start_date, client=client)
        if not next_slot_date:
            return
        next_date = datetime.strptime(next_slot_date, '%Y-%m-%dT%H:%M:%S.%fZ')
        start_date = datetime.strftime(next_date, '%Y-%m-%dT%H:%M:%S.%f%zZ')
        end_date = (next_date + timedelta(days=MAIIA_DAY_LIMIT)
                    ).strftime('%Y-%m-%dT%H:%M:%S.%f%zZ')
        url = f'{MAIIA_URL}/api/pat-public/availabilities?centerId={center_id}&consultationReasonName={consultation_reason_name}&from={start_date}&to={end_date}'
        availabilities = get_paged(url, limit=100000, client=client)['items']
    if availabilities:
        return availabilities
    return


def get_reasons(center_id: str, limit = MAIIA_LIMIT, client: httpx.Client = DEFAULT_CLIENT) -> list:
    url = f'{MAIIA_URL}/api/pat-public/consultation-reason-hcd?rootCenterId={center_id}'
    result = get_paged(url, limit=limit, client=client)
    if not result['total']:
        return []
    return result['items']


def get_first_availability(center_id: str, request_date: str, reasons: dict, client: httpx.Client = DEFAULT_CLIENT) -> [datetime, int]:
    date = isoparse(request_date)
    start_date = datetime.strftime(date, '%Y-%m-%dT%H:%M:%S.%f%zZ')
    end_date = (date + timedelta(days=MAIIA_DAY_LIMIT)
                ).strftime('%Y-%m-%dT%H:%M:%S.%f%zZ')
    first_availability = None
    slots_count = 0

    for consultation_reason in reasons:
        consultation_reason_name = consultation_reason['name']
        consultation_reason_name_quote = quote(consultation_reason_name, '')
        if 'injectionType' in consultation_reason and consultation_reason['injectionType'] in ['FIRST', 'SECOND']:
            slots = get_slots(
                center_id, consultation_reason_name_quote, start_date, end_date, client=client)
            slot_availability = parse_slots(slots)
            if slot_availability == None:
                continue
            slots_count += len(slots)
            if first_availability == None or slot_availability < first_availability:
                first_availability = slot_availability

    return first_availability, slots_count


@Profiling.measure('maiia_slot')
def fetch_slots(request: ScraperRequest, client: httpx.Client = DEFAULT_CLIENT) -> str:
    url = request.get_url()
    start_date = request.get_start_date()
    if '?centerid=' not in url:
        logger.warning(f'No centerId in fetch url: {url}')
        return
    center_id = url.split('?centerid=')[1]

    reasons = reasons = get_reasons(center_id, client=client)
    if not reasons:
        return

    first_availability, slots_count = get_first_availability(
        center_id, start_date, reasons, client=client)
    if first_availability == None:
        return

    for reason in reasons:
        request.add_vaccine_type(get_vaccine_name(reason['name']))
    request.update_internal_id(center_id)
    request.update_appointment_count(slots_count)
    return first_availability.isoformat()
# endregion


# region iterator
def maiia_schedule_to_business_hours(opening_schedules) -> dict:
    business_hours = dict()
    days = {'Lundi': 'MONDAY', 'Mardi': 'TUESDAY', 'Mercredi': 'WEDNESDAY',
            'Jeudi': 'THURSDAY', 'Vendredi': 'FRIDAY', 'Samedi': 'SATURDAY', 'Dimanche': 'SUNDAY'}
    for key, value in days.items():
        schedules = opening_schedules[value]['schedules']
        creneaux = list()
        for schedule in schedules:
            creneaux.append(f'{schedule["startTime"]}-{schedule["endTime"]}')
        if creneaux:
            business_hours[key] = ' '.join(creneaux)
    return business_hours


def maiia_center_to_csv(center: dict, root_center: dict) -> dict:
    if 'url' not in center:
        logger.warning(f'url not found - {center}')
    csv = dict()
    csv['gid'] = center['id'][:8]
    csv['nom'] = center['name']
    csv['rdv_site_web'] = f'{MAIIA_URL}{center["url"]}?centerid={center["id"]}'
    if 'publicInformation' in center:
        if 'address' in center['publicInformation']:
            insee = center['publicInformation']['address'].get('inseeCode', '')
            csv['com_insee'] = center['publicInformation']['address']['inseeCode']
            if len(insee) < 5:
                zip = center['publicInformation']['address']['zipCode']
                csv['com_insee'] = departementUtils.cp_to_insee(zip)
            csv['address'] = center['publicInformation']['address']['fullAddress']
            if 'location' in center['publicInformation']['address']:
                csv['long_coor1'] = center['publicInformation']['address']['location']['coordinates'][0]
                csv['lat_coor1'] = center['publicInformation']['address']['location']['coordinates'][1]
        if 'officeInformation' in center['publicInformation']:
            csv['phone_number'] = center['publicInformation']['officeInformation'].get(
                'phoneNumber', '')
            if 'openingSchedules' in center['publicInformation']['officeInformation']:
                csv['business_hours'] = maiia_schedule_to_business_hours(
                    center['publicInformation']['officeInformation']['openingSchedules'])
    return csv


def centre_iterator():
    with open(Path('data', 'output', 'maiia_centers.json'), 'r', encoding='utf8') as f:
        centers = json.load(f)
    for center in centers:
        if center.get('type') != "CENTER":
            continue
        has_vaccinne_reason = False
        for consultation_reason in center['consultationReasons']:
            if 'injectionType' in consultation_reason and consultation_reason['injectionType'] in ['FIRST', 'SECOND']:
                has_vaccinne_reason = True
        if has_vaccinne_reason:
            yield maiia_center_to_csv(center['center'], center)
            for child_center in center['center']['childCenters']:
                if child_center['speciality']['code'] in MAIIA_SPECIALITIES and 'url' in child_center:
                    yield maiia_center_to_csv(child_center, center)
# endregion
