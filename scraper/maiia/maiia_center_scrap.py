import httpx
import json
import logging

from datetime import datetime, timedelta
from dateutil.parser import isoparse
from pathlib import Path
from utils.vmd_utils import departementUtils, format_phone_number
from .maiia_utils import get_paged, MAIIA_LIMIT

timeout = httpx.Timeout(30.0, connect=30.0)
DEFAULT_CLIENT = httpx.Client(timeout=timeout)
logger = logging.getLogger('scraper')
MAIIA_URL = 'https://www.maiia.com'
MAIIA_DAY_LIMIT = 50
CENTER_TYPES = ['centre-de-vaccination',
                'pharmacie',
                'centre-hospitalier-(ch)']


def get_centers(speciality: str) -> list:
    result = get_paged(
        f'{MAIIA_URL}/api/pat-public/hcd?distanceMax=10000&AllVaccinationPlaces=true&speciality.shortName={speciality}', limit=50, client=DEFAULT_CLIENT)
    if 'items' not in result:
        return []
    return result['items']


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
            csv['phone_number'] = format_phone_number(center['publicInformation']['officeInformation'].get('phoneNumber', ''))
            if 'openingSchedules' in center['publicInformation']['officeInformation']:
                csv['business_hours'] = maiia_schedule_to_business_hours(
                    center['publicInformation']['officeInformation']['openingSchedules'])
    return csv


def main():
    centers = list()
    centers_ids = list()
    logger.info('Starting Maiia centers download')

    for speciality in CENTER_TYPES:
        logger.info(f'Fetching speciality {speciality}')
        result = get_centers(speciality)
        all_centers = list()
        for center in result:
            if center.get('type') != "CENTER":
                continue
            has_vaccinne_reason = False
            for consultation_reason in center['consultationReasons']:
                if 'injectionType' in consultation_reason and consultation_reason['injectionType'] in ['FIRST', 'SECOND']:
                    has_vaccinne_reason = True
            if has_vaccinne_reason:
                if center['center']['id'] in centers_ids:
                    continue
                centers.append(maiia_center_to_csv(center['center'], center))
                centers_ids.append(center['center']['id'])
            for child_center in center['center']['childCenters']:
                if child_center['speciality']['code'] == 'VAC01' and 'url' in child_center and child_center['id'] not in centers_ids:
                    centers.append(maiia_center_to_csv(child_center, center))
                    centers_ids.append(child_center['id'])

    output_path = Path('data', 'output', 'maiia_centers.json')
    with open(output_path, 'w', encoding='utf8') as f:
        json.dump(centers, f, indent=2)
    logger.info(f'Saved {len(centers)} centers to {output_path}')
    return


if __name__ == "__main__":
    main()
