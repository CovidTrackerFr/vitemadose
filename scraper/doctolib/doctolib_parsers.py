from typing import Dict, List, Optional

from scraper.pattern.scraper_result import VACCINATION_CENTER
from utils.vmd_config import get_conf_platform
from utils.vmd_utils import departementUtils, format_phone_number


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


def parse_center_places(center_output: Dict) -> List[Dict]:
    places = center_output.get("places", {})
    gid = "d{0}".format(center_output.get("profile", {}).get("id", ""))
    extracted_visit_motives = [vm.get("name") for vm in center_output.get("visit_motives", [])]
    extracted_visit_ids = [vm.get("ref_visit_motive_id") for vm in center_output.get("visit_motives", [])]

    liste_infos_page = []
    for place in places:
        infos_page = parse_place(place)
        infos_page["gid"] = gid
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
        "phone_number": format_phone_number(phone_number) if phone_number else None,
        "business_hours": parse_doctolib_business_hours(place),
    }


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
