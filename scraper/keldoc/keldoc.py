import os
import logging

import httpx
from typing import Dict, Iterator, List, Optional, Tuple, Set
from scraper.keldoc.keldoc_center import KeldocCenter
from scraper.keldoc.keldoc_filters import get_relevant_vaccine_specialties_id, filter_vaccine_motives
from scraper.pattern.scraper_request import ScraperRequest
from scraper.profiler import Profiling
from utils.vmd_config import get_conf_platform
from utils.vmd_utils import DummyQueue
from scraper.circuit_breaker import ShortCircuit
import json

KELDOC_CONF = get_conf_platform("keldoc")
timeout = httpx.Timeout(KELDOC_CONF.get("timeout", 25), connect=KELDOC_CONF.get("timeout", 25))
# change KELDOC_KILL_SWITCH to True to bypass Keldoc scraping
KELDOC_ENABLED = KELDOC_CONF.get("enabled", False)
KELDOC_HEADERS = {
    "User-Agent": os.environ.get("KELDOC_API_KEY", ""),
}
session = httpx.Client(timeout=timeout, headers=KELDOC_HEADERS)
logger = logging.getLogger("scraper")


# Allow 10 bad runs of keldoc_slot before giving up for the 200 next tries
@ShortCircuit("keldoc_slot", trigger=10, release=200, time_limit=40.0)
@Profiling.measure("keldoc_slot")
def fetch_slots(request: ScraperRequest, creneau_q=DummyQueue()):
    if "keldoc.com" in request.url:
        logger.debug(f"Fixing wrong hostname in request: {request.url}")
        request.url = request.url.replace("keldoc.com", "vaccination-covid.keldoc.com")
    if not KELDOC_ENABLED:
        return None
    center = KeldocCenter(request, client=session)
    # Unable to parse center resources (id, location)?
    if not center.parse_resource():
        return None
    # Try to fetch center data
    if not center.fetch_center_data():
        return None

    # Filter specialties, cabinets & motives
    center.vaccine_specialties = get_relevant_vaccine_specialties_id(center.specialties)
    center.fetch_vaccine_cabinets()
    center.vaccine_motives = filter_vaccine_motives(
        session,
        center.selected_cabinet,
        center.id,
        center.vaccine_specialties,
        center.vaccine_cabinets,
        request=request,
    )
    # Find the first availability
    date, count, appointment_schedules = center.find_first_availability(request.get_start_date())
    if not date:
        request.update_appointment_count(0)
        return None
    request.update_appointment_count(count)
    if appointment_schedules:
        request.update_appointment_schedules(appointment_schedules)
    return date.strftime("%Y-%m-%dT%H:%M:%S.%f%z")


def center_iterator() -> Iterator[Dict]:
    if not KELDOC_ENABLED:
        logger.warning("Keldoc scrap is disabled in configuration file.")
        return []
    center_path = "data/output/keldoc_centers.json"
    with open(center_path) as jsonFile:
        jsonObject = json.loads(jsonFile.read())
        jsonFile.close()

    logger.info(f"Found {len(jsonObject)} Keldoc centers (external scraper).")
    for center in jsonObject:
        yield center
