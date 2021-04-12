import httpx
import json
import logging
import time

from multiprocessing import Pool

from bs4 import BeautifulSoup
from scraper.mapharma.mapharma import get_name, get_address, get_reasons
from utils.vmd_utils import departementUtils
from scraper.pattern.scraper_result import DRUG_STORE

timeout = httpx.Timeout(30.0, connect=30.0)
DEFAULT_CLIENT = httpx.Client(timeout=timeout)
logger = logging.getLogger('scraper')

def get_location(center, zip: str, address: str, client: httpx.Client = DEFAULT_CLIENT):
    address = address.replace("LA VARENNE SAINT HILAIRE", "SAINT-MAUR-DES-FOSSES") # La Varenne est un quartier de St Maur
    base_url = f'https://api-adresse.data.gouv.fr/search/?q={address}&postcode='
    center["com_insee"] = departementUtils.cp_to_insee(zip)#feature['properties'].get('citycode')
    try:
        r = client.get(base_url)
        r.raise_for_status()
    except httpx.HTTPStatusError:
        return center

    result = r.json()
    features = result.get('features', None)
    if features is None or len(features) == 0:
        return center
    feature = features[0]

    center["adr_num"] = feature['properties'].get('housenumber')
    center["adr_voie"] = feature['properties'].get('street')
    center["com_cp"] = feature['properties'].get('postcode')
    center["com_nom"] = feature['properties'].get('city')
    center["adr_num"] = feature['properties'].get('housenumber')
    center["long_coor1"] = feature['geometry']['coordinates'][0]
    center["lat_coor1"] = feature['geometry']['coordinates'][1]

    return center

def get_profiles(zip: str, client: httpx.Client = DEFAULT_CLIENT):
    index = 0
    result = []
    while True:
        base_url = f"https://mapharma.net/{zip}-{index}" if index > 0 else f'https://mapharma.net/{zip}'
        try:
            r = client.get(base_url)
            r.raise_for_status()
        except httpx.HTTPStatusError:
            if index > 0:
                return result
            else:
                index = 1
                continue
        soup = BeautifulSoup(r.content, 'html.parser')
        reasons = get_reasons(soup)
        name = get_name(soup)
        address = get_address(soup)
        payload = {'id': index, 'gid': f'{zip}-{index}', 'rdv_site_web': base_url, 'zip': zip, 'nom': name, 'address': address, 'reasons': reasons}
        result.append(payload)
        index += 1

def async_parse_zip(zip: str):
    profiles = []
    for profile in get_profiles(zip, DEFAULT_CLIENT):
        profile = get_location(profile, profile['zip'], profile['address'])                
        profile['iterator'] = 'mapharma'
        profile['type'] = DRUG_STORE  
        profiles.append(profile)
    if len(profiles) > 0:
        logger.info(f'Found {len(profiles)} in CODE POSTAL {zip}')
        return {zip: profiles}
    return []


def main():
    zip_count = 0
    centers_count = 0
    zips = {}

    startTime = time.time()
    with open("data/input/codepostal_to_insee.json", "r") as json_file:
        zips = json.load(json_file)
    zip_count = len(zips)
    pool = Pool(15)
    result_profiles = pool.map(async_parse_zip, zips.keys())
    result = {}
    # le pool renvoi un résultat mal formatté, on reconstruit le dico
    for group in result_profiles:
        if group != []:
            key = next(iter(group))
            value = group[key]
            centers_count += len(value)
            result[key] = value
    elapsedTime = time.time() - startTime
    logger.info(f'Scanned {zip_count} 📬 in {round(elapsedTime,1)} sec 🕜')
    logger.info(f'and all I got was a loosy count of {centers_count} centers 😭')
    with open("data/output/mapharma-centers.json", "w", encoding='utf8') as json_file:
        json.dump(result, json_file, indent = 4, sort_keys=True)

if __name__ == "__main__":
    main()
