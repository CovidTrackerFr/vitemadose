import os
import logging

import httpx
from typing import Dict, Iterator, List, Optional, Tuple, Set
from scraper.keldoc.keldoc_center import KeldocCenter
from scraper.keldoc.keldoc_filters import filter_vaccine_motives
from scraper.pattern.scraper_request import ScraperRequest
from scraper.profiler import Profiling
from utils.vmd_config import get_conf_platform
from utils.vmd_utils import DummyQueue
from scraper.circuit_breaker import ShortCircuit
from scraper.creneaux.creneau import Creneau, Lieu, Plateforme, PasDeCreneau

import json
import requests

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
    center = KeldocCenter(request, client=session, creneau_q=creneau_q)
    center.vaccine_motives = filter_vaccine_motives(center.appointment_motives)

    center.lieu = Lieu(
        plateforme=Plateforme.KELDOC,
        url=request.url,
        location=request.center_info.location,
        nom=request.center_info.nom,
        internal_id=f"keldoc{request.internal_id}",
        departement=request.center_info.departement,
        lieu_type=request.practitioner_type,
        metadata=request.center_info.metadata,
    )

    # Find the first availability
    date, count, appointment_schedules = center.find_first_availability(request.get_start_date())
    if not date and center.lieu:
        if center.lieu:
            center.found_creneau(PasDeCreneau(lieu=center.lieu, phone_only=request.appointment_by_phone_only))
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
    try:
        center_path = "data/output/keldoc_centers.json"
        url = f"https://raw.githubusercontent.com/CovidTrackerFr/vitemadose/data-auto/{center_path}"
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        file = open(center_path, "w")
        file.write(json.dumps(data, indent=2))
        file.close()
        logger.info(f"Found {len(data)} Keldoc centers (external scraper).")
        for center in data:
            yield center
    except Exception as e:
        logger.warning(f"Unable to scrape keldoc centers: {e}")
