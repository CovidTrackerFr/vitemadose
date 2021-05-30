import json
import sys
import re
from pathlib import Path
from bs4 import BeautifulSoup
from typing import NamedTuple, Optional, Tuple, Dict, List
from datetime import datetime, timedelta, date

from utils.vmd_logger import get_logger
from utils.vmd_geo_api import get_location_from_address, Location
from utils.vmd_utils import format_phone_number
from utils.vmd_utils import departementUtils  # cp_to_insee, to_departement_number
from utils.vmd_config import get_conf_platform

import httpx
from .clikodoc_api import get_doctors, DEFAULT_CLIENT


CLIKODOC_CONF = get_conf_platform("clikodoc")
CLIKODOC_ENABLED = CLIKODOC_CONF.get("enabled", False)
FIRST_INJECTION_MOTIVES = CLIKODOC_CONF.get("filters", {}).get("first_injection_typeids", [])
INVALID_DOCTORS = CLIKODOC_CONF.get("filters", {}).get("invalid_doctors", [])
CLIKODOC_CENTERS_PATH = CLIKODOC_CONF.get("center_scraper", {}).get("result_path", "")


logger = get_logger()


def _get_location(doctor: Dict) -> Dict:
    location: Optional[Location] = get_location_from_address(
        doctor["clinic_address_line_1"], zipcode=doctor["clinic_zipcode"]
    )

    if not location:
        location = Location()
        location["number_street"] = re.sub(r"\W*\d{5}.*$", "", doctor["clinic_address_line_1"].strip())
        location["com_name"] = doctor["city_name"]
        location["com_zipcode"] = doctor["clinic_zipcode"]
        location["com_insee"] = departementUtils.cp_to_insee(location["com_zipcode"])
        location["departement"] = departementUtils.to_departement_number(location["com_insee"])
        location["full_address"] = f"{location['number_street']} {location['com_zipcode']} {location['com_name']}"
        location["longitude"] = float(doctor["clinic_longitude"])
        location["latitude"] = float(doctor["clinic_latitude"])

    return location


def _get_business_hours(doctor: Dict) -> Dict:
    business_hours: dict = {
        "lundi": None,
        "mardi": None,
        "mercredi": None,
        "jeudi": None,
        "vendredi": None,
        "samedi": None,
        "dimanche": None,
    }

    if "timinigs" in doctor:
        schedule = json.loads(doctor["timinigs"])
        business_hours["lundi"] = schedule["Monday"]
        business_hours["mardi"] = schedule["Tuesday"]
        business_hours["mercredi"] = schedule["Wednesday"]
        business_hours["jeudi"] = schedule["Thursday"]
        business_hours["vendredi"] = schedule["Friday"]
        business_hours["samedi"] = schedule["Saturday"]
        business_hours["dimanche"] = schedule["Sunday"]

    if len([x for x in business_hours.values() if x]) < 3:  # check if no 'timinigs' or 'timinigs' with no data or bad data
        weekdays: Tuple[str] = ("dimanche", "lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi")
        closed_weekdays: List[int] = [int(x) for x in doctor["cal_slotdays_to_hide"].split(",")]
        for index, weekday in enumerate(weekdays):
            business_hours[weekday] = (
                f"{doctor['clinic_start_time'][:5]} - {doctor['clinic_end_time'][:5]}"
                if index not in closed_weekdays
                else ""
            )

    return business_hours


def _get_motives(doctor: Dict) -> List[Dict]:
    motives = [x for x in doctor["type_ids"].split(",") if x in FIRST_INJECTION_MOTIVES]

    soup = BeautifulSoup(doctor["type_select_option"], "lxml")
    output = []
    for motive in motives:
        option = soup.find("option", {"value": motive})
        if option:
            output.append({
                    "id": motive,
                    "text": option.text,
                    "onlyByPhone": option["data-allow_patient_booking"] == "0"
            })

    return output


def parse_all_docs(client: httpx.Client = DEFAULT_CLIENT):
    output = []
    docs = get_doctors(client)
    if docs is None:
        return []
    for doc in docs["data"]:
        if doc["user_id"] in INVALID_DOCTORS:
            continue
        if any(x in FIRST_INJECTION_MOTIVES for x in doc.get("type_ids", "").split(",")):
            output.append(
                {
                    "gid": doc["user_id"],
                    "clinic_id": doc["clinic_id"],
                    "user_id": doc["user_id"],
                    "type": doc["specialization_ids"],
                    "motives": _get_motives(doc),
                    "rdv_site_web": doc["doc_url"],
                    "doctor_name": f"{doc['title']} {doc['first_name']} {doc['last_name']}",
                    "clinic_name": doc["clinic_name"],
                    "location": _get_location(doc),
                    "business_hours": _get_business_hours(doc),
                    "phone": format_phone_number(doc["clinic_tel"]),
                }
            )
    return output


if __name__ == "__main__":  # pragma: no cover
    if CLIKODOC_ENABLED:
        docs = parse_all_docs()
        path_out = Path(CLIKODOC_CENTERS_PATH)
        logger.info(f"Found {len(docs)} practionners on Clikodoc")
        logger.info(f"> Writing them on {path_out}")
        path_out.write_text(json.dumps(docs))
    else:
        logger.error(f"Clikodoc scraper is disabled in configuration file.")
        sys.exit(1)
