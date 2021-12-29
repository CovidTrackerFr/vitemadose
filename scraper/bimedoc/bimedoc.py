import json
import time
import logging
import os
from typing import Dict, Iterator, Optional
import httpx
import requests
from scraper.circuit_breaker import ShortCircuit
from scraper.creneaux.creneau import Creneau, Lieu, Plateforme, PasDeCreneau
from scraper.pattern.vaccine import get_vaccine_name
from scraper.pattern.scraper_request import ScraperRequest
from scraper.profiler import Profiling
from utils.vmd_config import get_conf_platform, get_config, get_conf_outputs
from scraper.error import Blocked403
from utils.vmd_utils import DummyQueue, append_date_days
from typing import Dict, Iterator, List, Optional
import dateutil
from cachecontrol import CacheControl
from cachecontrol.caches.file_cache import FileCache
import datetime
from scraper.pattern.vaccine import Vaccine, get_vaccine_name

PLATFORM = "bimedoc".lower()

PLATFORM_CONF = get_conf_platform("bimedoc")
PLATFORM_ENABLED = PLATFORM_CONF.get("enabled", False)

BIMEDOC_HEADERS = {"Authorization": f'Partner {os.environ.get("BIMEDOC_API_KEY", "")}'}


BIMEDOC_APIs = PLATFORM_CONF.get("api", "")

SCRAPER_CONF = PLATFORM_CONF.get("center_scraper", {})
CENTER_LIST_URL = PLATFORM_CONF.get("api", {}).get("center_list", {})

NUMBER_OF_SCRAPED_DAYS = get_config().get("scrape_on_n_days", 28)


timeout = httpx.Timeout(PLATFORM_CONF.get("timeout", 30), connect=PLATFORM_CONF.get("timeout", 30))

BOOSTER_VACCINES = get_config().get("vaccines_allowed_for_booster", [])
VACCINE_CONF = get_config().get("vaccines", {})

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


@Profiling.measure("mesoigner_slot")
def fetch_slots(request: ScraperRequest, creneau_q=DummyQueue) -> Optional[str]:
    if not PLATFORM_ENABLED:
        return None
    # Fonction principale avec le comportement "de prod".
    bimedoc = BimedocSlots(client=DEFAULT_CLIENT, creneau_q=creneau_q)
    first_availability = bimedoc.fetch(request)
    return first_availability


def get_possible_dose_numbers(vaccine_name: str):

    if not vaccine_name:
        return []

    if any([vaccine for vaccine in BOOSTER_VACCINES if vaccine in vaccine_name]):
        return [1, 2, 3]
    return [1, 2]


class BimedocSlots:
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
        platform = request.center_info.plateforme
        center_id = gid.split(platform)[-1]
        start_date = datetime.date.today()
        end_date = start_date + datetime.timedelta(NUMBER_OF_SCRAPED_DAYS)

        self.lieu = Lieu(
            plateforme=Plateforme[PLATFORM.upper()],
            url=request.url,
            location=request.center_info.location,
            nom=request.center_info.nom,
            internal_id=request.internal_id,
            departement=request.center_info.departement,
            lieu_type=request.practitioner_type,
            metadata=request.center_info.metadata,
        )

        centre_api_url = BIMEDOC_APIs.get("slots", "").format(
            pharmacy_id=center_id, start_date=start_date, end_date=end_date
        )
        response = self._client.get(centre_api_url, headers=BIMEDOC_HEADERS)
        request.increase_request_count("slots")

        if response.status_code == 403:
            request.increase_request_count("error")
            self.found_creneau(PasDeCreneau(lieu=self.lieu))
            raise Blocked403(PLATFORM, centre_api_url)

        response.raise_for_status()
        rdata = response.json()

        if not rdata:
            self.found_creneau(PasDeCreneau(lieu=self.lieu))

        first_availability = self.get_appointments(request, rdata)
        if self.lieu and first_availability is None:
            self.found_creneau(PasDeCreneau(lieu=self.lieu))

        return first_availability

    def get_appointments(self, request: ScraperRequest, slots_api):
        first_availability = None

        if len(slots_api.get("slots", [])) == 0:
            self.found_creneau(PasDeCreneau(lieu=self.lieu))
            return None

        for creneau in slots_api.get("slots", []):
            dose_ranks = get_possible_dose_numbers(creneau["vaccine_name"])

            self.found_creneau(
                Creneau(
                    horaire=dateutil.parser.parse(creneau["datetime"]),
                    reservation_url=request.url,
                    dose=dose_ranks,
                    type_vaccin=get_vaccine_name(creneau["vaccine_name"]),
                    lieu=self.lieu,
                )
            )
            request.update_appointment_count(request.appointment_count + 1)

            if first_availability is None or creneau["datetime"] < first_availability:
                first_availability = creneau["datetime"]

            request.add_vaccine_type(get_vaccine_name(creneau["vaccine_name"]))

        return first_availability


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
