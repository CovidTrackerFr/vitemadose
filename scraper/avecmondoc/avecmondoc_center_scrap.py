import httpx
from utils.vmd_logger import get_logger
from utils.vmd_config import get_conf_platform
from utils.vmd_utils import departementUtils, format_phone_number
import json
import os

AVECMONDOC_CONF = get_conf_platform("avecmondoc")
AVECMONDOC_ENABLED = AVECMONDOC_CONF.get("enabled", False)
AVECMONDOC_HEADERS = {
    "User-Agent": os.environ.get("AVECMONDOC_API_KEY", ""),
}
SCRAPER_CONF = AVECMONDOC_CONF.get("center_scraper", {})
CENTER_LIST_URL = AVECMONDOC_CONF.get("api", {}).get("search", {})

DEFAULT_CLIENT = httpx.Client()

logger = get_logger()

def scrap_centers():
    if not AVECMONDOC_ENABLED:
        return None

    logger.info(f"[AvecMonDoc centers] Parsing centers from API")
    try:
        r = DEFAULT_CLIENT.get(
            CENTER_LIST_URL.format(1),
            headers=AVECMONDOC_HEADERS,
        )
        api_centers = r.json()
        if api_centers.get("count",None) is not None:
            limit=api_centers.get("count",None)

        r = DEFAULT_CLIENT.get(
        CENTER_LIST_URL.format(limit),
        headers=AVECMONDOC_HEADERS,
    )
        api_centers = r.json().get("data")

        if r.status_code != 200:
            logger.error(f"Can't access API - {r.status_code} => {json.loads(r.text)['message']}")
            return None
    except:
        logger.error(f"Can't access API")
        return None

    return api_centers


# def get_coordinates(center):
#     longitude = center["position"]["longitude"]
#     latitude = center["position"]["latitude"]
#     if longitude:
#         longitude = float(longitude)
#     if latitude:
#         latitude = float(latitude)
#     return longitude, latitude


# def set_center_type(center_type: str):
#     center_types = AVECMONDOC_CONF.get("center_types", {})
#     center_type_format = [center_types[i] for i in center_types if i in center_type]
#     return center_type_format[0]


# def parse_mesoigner_business_hours(place: dict):
#     # Opening hours
#     business_hours = dict()
#     if not place["opening_hours"]:
#         return None

#     for opening_hour in place["opening_hours"]:
#         format_hours = ""
#         key_name = SCRAPER_CONF["business_days"][opening_hour["day"] - 1]
#         if not opening_hour["ranges"] or len(opening_hour["ranges"]) == 0:
#             business_hours[key_name] = None
#             continue
#         for range in opening_hour["ranges"]:
#             if len(format_hours) > 0:
#                 format_hours += ", "
#             format_hours += f"{range[0]}-{range[1]}"
#         business_hours[key_name] = format_hours
#     return business_hours


def parse_mesoigner_centers():

    unique_centers = []
    centers_list = scrap_centers()
    useless_keys = ["id", "zipcode", "position", "opening_hours", "position", "adress_city", "adress_street"]

    if centers_list is None:
        return None

    for centre in centers_list:
        logger.info(f'[Mesoigner] Found Center {centre["name"]} ({centre["zipcode"]})')

        if centre["rdv_site_web"] not in [unique_center["rdv_site_web"] for unique_center in unique_centers]:
            centre["gid"] = centre["id"]
            centre["nom"] = centre["name"]
            centre["com_insee"] = departementUtils.cp_to_insee(centre["zipcode"])
            long_coor1, lat_coor1 = get_coordinates(centre)
            address = f'{centre["adress_street"]}, {centre["zipcode"]} {centre["adress_city"]}'
            centre["address"] = address
            centre["long_coor1"] = long_coor1
            centre["lat_coor1"] = lat_coor1
            centre["business_hours"] = parse_mesoigner_business_hours(centre)
            centre["type"] = set_center_type(centre["center_type"])
            centre["phone_number"] = format_phone_number(centre["phone_number"])

            [centre.pop(key) for key in list(centre.keys()) if key in useless_keys]

            unique_centers.append(centre)

    return unique_centers


if __name__ == "__main__":  # pragma: no cover
    if AVECMONDOC_ENABLED:
        scrap_centers()
        # centers = parse_mesoigner_centers()
        # path_out = SCRAPER_CONF.get("result_path", False)
        # if not path_out:
        #     logger.error(f"Mesoigner - No result_path in config file.")
        #     exit(1)

        # if not centers:
        #     exit(1)

        # logger.info(f"Found {len(centers)} centers on Mesoigner")
        # if len(centers) < SCRAPER_CONF.get("minimum_results", 0):
        #     logger.error(f"[NOT SAVING RESULTS]{len(centers)} does not seem like enough Mesoigner centers")
        # else:
        #     logger.info(f"> Writing them on {path_out}")
        #     with open(path_out, "w") as f:
        #         f.write(json.dumps(centers, indent=2))
    else:
        logger.error(f"Mesoigner scraper is disabled in configuration file.")
        exit(1)
