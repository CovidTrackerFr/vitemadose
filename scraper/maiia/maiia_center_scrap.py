import httpx
import json
import logging

from datetime import datetime, timedelta
from dateutil.parser import isoparse
from pathlib import Path

from .maiia import get_paged

timeout = httpx.Timeout(30.0, connect=30.0)
DEFAULT_CLIENT = httpx.Client(timeout=timeout)
logger = logging.getLogger('scraper')
MAIIA_URL = 'https://www.maiia.com'
MAIIA_DAY_LIMIT = 50
MAIIA_SPECIALITIES = ['centre-de-vaccination',
                      #'vaccinateur', 
                      'pharmacie', 
                      'centre-hospitalier-(ch)']

def get_centers(speciality: str) -> list:
    result = get_paged(
        f'{MAIIA_URL}/api/pat-public/hcd?distanceMax=10000&AllVaccinationPlaces=true&speciality.shortName={speciality}', limit=50, client=DEFAULT_CLIENT)
    if 'items' not in result:
        return []
    return result['items']


def main():
    #get_paged(f'https://www.maiia.com/api/pat-public/hcd?distanceMax=10000&AllVaccinationPlaces=true', limit=50, client=DEFAULT_CLIENT)
    centers = list()
    centers_ids = list()
    logger.info('Starting Maiia centers download')

    for speciality in MAIIA_SPECIALITIES:
        logger.info(f'Checking speciality {speciality}')
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
                    logger.warning(f'center_id {center["center"]["id"]} ({center["center"]["name"]}) already in result')
                    continue
                centers.append(center)
                centers_ids.append(center['center']['id'])
                print(center['center']['url'])

    output_path = Path('data', 'output', 'maiia_centers.json')
    with open(output_path, 'w', encoding='utf8') as f:
        json.dump(centers, f, indent=4)
    logger.info(f'Saved {len(centers)} centers to {output_path}')
    return



    centers_count = 0
    centers_availabilities = 0
    good_reasons = 0
    good_centers = 0
    for center in centers:
        centers_count += 1
        reasons_count, any_availability = check_center(center, client=DEFAULT_CLIENT)
        good_reasons += reasons_count
        if reasons_count > 0:
            good_centers += 1
        if any_availability:
            centers_availabilities += 1
    logger.info(f'Found {good_centers}/{centers_count} centers, {good_reasons} good reasons and {centers_availabilities} availabilities')
    
    #with open(Path('data', 'output', 'consultationReasons.json'), 'w', encoding='utf8') as f:
    #    json.dump(consultationReasons, f)


if __name__ == "__main__":
    main()
