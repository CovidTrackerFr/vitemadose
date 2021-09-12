import os
import logging

import httpx
from typing import Dict, Iterator, List, Optional, Tuple, Set
from scraper.keldoc.keldoc_center import KeldocCenter
from scraper.keldoc.keldoc_filters import filter_vaccine_motives
from scraper.pattern.scraper_request import ScraperRequest
from scraper.profiler import Profiling
from utils.vmd_config import get_conf_platform, get_config, get_conf_outputs
from utils.vmd_utils import DummyQueue
from scraper.circuit_breaker import ShortCircuit
from scraper.creneaux.creneau import Creneau, Lieu, Plateforme, PasDeCreneau
import json
import requests
from cachecontrol import CacheControl
from cachecontrol.caches.file_cache import FileCache


# PLATFORM MUST BE LOW, PLEASE LET THE "lower()" IN CASE OF BAD INPUT FORMAT.
PLATFORM = "keldoc".lower()

PLATFORM_CONF = get_conf_platform("keldoc")
PLATFORM_ENABLED = PLATFORM_CONF.get("enabled", False)

PLATFORM_TIMEOUT = PLATFORM_CONF.get("timeout", 25)

timeout = httpx.Timeout(PLATFORM_TIMEOUT, connect=PLATFORM_TIMEOUT)
# change KELDOC_KILL_SWITCH to True to bypass Keldoc scraping

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
    if not PLATFORM_ENABLED:
        return None
    center = KeldocCenter(request, client=session, creneau_q=creneau_q)
    center.vaccine_motives = filter_vaccine_motives(center.appointment_motives)

    center.lieu = Lieu(
        plateforme=Plateforme[PLATFORM.upper()],
        url=request.url,
        location=request.center_info.location,
        nom=request.center_info.nom,
        internal_id=f"keldoc{request.internal_id}",
        departement=request.center_info.departement,
        lieu_type=request.practitioner_type,
        metadata=request.center_info.metadata,
    )

    # Find the first availability
    date, count = center.find_first_availability(request.get_start_date())
    if not date and center.lieu:
        if center.lieu:
            center.found_creneau(PasDeCreneau(lieu=center.lieu, phone_only=request.appointment_by_phone_only))
        request.update_appointment_count(0)
        return None

    request.update_appointment_count(count)
    return date.strftime("%Y-%m-%dT%H:%M:%S.%f%z")


def center_iterator(client=None) -> Iterator[Dict]:
    if not PLATFORM_ENABLED:
        logger.warning(f"{PLATFORM.capitalize()} scrap is disabled in configuration file.")
        return []

    session = CacheControl(requests.Session(), cache=FileCache("./cache"))

    if client:
        session = client
    try:
        url = f'{get_config().get("base_urls").get("github_public_path")}{get_conf_outputs().get("centers_json_path").format(PLATFORM)}'
        response = session.get(url)
        # Si on ne vient pas des tests unitaires
        if not client:
            if response.from_cache:
                logger.info(f"Liste des centres pour {PLATFORM} vient du cache")
            else:
                logger.info(f"Liste des centres pour {PLATFORM} est une vraie requête")

        data = response.json()
        logger.info(f"Found {len(data)} {PLATFORM.capitalize()} centers (external scraper).")
        for center in data:
            yield center
    except Exception as e:
        logger.warning(f"Unable to scrape {PLATFORM} centers: {e}")
