import json
import logging
import httpx

import datetime as dt
from pytz import timezone

import requests
from dateutil.parser import isoparse
from urllib import parse as urlparse
from urllib.parse import quote, parse_qs
from typing import List, Optional, Tuple

from scraper.profiler import Profiling
from scraper.pattern.center_info import INTERVAL_SPLIT_DAYS, CHRONODOSES
from scraper.pattern.vaccine import get_vaccine_name
from scraper.pattern.scraper_request import ScraperRequest
from scraper.maiia.maiia_utils import get_paged, MAIIA_LIMIT, DEFAULT_CLIENT
from utils.vmd_config import get_conf_platform, get_config

MAIIA_CONF = get_conf_platform("maiia")
MAIIA_API = MAIIA_CONF.get("api", {})
MAIIA_ENABLED = MAIIA_CONF.get("enabled", False)
MAIIA_SCRAPER = MAIIA_CONF.get("center_scraper", {})

# timeout = httpx.Timeout(MAIIA_CONF.get("timeout", 25), connect=MAIIA_CONF.get("timeout", 25))

logger = logging.getLogger("scraper")
paris_tz = timezone("Europe/Paris")

MAIIA_URL = MAIIA_CONF.get("base_url")
MAIIA_DAY_LIMIT = MAIIA_CONF.get("calendar_limit", 50)


def parse_slots(slots: list) -> Optional[dt.datetime]:
    if not slots:
        return None
    first_availability = None
    for slot in slots:
        start_date_time = isoparse(slot["startDateTime"])
        if first_availability is None or start_date_time < first_availability:
            first_availability = start_date_time
    return first_availability


def count_slots(slots: list, start_date: str, end_date: str) -> int:
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


def get_next_slot_date(
    center_id: str,
    consultation_reason_name: str,
    start_date: str,
    client: httpx.Client = DEFAULT_CLIENT,
    request: ScraperRequest = None,
) -> Optional[str]:
    url = MAIIA_API.get("next_slot").format(
        center_id=center_id, consultation_reason_name=consultation_reason_name, start_date=start_date
    )
    if request:
        request.increase_request_count("next-slots")
    try:
        r = client.get(url)
        r.raise_for_status()
    except httpx.HTTPStatusError as hex:
        logger.warning(f"{url} returned error {hex.response.status_code}")
        return None
    result = r.json()
    if "firstPhysicalStartDateTime" in result:
        return result["firstPhysicalStartDateTime"]
    return None


def get_slots(
    center_id: str,
    consultation_reason_name: str,
    start_date: str,
    end_date: str,
    limit=MAIIA_LIMIT,
    client: httpx.Client = DEFAULT_CLIENT,
    request: ScraperRequest = None,
) -> Optional[list]:
    url = MAIIA_API.get("slots").format(
        center_id=center_id, consultation_reason_name=consultation_reason_name, start_date=start_date, end_date=end_date
    )
    availabilities = get_paged(url, limit=limit, client=client, request=request, request_type="slots")["items"]
    if not availabilities:
        next_slot_date = get_next_slot_date(
            center_id, consultation_reason_name, start_date, client=client, request=request
        )
        if not next_slot_date:
            return None
        next_date = dt.datetime.strptime(next_slot_date, "%Y-%m-%dT%H:%M:%S.%fZ")
        if next_date - isoparse(start_date) > dt.timedelta(days=MAIIA_DAY_LIMIT):
            return None
        start_date = next_date.isoformat()
        url = MAIIA_API.get("slots").format(
            center_id=center_id,
            consultation_reason_name=consultation_reason_name,
            start_date=start_date,
            end_date=end_date,
        )
        availabilities = get_paged(url, limit=limit, client=client, request=request, request_type="slots")["items"]
    if availabilities:
        return availabilities
    return None


def get_reasons(
    center_id: str, limit=MAIIA_LIMIT, client: httpx.Client = DEFAULT_CLIENT, request: ScraperRequest = None
) -> list:
    url = MAIIA_API.get("motives").format(center_id=center_id)
    result = get_paged(url, limit=limit, client=client, request=request, request_type="motives")
    if not result["total"]:
        return []
    return result.get("items", [])


