import httpx
from utils.vmd_logger import get_logger
from utils.vmd_config import get_conf_platform, get_config
from utils.vmd_utils import departementUtils, format_phone_number
from scraper.pattern.vaccine import Vaccine, get_vaccine_name
import json
import os
import datetime
import multiprocessing
import sys
import time

NUMBER_OF_SCRAPED_DAYS = get_config().get("scrape_on_n_days", 28)

PLATFORM="bimedoc".lower()

BIMEDOC_CONF = get_conf_platform("bimedoc")
BIMEDOC_ENABLED = BIMEDOC_CONF.get("enabled", False)

SCRAPER_CONF = BIMEDOC_CONF.get("center_scraper", {})
CENTER_LIST_URL = BIMEDOC_CONF.get("api", {}).get("center_list", {})
SLOTS_URL = BIMEDOC_CONF.get("api", {}).get("slots", {})
APPOINTMENT_URL = BIMEDOC_CONF.get("appointment_url", {})

DEFAULT_CLIENT = httpx.Client()

logger = get_logger()


BIMEDOC_HEADERS = { 
    "Authorization": os.environ.get("BIMEDOC_API_KEY", "")
}

def get_center_details(center):
    start_date=datetime.date.today()
    end_date=datetime.date.today()+datetime.timedelta(NUMBER_OF_SCRAPED_DAYS)
    request_url=SLOTS_URL.format(pharmacy_id=f'{center["id"]}/',start_date=start_date, end_date=end_date)
    try:
        r = DEFAULT_CLIENT.get(request_url, headers=BIMEDOC_HEADERS)
        time.sleep(0.1)
        print(r)
        r.raise_for_status()
        print(r.status_code)
        center_details = r.json()
        print(center_details)
        if r.status_code != 200:
            logger.error(f"Can't access API center details - {r.status_code} => {json.loads(r.text)}")

        else:
            useless_keys = ["slots","id", "postcode", "coordinates", "city", "street","building_number", "name"]
            logger.info(f'[Bimedoc] Found Center {center_details["name"]} ({center_details["postcode"]})')

            center_details["rdv_site_web"]=APPOINTMENT_URL.format(pharmacy_id=center_details["id"])
            center_details["platform_is"]=PLATFORM
            center_details["gid"] = f'bimedoc{center_details["id"]}'
            center_details["nom"] = center_details["name"]
            center_details["com_insee"] = departementUtils.cp_to_insee(center_details["postcode"])
            long_coor1, lat_coor1 = get_coordinates(center_details)
            address = f'{center_details["street"]}, {center_details["postcode"]} {center_details["city"]}'
            center_details["address"] = address
            center_details["long_coor1"] = long_coor1
            center_details["lat_coor1"] = lat_coor1
            center_details["type"] = set_center_type("pharmacie")
            center_details["phone_number"] = format_phone_number(center_details["phone_number"])
            center_details["vaccine_names"] = [get_vaccine_name(vaccine).value for vaccine in center_details["vaccine_names"]]
            [center_details.pop(key) for key in list(center_details.keys()) if key in useless_keys]
    except httpx.HTTPError as exc:
        print(f"HTTP Exception for {exc.request.url} - {exc}")
        return None
    return center_details


def scrap_centers():
    if not BIMEDOC_ENABLED:
        return None

    start_date=datetime.date.today()
    end_date=datetime.date.today()+datetime.timedelta(NUMBER_OF_SCRAPED_DAYS)

    logger.info(f"[Bimedoc centers] Parsing centers from API")

        
    request_url = CENTER_LIST_URL.format(start_date=start_date, end_date=end_date)
    try:
        r = DEFAULT_CLIENT.get(request_url,headers=BIMEDOC_HEADERS)
        r.raise_for_status()
        center_list = r.json()

        if r.status_code != 200:
            logger.error(f"Can't access API center list - {r.status_code} => {json.loads(r.text)}")
            return None
        else:
            logger.info(f"La liste des centres Bimedoc a été récupérée (API CENTER_LIST)")
    
    except:
        logger.error(f"Can't access API center list - {r}")
        return None

    if not center_list:
        return None
    if len(center_list) == 0:
        return None

    print(center_list)
    results = []
    with multiprocessing.Pool(50) as pool:
        centers_with_details = pool.imap_unordered(get_center_details, (center for center in center_list))  
        for center_with_details in centers_with_details:
            if center_with_details is not None:
                results.append(center_with_details)
    return results


def get_coordinates(center):
    coordinates=center["coordinates"]
    longitude = coordinates[0]
    latitude = coordinates[1]
    if longitude:
        longitude = float(longitude)
    if latitude:
        latitude = float(latitude)
    return longitude, latitude


def set_center_type(center_type: str):
    center_types = BIMEDOC_CONF.get("center_types", {})
    center_type_format = [center_types[i] for i in center_types if i in center_type]
    return center_type_format[0]



if __name__ == "__main__":  # pragma: no cover
    if BIMEDOC_ENABLED:
        centers = scrap_centers()
        path_out = SCRAPER_CONF.get("result_path", False)
        if not path_out:
            logger.error(f"Bimedoc - No result_path in config file.")
            exit(1)

        if not centers:
            exit(1)

        logger.info(f"Found {len(centers)} centers on Bimedoc")
        if len(centers) ==0 :
            logger.error(f"[NOT SAVING RESULTS]{len(centers)} does not seem like enough Bimedoc centers")
        else:
            logger.info(f"> Writing them on {path_out}")
            with open(path_out, "w") as f:
                f.write(json.dumps(centers, indent=2))
    else:
        logger.error(f"Bimedoc scraper is disabled in configuration file.")
        exit(1)
