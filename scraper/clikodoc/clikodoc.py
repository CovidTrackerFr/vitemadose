import httpx
from bs4 import BeautifulSoup
import json
from urllib.parse import urlencode
from pathlib import Path
import re

from functools import wraps
from typing import NamedTuple, Optional, Tuple, Dict, List, Iterator
from datetime import datetime, timedelta, date
from dataclasses import dataclass, field

from scraper.pattern.center_info import INTERVAL_SPLIT_DAYS, CHRONODOSES
from scraper.pattern.vaccine import Vaccine
from scraper.pattern.scraper_request import ScraperRequest
from scraper.pattern.scraper_result import GENERAL_PRACTITIONER
from utils.vmd_logger import get_logger
from utils.vmd_config import get_conf_platform, get_config
from scraper.profiler import Profiling

import httpx
from .clikodoc_api import get_next_available_date, get_slots, DEFAULT_CLIENT

CLIKODOC_CONF = get_conf_platform("clikodoc")
CLIKODOC_ENABLED = CLIKODOC_CONF.get("enabled", False)
DATA_AUTO_URL = get_config().get("data-auto", {}).get("base_url", "")
CLIKODOC_CENTERS_PATH = CLIKODOC_CONF.get("center_scraper", {}).get("result_path", "")
SLOT_LIMIT = CLIKODOC_CONF.get("slot_limit", 3)
DAYS_LIMIT = CLIKODOC_CONF.get("days_limit", 50)


logger = get_logger()

doctors_list = []


@dataclass(order=True)
class Slot:
    timestamp: datetime
    motive: str = field(compare=False)


def _populate_doctors_list():
    global doctors_list
    center_path = Path(CLIKODOC_CENTERS_PATH)
    doctors_list = json.loads(center_path.read_text())
    logger.info(f"Found {len(doctors_list)} Clikodoc centers (external scraper).")


def _get_first_available_date(doctorid: str, typeid:str, request: ScraperRequest = None) -> Optional[date]:
    first_date = get_next_available_date(doctorid, typeid, request=request)

    if not first_date or first_date["status"] != "success":
        return None
    else:
        return date.fromisoformat(first_date["nextavaildate"])


def _get_slots(doctorid: str, motiveid: str, start_date: date, end_date: date, request: ScraperRequest = None) -> List[Slot]:
    all_slots: List[Slot] = []

    next_date = start_date
    end_date_str = end_date.isoformat()
    while next_date < end_date:
        data = get_slots(doctorid, motiveid, next_date, end_date, request=request)
        if not data["slots"]:
            break
        for day, slots in data["slots"].items():
            if day <= end_date_str:
                all_slots.extend(
                    [Slot(datetime.strptime(f"{day} {slot['start']}", "%Y-%m-%d %H:%M"), motiveid) for slot in slots]
                )
        if (last_date := date.fromisoformat(max(list(data["slots"].keys())))) > next_date:
            next_date = last_date + timedelta(days=1)
        else:
            break
 
    return all_slots


def _count_slots(slots: List[Slot], start_date: date, end_date: date) -> int:
    return len([slot for slot in slots if slot.timestamp > start_date and slot.timestamp < end_date])


@Profiling.measure("clikodoc_slot")
def fetch_slots(request: ScraperRequest, client: httpx.Client = DEFAULT_CLIENT) -> Optional[str]:
    global doctors_list

    if not CLIKODOC_ENABLED:
        return None
    first_availability = None

    if not doctors_list:
        _populate_doctors_list()

    doctor = [doc for doc in doctors_list if doc["rdv_site_web"] == request.url]
    if not doctor:
        return None
    doctor = doctor[0]

    only_by_phone = True
    slots = []
    for motive in doctor["motives"]:
        only_by_phone = only_by_phone and motive["onlyByPhone"]
        if motive["onlyByPhone"] is True:
            request.set_appointments_only_by_phone(True)
            continue

        first_date = _get_first_available_date(doctor["user_id"], motive["id"], request=request)
        if not first_date:
            continue

        end_date = date.fromisoformat(request.start_date) + timedelta(days=DAYS_LIMIT)
        #first_date = date.fromisoformat(request.start_date)
        slots.extend(_get_slots(doctor["user_id"], motive["id"], first_date, end_date, request=request))

    if not slots:
        return None

    first_availability = min(slots).timestamp
    request.add_vaccine_type(Vaccine.ASTRAZENECA)
    request.update_appointment_count(len(slots))

    # create appointment_schedules array with names and dates
    appointment_schedules = []
    start_date = datetime.fromisoformat(request.get_start_date())
    end_date = start_date + timedelta(days=CHRONODOSES["Interval"], seconds=-1)
    appointment_schedules.append(
        {"name": "chronodose", "from": start_date.isoformat(), "to": end_date.isoformat(), "total": 0}
    )
    for n in INTERVAL_SPLIT_DAYS:
        end_date = start_date + timedelta(days=n, seconds=-1)
        appointment_schedules.append(
            {
                "name": f"{n}_days",
                "from": start_date.isoformat(),
                "to": end_date.isoformat(),
                "total": _count_slots(slots, start_date, end_date),
            }
        )

    request.update_appointment_schedules(appointment_schedules)
    logger.info(f"appointment_schedules: {request.appointment_schedules}")
    return first_availability.isoformat()


def center_iterator() -> Iterator[Dict]:
    if not CLIKODOC_ENABLED:
        return
    try:
        if not doctors_list:
            _populate_doctors_list()
        for doctor in doctors_list:
            center = {}
            center["gid"] = doctor["gid"]
            center["rdv_site_web"] = doctor["rdv_site_web"]
            center["com_cp"] = doctor["location"]["com_zipcode"]
            center["com_insee"] = doctor["location"]["com_insee"]
            center["address"] = doctor["location"]["full_address"]
            center["nom"] = doctor["doctor_name"]
            center["phone_number"] = doctor["phone"]
            center["location"] = {
                "long_coor1": doctor["location"]["longitude"],
                "lat_coor1": doctor["location"]["latitude"],
                "com_nom": doctor["location"]["com_name"],
                "com_cp": doctor["location"]["com_zipcode"],
            }
            center["iterator"] = "clikodoc"
            center["type"] = GENERAL_PRACTITIONER
            center["business_hours"] = doctor["business_hours"]
            yield center
    except Exception:
        logger.exception(f"Unable to scrape clikodoc centers")


if __name__ == "__main__":
    print_token()
