import json
import time
import logging
import os
from typing import Dict, Iterator, Optional
import httpx
import requests
from scraper.circuit_breaker import ShortCircuit
from scraper.creneaux.creneau import Creneau, Lieu, Plateforme, PasDeCreneau
from scraper.pattern.vaccine import Vaccine, get_vaccine_name
from scraper.pattern.scraper_request import ScraperRequest
from scraper.profiler import Profiling
from utils.vmd_config import get_conf_platform, get_config, get_conf_outputs
from utils.vmd_utils import DummyQueue, append_date_days
from typing import Dict, Iterator, List, Optional
import dateutil
from cachecontrol import CacheControl
from cachecontrol.caches.file_cache import FileCache
from scraper.error import Blocked403

PLATFORM = "Valwin"

PLATFORM_CONF = get_conf_platform(PLATFORM)
PLATFORM_ENABLED = PLATFORM_CONF.get("enabled", False)

PLATFORM_HEADERS = {}

PLATFORM_APIs = PLATFORM_CONF.get("api", "")

SCRAPER_CONF = PLATFORM_CONF.get("center_scraper", {})
CENTER_LIST_URL = PLATFORM_CONF.get("api", {}).get("center_list", {})

timeout = httpx.Timeout(PLATFORM_CONF.get("timeout", 30), connect=PLATFORM_CONF.get("timeout", 30))

if os.getenv("WITH_TOR", "no") == "yes":
    session = requests.Session()
    session.proxies = {  # type: ignore
        "http": "socks5://127.0.0.1:9050",
        "https": "socks5://127.0.0.1:9050",
    }
    DEFAULT_CLIENT = session  # type: ignore
else:
    DEFAULT_CLIENT = httpx.Client(timeout=timeout)

logger = logging.getLogger("scraper")


@Profiling.measure(f"{PLATFORM.lower().capitalize()}_slot")
def fetch_slots(request: ScraperRequest, creneau_q=DummyQueue) -> Optional[str]:
    if not PLATFORM_ENABLED:
        return None
    # Fonction principale avec le comportement "de prod".
    parse_availabilities = Slots(client=DEFAULT_CLIENT, creneau_q=creneau_q)
    # print(request.__dict__)
    return parse_availabilities.fetch(request)


class Slots:
    def __init__(
        self,
        creneau_q=DummyQueue,
        client: httpx.Client = None,
    ):
        self._client = DEFAULT_CLIENT if client is None else client
        self.creneau_q = creneau_q
        self.lieu = None

    def found_creneau(self, creneau):
        self.creneau_q.put(creneau)

    def fetch(self, request: ScraperRequest) -> Optional[str]:
        gid = request.center_info.internal_id
        platform = PLATFORM.lower()
        center_id = gid
        start_date = request.get_start_date()

        self.lieu = Lieu(
            plateforme=Plateforme[PLATFORM.upper()],
            url=request.url,
            location=request.center_info.location,
            nom=request.center_info.nom,
            internal_id=f"{PLATFORM}{request.internal_id}",
            departement=request.center_info.departement,
            lieu_type=request.practitioner_type,
            metadata=request.center_info.metadata,
        )

        centre_api_url = PLATFORM_APIs.get("slots", "").format(id=center_id)
        response = self._client.get(centre_api_url, headers=PLATFORM_HEADERS)
        request.increase_request_count("slots")

        if response.status_code == 403:
            request.increase_request_count("error")
            raise Blocked403(PLATFORM, centre_api_url)

        response.raise_for_status()
        rdata = response.json()
        first_availability = self.get_appointments(request, rdata)
        if self.lieu and first_availability is None:
            self.found_creneau(PasDeCreneau(lieu=self.lieu))
        return first_availability

    def get_appointments(self, request: ScraperRequest, slots_api):
        appointments_number = 0
        first_availability = None
        vaccine_ids = []

        if slots_api:
            if slots_api.get("links"):
                if slots_api.get("links").get("total"):
                    appointments_number += int(slots_api.get("links").get("total", 0))

        if len(slots_api.get("result", [])) == 0:
            return None

        start_date = request.get_start_date()

        for creneau in slots_api.get("result", []):
            for vaccine in creneau["types"]:
                vaccine_name = get_vaccine_name(vaccine["label"])
                vaccine_id = vaccine["id"]
                if vaccine_id == "be6c293a-e0a6-49ea-bdb4-31a779bde277":
                    vaccine_name = Vaccine.ASTRAZENECA
                request.add_vaccine_type(vaccine_name)
                if vaccine_id not in vaccine_ids:
                    vaccine_ids.append(vaccine_id)

        for creneau in slots_api.get("result", []):
            appointment_exact_date = creneau["start"]
            if len(vaccine_ids) == 1:
                url = (
                    PLATFORM_CONF.get("build_urls")
                    .get("campaign_target")
                    .format(pharmacy_link=request.url, vaccine_id=vaccine_ids[0])
                )
            else:
                url = PLATFORM_CONF.get("build_urls").get("campaign_choice").format(pharmacy_link=request.url)

            if self.lieu:
                self.lieu.url = url

            self.found_creneau(
                Creneau(
                    horaire=dateutil.parser.parse(appointment_exact_date),
                    reservation_url=url,
                    type_vaccin=vaccine_name,
                    lieu=self.lieu,
                )
            )

            if first_availability is None or appointment_exact_date < first_availability:
                first_availability = appointment_exact_date

        request.update_appointment_count(request.appointment_count + appointments_number)
        return first_availability


def center_iterator(client=None) -> Iterator[Dict]:
    if not PLATFORM_ENABLED:
        logger.warning(f"{PLATFORM.lower().capitalize()} scrap is disabled in configuration file.")
        return []

    session = CacheControl(requests.Session(), cache=FileCache("./cache"))

    if client:
        session = client
    try:
        url = f'{get_config().get("base_urls").get("github_public_path")}{get_conf_outputs().get("centers_json_path").format(PLATFORM.lower())}'
        response = session.get(url)
        # Si on ne vient pas des tests unitaires
        if not client:
            if response.from_cache:
                logger.info(f"Liste des centres pour {PLATFORM.lower().capitalize()} vient du cache")
            else:
                logger.info(f"Liste des centres pour {PLATFORM.lower().capitalize()} est une vraie requête")

        data = response.json()
        logger.info(f"Found {len(data)} {PLATFORM.lower().capitalize()} centers (external scraper).")
        for center in data:
            yield center
    except Exception as e:
        logger.warning(f"Unable to scrape {PLATFORM.lower().capitalize()} centers: {e}")
