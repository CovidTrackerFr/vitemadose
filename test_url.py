from scraper.scraper import get_default_fetch_map, get_center_platform, fix_scrap_urls
from scraper.doctolib.doctolib import _parse_centre, _find_visit_motive_id
from utils.vmd_config import get_config
import json
import sys
import httpx
import requests
import os

DOCTOLIB_HEADERS = {
    "User-Agent": os.environ.get("DOCTOLIB_API_KEY", ""),
}


def find_platform(url: str) -> str:
    fetch_map = get_default_fetch_map()
    rdv_site_web = fix_scrap_urls(url)
    platform = get_center_platform(url, fetch_map=fetch_map)
    return platform


def load_config(platform: str) -> dict:
    config = get_config()
    config_platform = config["platforms"][platform.lower()]
    return config_platform


def load_platform_centers(config_platform: str) -> list:
    if not config_platform["center_scraper"]["result_path"]:
        return None
    centers_list = open(config_platform["center_scraper"]["result_path"])
    return json.load(centers_list)


def is_url_in_platforms_centers(platform_centers: str, url: str) -> bool:
    if not platform_centers or not url:
        return None
    for center in platform_centers:
        params = httpx.QueryParams(httpx.URL(url).query)
        if _parse_centre(center["rdv_site_web"]) == _parse_centre(url):
            return True
    return False


def get_doctolib_center_data(config_platform: dict, url: str) -> list:
    if not config_platform or not url:
        return None
    split_url = url.split("?")[0].split("/")[-1]
    center_data_url = config_platform["api"]["booking"].format(centre=split_url)
    center_data = requests.get(center_data_url, headers=DOCTOLIB_HEADERS)
    center_data = center_data.json()["data"]
    return center_data


def get_vaccination_motives(center_data: dict, vaccination_motives: list) -> dict:
    visit_motives = {}
    for visit_motive in center_data["visit_motives"]:
        if any(
            [keyword for keyword in str(visit_motive["name"]).lower() if keyword in str(vaccination_motives).lower()]
        ):
            if not visit_motive["id"] in visit_motives:
                visit_motives[(visit_motive["id"])] = visit_motive["name"]

    return visit_motives


def find_locations_with_vaccination_motive(visit_motives: dict, center_data: list) -> list:
    practice_ids_with_vaccination_motives = []
    for agenda in center_data["agendas"]:
        if agenda["practice_id"] in list(map(int, list(agenda["visit_motive_ids_by_practice_id"].keys()))) and any(
            [
                vaccination_motive
                for vaccination_motive in list(map(int, list(visit_motives)))
                if vaccination_motive in agenda["visit_motive_ids_by_practice_id"][str(agenda["practice_id"])]
            ]
        ):
            for place in center_data["places"]:
                if agenda["practice_id"] in place["practice_ids"] and not any(
                    [
                        item["id"]
                        for item in practice_ids_with_vaccination_motives
                        if item["id"] == agenda["practice_id"]
                    ]
                ):

                    practice_ids_with_vaccination_motives.append(
                        {
                            "id": agenda["practice_id"],
                            "name": f'{center_data["profile"]["name_with_title"]} - {place["formal_name"]}',
                            "address": place["full_address"],
                            "motives in centre" : 
                        }
                    )
    return practice_ids_with_vaccination_motives


def find_filtered_vaccination_motives(center_data: list, vaccination_motives_ids: dict) -> list:
    filtered_motives_names = {}
    filtered_motives = _find_visit_motive_id(center_data)
    for key, values in filtered_motives.items():
        for value in values:
            if value in vaccination_motives_ids and value not in filtered_motives_names:
                filtered_motives_names[value] = vaccination_motives_ids[value]
    return filtered_motives_names


if __name__ == "__main__":
    url = sys.argv[1]

    center_data = None
    url_dans_center_scraper = None

    platform = find_platform(url)
    config_platform = load_config(platform)
    platform_centers = load_platform_centers(config_platform)
    if platform == "Doctolib":
        center_data = get_doctolib_center_data(config_platform, url)
        url_dans_center_scraper = is_url_in_platforms_centers(platform_centers, url)
        vaccination_motives = config_platform["filters"]["appointment_reason"]
        vaccination_motives_ids = get_vaccination_motives(center_data, vaccination_motives)
        vaccination_places = find_locations_with_vaccination_motive(vaccination_motives_ids, center_data)
        relevant_visit_motives = find_filtered_vaccination_motives(center_data, vaccination_motives_ids)
    platform_enabled = config_platform["enabled"]

    print(f"plateforme = {platform}")
    print(f"plateforme activée = {platform_enabled}")
    print(f"url bien présente dans le scrap des centres ? {url_dans_center_scraper}")
    # print(f"données du centre = {center_data}")
    print(f"tous les motifs de vaccination = {vaccination_motives_ids}")
    print(f"motifs de vaccination ViteMaDose = {relevant_visit_motives}")

    print(f"lieux avec motifs de vaccination = {vaccination_places}")
