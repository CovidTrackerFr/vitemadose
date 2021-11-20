import json
import logging
import httpx

import datetime as dt
from pytz import timezone

from typing import Dict, Iterator, List, Optional, Tuple, Set
from dateutil.parser import isoparse, parse
from urllib import parse as urlparse
from urllib.parse import quote, parse_qs
from typing import List, Optional, Tuple
from scraper.profiler import Profiling
from scraper.pattern.vaccine import get_vaccine_name
from scraper.pattern.scraper_request import ScraperRequest
from scraper.maiia.maiia_utils import get_paged, MAIIA_LIMIT, DEFAULT_CLIENT
from utils.vmd_config import get_conf_platform, get_config, get_conf_outputs
from utils.vmd_utils import DummyQueue
from scraper.creneaux.creneau import Creneau, Lieu, Plateforme, PasDeCreneau
import requests
from cachecontrol import CacheControl
from cachecontrol.caches.file_cache import FileCache

PLATFORM = "maiia".lower()
PLATFORM_CONF = get_conf_platform("maiia")
PLATFORM_API = PLATFORM_CONF.get("api", {})
PLATFORM_ENABLED = PLATFORM_CONF.get("enabled", False)
PLATFORM_SCRAPER = PLATFORM_CONF.get("center_scraper", {})

# timeout = httpx.Timeout(PLATFORM_CONF.get("timeout", 25), connect=PLATFORM_CONF.get("timeout", 25))

logger = logging.getLogger("scraper")
paris_tz = timezone("Europe/Paris")

MAIIA_URL = PLATFORM_CONF.get("base_url")
NUMBER_OF_SCRAPED_DAYS = get_config().get("scrape_on_n_days", 28)

MAIIA_DOSES = PLATFORM_SCRAPER.get("dose_types")


def fetch_slots(request: ScraperRequest, creneau_q=DummyQueue, client: httpx.Client = DEFAULT_CLIENT) -> Optional[str]:
    if not PLATFORM_ENABLED:
        return None

    # Fonction principale avec le comportement "de prod".
    maiia = MaiiaSlots(creneau_q, client)
    return maiia.fetch(request)


