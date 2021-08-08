from scraper.bimedoc.bimedoc import PLATFORM
import httpx
from utils.vmd_logger import get_logger
from utils.vmd_config import get_conf_platform, get_config
from utils.vmd_utils import departementUtils, format_phone_number
from scraper.pattern.vaccine import Vaccine, get_vaccine_name

import json
import os
import datetime

NUMBER_OF_SCRAPED_DAYS = get_config().get("scrape_on_n_days", 28)

BIMEDOC_CONF = get_conf_platform("bimedoc")
BIMEDOC_ENABLED = BIMEDOC_CONF.get("enabled", False)

SCRAPER_CONF = BIMEDOC_CONF.get("center_scraper", {})
CENTER_LIST_URL = BIMEDOC_CONF.get("api", {}).get("center_list", {})
SLOTS_URL = BIMEDOC_CONF.get("api", {}).get("slots", {})
APPOINTMENT_URL = BIMEDOC_CONF.get("appointment_url", {})

DEFAULT_CLIENT = httpx.Client()

logger = get_logger()


BIMEDOC_HEADERS = { 
    "Authorization": "Partner 8b0591b8-871b-42aa-8731-966c1711d168:x9JmYf#tS~-aEcJJ",
}

def scrap_centers():
    if not BIMEDOC_ENABLED:
        return None

    center_list=[]
    start_date=datetime.date.today()
    end_date=datetime.date.today()+datetime.timedelta(NUMBER_OF_SCRAPED_DAYS)

    logger.info(f"[Bimedoc centers] Parsing centers from API")
    try:
        r = DEFAULT_CLIENT.get(
            CENTER_LIST_URL.format(start_date=start_date, end_date=end_date),
            headers=BIMEDOC_HEADERS,
        )
 
        api_centers = r.json()

        if r.status_code != 200:
            logger.error(f"Can't access API center list - {r.status_code} => {json.loads(r.text)}")
            return None
    except:
        logger.error(f"Can't access API center list")
        return None

    if not api_centers:
        return None
    if len(api_centers) == 0:
        return None

    for center in api_centers:

        try:
            r = DEFAULT_CLIENT.get(
                SLOTS_URL.format(pharmacy_id=center["id"],start_date=start_date, end_date=end_date),
                headers=BIMEDOC_HEADERS,
            )

            center_result = r.json()

            if r.status_code != 200:
                logger.error(f"Can't access API center details - {r.status_code} => {json.loads(r.text)}")
                
            else:
                center_result.pop("slots")
                center_list.append(center_result)


        except:
            logger.error(f"Can't access API center details")
            return None

    return center_list


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


def parse_bimedoc_centers():

    unique_centers = []
    centers_list = scrap_centers()
    useless_keys = ["id", "postcode", "coordinates", "city", "street","building_number", "name"]

    if centers_list is None:
        return None

    for centre in centers_list:
        logger.info(f'[Bimedoc] Found Center {centre["name"]} ({centre["postcode"]})')
        if centre["id"] not in [unique_center["gid"] for unique_center in unique_centers]:
            centre["rdv_site_web"]=APPOINTMENT_URL.format(pharmacy_id=centre["id"])
            centre["platform_is"]=PLATFORM
            centre["gid"] = f'bimedoc{centre["id"]}'
            centre["nom"] = centre["name"]
            centre["com_insee"] = departementUtils.cp_to_insee(centre["postcode"])
            long_coor1, lat_coor1 = get_coordinates(centre)
            address = f'{centre["street"]}, {centre["postcode"]} {centre["city"]}'
            centre["address"] = address
            centre["long_coor1"] = long_coor1
            centre["lat_coor1"] = lat_coor1
            centre["type"] = set_center_type("pharmacie")
            centre["phone_number"] = format_phone_number(centre["phone_number"])
            centre["vaccine_names"] = [get_vaccine_name(vaccine).value for vaccine in centre["vaccine_names"]]
            [centre.pop(key) for key in list(centre.keys()) if key in useless_keys]

            unique_centers.append(centre)

    return unique_centers


if __name__ == "__main__":  # pragma: no cover
    if BIMEDOC_ENABLED:
        centers = parse_bimedoc_centers()
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
