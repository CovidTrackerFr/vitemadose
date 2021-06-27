import json
from scraper.doctolib.doctolib import build_appointment_schedules
import time
import logging
import os
from typing import Dict, Iterator, Optional
import httpx
import requests
from scraper.circuit_breaker import ShortCircuit
from scraper.pattern.vaccine import get_vaccine_name
from scraper.pattern.scraper_request import ScraperRequest
from scraper.profiler import Profiling
from utils.vmd_config import get_conf_platform
from scraper.error import BlockedByMesoignerError
from utils.vmd_utils import append_date_days
from scraper.pattern.center_info import INTERVAL_SPLIT_DAYS, CHRONODOSES
from typing import Dict, Iterator, List, Optional

MESOIGNER_CONF = get_conf_platform("mesoigner")
MESOIGNER_ENABLED = MESOIGNER_CONF.get("enabled", False)
MESOIGNER_HEADERS = {
    "Authorization": f'Mesoigner apikey={os.environ.get("MESOIGNER_API_KEY", "")}',
}
MESOIGNER_APIs = MESOIGNER_CONF.get("api", "")

SCRAPER_CONF = MESOIGNER_CONF.get("center_scraper", {})
CENTER_LIST_URL = MESOIGNER_CONF.get("api", {}).get("center_list", {})

timeout = httpx.Timeout(MESOIGNER_CONF.get("timeout", 30), connect=MESOIGNER_CONF.get("timeout", 30))

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
def fetch_slots(request: ScraperRequest, creneaux_q=None) -> Optional[str]:

    if not MESOIGNER_CONF.get("enabled", False):
        return None
    # Fonction principale avec le comportement "de prod".
    mesoigner = MesoignerSlots(client=DEFAULT_CLIENT)
    return mesoigner.fetch(request)


class MesoignerSlots:
    def __init__(self, client: httpx.Client = None, cooldown_interval=MESOIGNER_CONF.get("request_sleep", 0.1)):
        self._cooldown_interval = cooldown_interval
        self._client = DEFAULT_CLIENT if client is None else client
        self.lieu = None

    def fetch(self, request: ScraperRequest) -> Optional[str]:
        result = self._fetch(request)
        return result

    def _fetch(self, request: ScraperRequest) -> Optional[str]:
        gid = request.center_info.internal_id
        platform = request.center_info.plateforme
        center_id = gid.split(platform)[-1]
        start_date = request.get_start_date()

        centre_api_url = MESOIGNER_APIs.get("slots", "").format(id=center_id, start_date=start_date)
        response = self._client.get(centre_api_url, headers=MESOIGNER_HEADERS)
        request.increase_request_count("slots")

        if response.status_code == 403:
            request.increase_request_count("error")
            raise BlockedByMesoignerError(centre_api_url)

        response.raise_for_status()
        time.sleep(self._cooldown_interval)
        rdata = response.json()

        first_availability = self.get_appointments(request, rdata)
        return first_availability

    def build_appointment_schedules(
        request,
        interval: int,
        start_date: str,
        end_date: str,
        count: int,
        appointment_schedules: Optional[List[dict]],
        chronodose=False,
    ) -> List[dict]:
        if appointment_schedules is None:
            appointment_schedules = []
        if isinstance(appointment_schedules, list) and len(appointment_schedules) > 0:
            for appointment in appointment_schedules:
                if appointment["name"] == f"{interval}_days":
                    appointment["total"] += count

        if not any(appointment["name"] == f"{interval}_days" for appointment in appointment_schedules):
            appointment_schedules.append(
                {
                    "name": f"{interval}_days",
                    "from": start_date,
                    "to": end_date,
                    "total": count,
                }
            )

        if chronodose:
            if isinstance(appointment_schedules, list) and len(appointment_schedules) > 0:
                for appointment in appointment_schedules:
                    if appointment["name"] == "chronodose":
                        appointment["total"] += count

            if not any(appointment["name"] == "chronodose" for appointment in appointment_schedules):
                appointment_schedules.append(
                    {
                        "name": "chronodose",
                        "from": start_date,
                        "to": end_date,
                        "total": count,
                    }
                )

        return appointment_schedules

    def get_appointments(self, request: ScraperRequest, slots_api):
        appointments_number = 0
        first_availability = None
        appointment_schedules = None

        if slots_api.get("total"):
            appointments_number += int(slots_api.get("total", 0))

        if len(slots_api.get("slots", [])) == 0:
            return None

        start_date = request.get_start_date()

        for interval in INTERVAL_SPLIT_DAYS:
            chronodose = False
            if interval == CHRONODOSES["Interval"]:
                chronodose = True
            appointment_schedules = build_appointment_schedules(
                request,
                interval,
                append_date_days(start_date, 0),
                append_date_days(start_date, days=interval, seconds=-1),
                0,
                appointment_schedules,
                chronodose,
            )
        request.update_appointment_schedules(appointment_schedules)

        for day in slots_api.get("slots", []):

            for day_date, appointments_infos in day.items():
                if len(appointments_infos) == 0:
                    continue

                for one_appointment_info in appointments_infos:
                    appointment_exact_date = one_appointment_info["slot_beginning"]
                    if first_availability is None or appointment_exact_date < first_availability:
                        first_availability = appointment_exact_date

                    request.add_vaccine_type(
                        [get_vaccine_name(vaccine) for vaccine in one_appointment_info["available_vaccines"]]
                    )

                for interval in INTERVAL_SPLIT_DAYS:
                    chronodose = False
                    if interval == CHRONODOSES["Interval"]:
                        chronodose = True
                    appointment_schedules = build_appointment_schedules(
                        request,
                        interval,
                        append_date_days(start_date, 0),
                        append_date_days(start_date, days=interval, seconds=-1),
                        sum(one_appointment_info["number_of_slots"] for one_appointment_info in appointments_infos)
                        if day_date <= append_date_days(start_date, days=interval, seconds=-1)
                        else 0,
                        appointment_schedules,
                        chronodose,
                    )
        request.update_appointment_schedules(appointment_schedules)

        request.update_appointment_count(request.appointment_count + appointments_number)

        return first_availability


def center_iterator() -> Iterator[Dict]:
    if not MESOIGNER_CONF["enabled"]:
        return
    try:
        center_path = "data/output/mesoigner_centers.json"
        url = f"https://raw.githubusercontent.com/CovidTrackerFr/vitemadose/data-auto/{center_path}"
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        file = open(center_path, "w")
        file.write(json.dumps(data, indent=2))
        file.close()
        logger.info(f"Found {len(data)} mesoigner centers (external scraper).")
        for center in data:
            yield center
    except Exception as e:
        logger.warning(f"Unable to scrape mesoigner centers: {e}")
