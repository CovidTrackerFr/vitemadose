from types import DynamicClassAttribute
from typing import Dict, List, Optional

from scraper.pattern.scraper_result import VACCINATION_CENTER
from utils.vmd_config import get_conf_platform, get_conf_inputs
from utils.vmd_utils import departementUtils, format_phone_number
import requests
import json
from urllib import parse

DOCTOLIB_CONF = get_conf_platform("doctolib")
SCRAPER_CONF = DOCTOLIB_CONF.get("center_scraper")


def get_coordinates(doctor_dict: Dict):
    longitude = doctor_dict["position"]["lng"]
    latitude = doctor_dict["position"]["lat"]
    if longitude:
        longitude = float(longitude)
    if latitude:
        latitude = float(latitude)
    return longitude, latitude


def center_type(url_path: str, nom: str) -> str:
    for key in SCRAPER_CONF.get("center_types"):
        if key in nom.lower() or key in url_path:
            return SCRAPER_CONF.get("center_types")[key]
    return SCRAPER_CONF.get("center_types").get("*", VACCINATION_CENTER)


def parse_doctor(doctor_dict: Dict) -> Dict:
    nom = doctor_dict["name_with_title"]
    sub_addresse = doctor_dict["address"]
    ville = doctor_dict["city"]
    code_postal = doctor_dict["zipcode"].replace(" ", "").strip()
    addresse = f"{sub_addresse}, {code_postal} {ville}"
    url_path = doctor_dict["link"]
    _type = center_type(url_path, nom)
    longitude, latitude = get_coordinates(doctor_dict)
    return {
        "nom": nom,
        "ville": ville,
        "address": addresse,
        "long_coor1": longitude,
        "lat_coor1": latitude,
        "type": _type,
        "com_insee": departementUtils.cp_to_insee(code_postal),
    }


def get_atlas_correct_match(atlas_matches, infos_page, atlas_center_list):
    correct_atlas_gid = None

    req = requests.get(
        "https://api-adresse.data.gouv.fr/search/",
        params=[("q", infos_page["address"]), ("postcode", infos_page["cp"])],
    )
    req.raise_for_status()

    try:
        data = req.json()
        id_adr = data["features"][0]["properties"]["id"]
        matching_atlas_for_id = [
            center_id for center_id, center_data in atlas_center_list.items() if center_data["id_adresse"] == id_adr
        ]
        if matching_atlas_for_id:
            correct_atlas_gid = matching_atlas_for_id[0]
    except:
        return None
    return correct_atlas_gid


def parse_center_places(center_output: Dict, url, atlas_center_list) -> List[Dict]:

    # if url in atlas_center_list.keys():
    #     atlas_gid = atlas_center_list[url]
    places = center_output.get("places", {})
    gid = "d{0}".format(center_output.get("profile", {}).get("id", ""))
    extracted_visit_motives = [vm.get("name") for vm in center_output.get("visit_motives", [])]
    extracted_visit_ids = [vm.get("ref_visit_motive_id") for vm in center_output.get("visit_motives", [])]

    atlas_matches = [center_id for center_id, center_data in atlas_center_list.items() if url in center_data["url_end"]]
    if len(atlas_matches) == 0:
        atlas_gid = None
    if len(atlas_matches) == 1:
        atlas_gid = max(atlas_matches)

    liste_infos_page = []
    for place in places:
        infos_page = parse_place(place)
        if len(atlas_matches) > 1:
            atlas_gid = get_atlas_correct_match(atlas_matches, infos_page, atlas_center_list)
        infos_page["gid"] = gid
        infos_page["atlas_gid"] = atlas_gid
        infos_page["visit_motives"] = extracted_visit_motives
        infos_page["visit_motives_ids"] = extracted_visit_ids
        infos_page["booking"] = center_output
        liste_infos_page.append(infos_page)

    # Returns a list with data for each place
    return liste_infos_page


def parse_place(place: Dict) -> Dict:
    phone_number = place.get("landline_number", place.get("phone_number"))
    return {
        "place_id": place["id"],
        "address": place["full_address"],
        "ville": place["city"],
        "long_coor1": place.get("longitude"),
        "lat_coor1": place.get("latitude"),
        "com_insee": departementUtils.cp_to_insee(place["zipcode"].replace(" ", "").strip()),
        "cp": place["zipcode"].replace(" ", "").strip(),
        "phone_number": format_phone_number(phone_number) if phone_number else None,
        "business_hours": parse_doctolib_business_hours(place),
    }


def parse_atlas():
    url = get_conf_inputs().get("from_data_gouv_website").get("centers_gouv")
    data = requests.get(url).json()
    doctolib_gouv_centers = {}
    for center in data["features"]:
        centre_pro = center["properties"].get("c_reserve_professionels_sante", False)
        url = center["properties"].get("c_rdv_site_web", None)
        id_adresse = center["properties"].get("c_id_adr", None)
        gid = center["properties"].get("c_gid", None)

        if centre_pro:
            continue
        if not url:
            continue
        if not gid:
            continue
        if not "doctolib" in url:
            continue
        end_url = f'{parse.urlsplit(url).path.split("/")[-1]}'

        doctolib_gouv_centers[gid] = {"url_end": end_url, "id_adresse": id_adresse}
    return doctolib_gouv_centers


def parse_doctolib_business_hours(place: dict) -> Optional[dict]:
    # Opening hours
    business_hours = dict()
    if not place["opening_hours"]:
        return None

    for opening_hour in place["opening_hours"]:
        format_hours = ""
        key_name = SCRAPER_CONF.get("business_days")[opening_hour["day"] - 1]
        if not opening_hour.get("enabled", False):
            business_hours[key_name] = None
            continue
        for range in opening_hour["ranges"]:
            if len(format_hours) > 0:
                format_hours += ", "
            format_hours += f"{range[0]}-{range[1]}"
        business_hours[key_name] = format_hours

    return business_hours


def center_reducer(center: dict) -> dict:
    """This function should be used to remove fields that are irrelevant to the front,
    such as fields used to filter centers during scraping process.
    Removes following fields : visit_motives

    Parameters
    ----------
    center_dict : "Center" dict
        Center dict, output by the doctolib_center_scrap.center_from_doctor_dict

    Returns
    ----------
    center dict, without irrelevant fields to the front

    Example
    ----------
    >>> center_reducer({'gid': 'd257554', 'visit_motives': ['1re injection vaccin COVID-19 (Pfizer-BioNTech)', '2de injection vaccin COVID-19 (Pfizer-BioNTech)', '1re injection vaccin COVID-19 (Moderna)', '2de injection vaccin COVID-19 (Moderna)']})
    {'gid': 'd257554'}
    """
    center.pop("visit_motives", "place_id")

    return center