def get_first_availability(
    center_id: str,
    request_date: str,
    reasons: List[dict],
    client: httpx.Client = DEFAULT_CLIENT,
    request: ScraperRequest = None,
) -> Tuple[Optional[dt.datetime], int, dict]:
    date = isoparse(request_date).replace(tzinfo=None)
    start_date = date.isoformat()
    end_date = (date + dt.timedelta(days=MAIIA_DAY_LIMIT)).isoformat()
    first_availability = None
    slots_count = 0
    appointment_schedules = []
    counts = {}
    counts["chronodose"] = 0
    for n in INTERVAL_SPLIT_DAYS:
        counts[f"{n}_days"] = 0
    datenow = dt.datetime.now()
    for consultation_reason in reasons:
        consultation_reason_name_quote = quote(consultation_reason.get("name"), "")
        if "injectionType" in consultation_reason and consultation_reason["injectionType"] in ["FIRST"]:
            slots = get_slots(
                center_id, consultation_reason_name_quote, start_date, end_date, client=client, request=request
            )
            slot_availability = parse_slots(slots)
            if slot_availability is None:
                continue
            for n in (
                INTERVAL_SPLIT_DAY
                for INTERVAL_SPLIT_DAY in INTERVAL_SPLIT_DAYS
                if INTERVAL_SPLIT_DAY <= MAIIA_DAY_LIMIT
            ):
                n_date = (isoparse(start_date) + dt.timedelta(days=n, seconds=-1)).isoformat()
                counts[f"{n}_days"] += count_slots(slots, start_date, n_date)
            slots_count += len(slots)
            if get_vaccine_name(consultation_reason["name"]) in CHRONODOSES["Vaccine"]:
                current_date = (paris_tz.localize(datenow + dt.timedelta(days=0))).isoformat()
                n_date = (datenow + dt.timedelta(days=1, seconds=-1)).isoformat()
                counts["chronodose"] += count_slots(slots, current_date, n_date)
            if first_availability == None or slot_availability < first_availability:
                first_availability = slot_availability
    current_date = (paris_tz.localize(datenow + dt.timedelta(days=0))).isoformat()
    start_date = (paris_tz.localize(date)).isoformat()
    n_date = (paris_tz.localize(datenow + dt.timedelta(days=1, seconds=-1))).isoformat()
    appointment_schedules.append(
        {"name": "chronodose", "from": current_date, "to": n_date, "total": counts["chronodose"]}
    )
    for n in INTERVAL_SPLIT_DAYS:
        n_date = (paris_tz.localize(date + dt.timedelta(days=n, seconds=-1))).isoformat()
        appointment_schedules.append(
            {"name": f"{n}_days", "from": start_date, "to": n_date, "total": counts[f"{n}_days"]}
        )
    logger.debug(f"appointment_schedules: {appointment_schedules}")
    return first_availability, slots_count, appointment_schedules


@Profiling.measure("maiia_slot")
def fetch_slots(request: ScraperRequest, client: httpx.Client = DEFAULT_CLIENT) -> Optional[str]:
    if not MAIIA_ENABLED:
        return None
    url = request.get_url()
    start_date = request.get_start_date()
    url_query = parse_qs(urlparse.urlparse(url).query)
    if "centerid" not in url_query:
        logger.warning(f"No centerId in fetch url: {url}")
        return None
    center_id = url_query["centerid"][0]

    reasons = get_reasons(center_id, client=client, request=request)
    if not reasons:
        return None

    first_availability, slots_count, appointment_schedules = get_first_availability(
        center_id, start_date, reasons, client=client, request=request
    )
    if first_availability is None:
        return None

    for reason in reasons:
        request.add_vaccine_type(get_vaccine_name(reason["name"]))
    request.update_internal_id(f"maiia{center_id}")
    request.update_appointment_count(slots_count)
    request.update_appointment_schedules(appointment_schedules)
    return first_availability.isoformat()


def centre_iterator(overwrite_centers_file=True):
    if not MAIIA_ENABLED:
        return None
    try:
        center_path = MAIIA_SCRAPER.get("result_path")
        data_auto = get_config().get("data-auto", {}).get("base_url")
        url = f"{data_auto}{center_path}"
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        if overwrite_centers_file:
            with open(center_path, "w") as f:
                f.write(json.dumps(data, indent=2))
        logger.info(f"Found {len(data)} Maiia centers (external scraper).")
        for center in data:
            yield center
    except Exception as e:
        logger.warning(f"Unable to scrape Maiia centers: {e}")
