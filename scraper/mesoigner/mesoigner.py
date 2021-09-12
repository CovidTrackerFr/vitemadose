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


PLATFORM = "mesoigner"

PLATFORM_CONF = get_conf_platform("mesoigner")
PLATFORM_ENABLED = PLATFORM_CONF.get("enabled", False)
MESOIGNER_HEADERS = {
    "Authorization": f'Mesoigner apikey="{os.environ.get("MESOIGNER_API_KEY", "")}"',
}
MESOIGNER_APIs = PLATFORM_CONF.get("api", "")

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


@Profiling.measure("mesoigner_slot")
def fetch_slots(request: ScraperRequest, creneau_q=DummyQueue) -> Optional[str]:
    if not PLATFORM_ENABLED:
        return None
    # Fonction principale avec le comportement "de prod".
    mesoigner = MesoignerSlots(client=DEFAULT_CLIENT, creneau_q=creneau_q)
    return mesoigner.fetch(request)


class MesoignerSlots:
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
        start_date = request.get_start_date()

        self.lieu = Lieu(
            plateforme=Plateforme[PLATFORM.upper()],
            url=request.url,
            location=request.center_info.location,
            nom=request.center_info.nom,
            internal_id=f"mesoigner{request.internal_id}",
            departement=request.center_info.departement,
            lieu_type=request.practitioner_type,
            metadata=request.center_info.metadata,
        )

        centre_api_url = MESOIGNER_APIs.get("slots", "").format(id=center_id, start_date=start_date)
        response = self._client.get(centre_api_url, headers=MESOIGNER_HEADERS)
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

        if slots_api.get("total"):
            appointments_number += int(slots_api.get("total", 0))

        if len(slots_api.get("slots", [])) == 0:
            return None

        start_date = request.get_start_date()

        # print(slots_api.get("slots", []))
        for day in slots_api.get("slots", []):

            for day_date, appointments_infos in day.items():
                if len(appointments_infos) == 0:
                    continue

                for one_appointment_info in appointments_infos:
                    appointment_exact_date = one_appointment_info["slot_beginning"]

                    self.found_creneau(
                        Creneau(
                            horaire=dateutil.parser.parse(appointment_exact_date),
                            reservation_url=request.url,
                            type_vaccin=one_appointment_info["available_vaccines"],
                            lieu=self.lieu,
                        )
                    )
                    if first_availability is None or appointment_exact_date < first_availability:
                        first_availability = appointment_exact_date

                    for vaccine in one_appointment_info["available_vaccines"]:
                        request.add_vaccine_type(get_vaccine_name(vaccine))

        request.update_appointment_count(request.appointment_count + appointments_number)

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