class MaiiaSlots:
    # Permet de passer un faux client HTTP,
    # pour éviter de vraiment appeler Doctolib lors des tests.

    def __init__(self, creneau_q, client):
        self.creneau_q = creneau_q
        self._client = DEFAULT_CLIENT if client is None else client
        self.lieu = None

    def found_creneau(self, creneau):
        self.creneau_q.put(creneau)

    def fetch(self, request: ScraperRequest) -> Optional[str]:
        result = self._fetch(request)
        if result is None and self.lieu:
            self.found_creneau(PasDeCreneau(lieu=self.lieu, phone_only=request.appointment_by_phone_only))

        return result

    def found_creneau(self, creneau):
        self.creneau_q.put(creneau)

    @Profiling.measure("maiia_slot")
    def _fetch(self, request: ScraperRequest, creneau_q=DummyQueue()) -> Optional[str]:
        if not PLATFORM_ENABLED:
            return None
        url = request.get_url()
        start_date = request.get_start_date()
        url_query = parse_qs(urlparse.urlparse(url).query)
        if "centerid" not in url_query:
            logger.warning(f"No centerId in fetch url: {url}")
            return None
        center_id = url_query["centerid"][0]

        reasons = get_reasons(center_id, self._client, request=request)
        if not reasons:
            return None
        self.lieu = Lieu(
            plateforme=Plateforme[PLATFORM.upper()],
            url=request.url,
            location=request.center_info.location,
            nom=request.center_info.nom,
            internal_id=f"maiia{request.internal_id}",
            departement=request.center_info.departement,
            lieu_type=request.practitioner_type,
            metadata=request.center_info.metadata,
        )
        first_availability, slots_count = self.get_first_availability(
            center_id, start_date, reasons, client=self._client, request=request
        )
        if first_availability is None:
            if self.lieu:
                self.found_creneau(PasDeCreneau(lieu=self.lieu, phone_only=request.appointment_by_phone_only))
            return None

        for reason in reasons:
            request.add_vaccine_type(get_vaccine_name(reason["name"]))
        request.update_internal_id(f"maiia{center_id}")
        request.update_appointment_count(slots_count)
        return first_availability.isoformat()

    def parse_slots(self, slots: list, request: ScraperRequest, dose: int = None) -> Optional[dt.datetime]:
        if not slots:
            return None
        first_availability = None
        for slot in slots:
            self.found_creneau(
                Creneau(
                    horaire=parse(slot["startDateTime"]),
                    reservation_url=request.url,
                    type_vaccin=[slot.get("vaccine_type")],
                    lieu=self.lieu,
                    dose=dose,
                )
            )

            start_date_time = isoparse(slot["startDateTime"])
            if first_availability is None or start_date_time < first_availability:
                first_availability = start_date_time
        return first_availability

    def get_next_slot_date(
        self,
        center_id: str,
        consultation_reason_name: str,
        start_date: str,
        client: httpx.Client = DEFAULT_CLIENT,
        request: ScraperRequest = None,
    ) -> Optional[str]:
        url = PLATFORM_API.get("next_slot").format(
            center_id=center_id, consultation_reason_name=consultation_reason_name, start_date=start_date
        )
        if request:
            request.increase_request_count("next-slots")
        try:
            r = client.get(url)
            r.raise_for_status()
        except httpx.HTTPStatusError as hex:
            logger.warning(f"{url} returned error {hex.response.status_code}")
            request.increase_request_count("error")
            return None
        result = r.json()
        if "firstPhysicalStartDateTime" in result:
            return result["firstPhysicalStartDateTime"]
        return None

    def get_slots(
        self,
        center_id: str,
        consultation_reason_name: str,
        start_date: str,
        end_date: str,
        limit=MAIIA_LIMIT,
        client: httpx.Client = DEFAULT_CLIENT,
        request: ScraperRequest = None,
    ) -> Optional[list]:
        url = PLATFORM_API.get("slots").format(
            center_id=center_id,
            consultation_reason_name=consultation_reason_name,
            start_date=start_date,
            end_date=end_date,
        )
        availabilities = get_paged(url, limit=limit, client=client, request=request, request_type="slots")["items"]
        if not availabilities:
            next_slot_date = self.get_next_slot_date(
                center_id, consultation_reason_name, start_date, client=client, request=request
            )
            if not next_slot_date:
                return None
            next_date = dt.datetime.strptime(next_slot_date, "%Y-%m-%dT%H:%M:%S.%fZ")
            if next_date - isoparse(start_date) > dt.timedelta(days=NUMBER_OF_SCRAPED_DAYS):
                return None
            start_date = next_date.isoformat()
            url = PLATFORM_API.get("slots").format(
                center_id=center_id,
                consultation_reason_name=consultation_reason_name,
                start_date=start_date,
                end_date=end_date,
            )
            availabilities = get_paged(url, limit=limit, client=client, request=request, request_type="slots")["items"]
        if availabilities:
            return availabilities
        return None

    def count_slots(self, slots: list, start_date: str, end_date: str) -> int:
        logger.debug(f"counting slots from {start_date} to {end_date}")
        paris_tz = timezone("Europe/Paris")
        start_dt = isoparse(start_date).astimezone(paris_tz)
        end_dt = isoparse(end_date).astimezone(paris_tz)
        count = 0

        for slot in slots:
            if "startDateTime" not in slot:
                continue
            slot_dt = isoparse(slot["startDateTime"]).astimezone(paris_tz)
            if start_dt < slot_dt < end_dt:
                count += 1
        return count

    def get_first_availability(
        self,
        center_id: str,
        request_date: str,
        reasons: List[dict],
        client: httpx.Client = DEFAULT_CLIENT,
        request: ScraperRequest = None,
    ) -> Tuple[Optional[dt.datetime], int, dict]:
        date = isoparse(request_date).replace(tzinfo=None)
        start_date = date.isoformat()
        end_date = (date + dt.timedelta(days=NUMBER_OF_SCRAPED_DAYS)).isoformat()
        first_availability = None
        slots_count = 0
        for consultation_reason in reasons:
            consultation_reason_name_quote = quote(consultation_reason.get("name"), "")
            if "injectionType" in consultation_reason:
                slots = self.get_slots(
                    center_id, consultation_reason_name_quote, start_date, end_date, client=client, request=request
                )
                dose = None
                dose_name = consultation_reason["injectionType"]

                if dose_name and dose_name!= "NONE":
                    dose = MAIIA_DOSES[dose_name]

                if slots:
                    for slot in slots:
                        slot["vaccine_type"] = get_vaccine_name(consultation_reason.get("name"))
                slot_availability = self.parse_slots(slots, request, dose)
                if slot_availability is None:
                    continue
                slots_count += len(slots)
                if first_availability == None or slot_availability < first_availability:
                    first_availability = slot_availability
        return first_availability, slots_count


def get_reasons(
    center_id: str, limit=MAIIA_LIMIT, client: httpx.Client = DEFAULT_CLIENT, request: ScraperRequest = None
) -> list:
    url = PLATFORM_API.get("motives").format(center_id=center_id)
    result = get_paged(url, limit=limit, client=client, request=request, request_type="motives")
    if not result["total"]:
        return []
    return result.get("items", [])


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
