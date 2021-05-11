import json
import logging
import httpx

from datetime import datetime, timedelta
from pytz import timezone

import requests
from dateutil.parser import isoparse
from pathlib import Path
from urllib import parse as urlparse
from urllib.parse import quote, parse_qs
from typing import Optional, Tuple, Iterator, List

from scraper.profiler import Profiling
from scraper.pattern.center_info import get_vaccine_name, Vaccine, INTERVAL_SPLIT_DAYS, CHRONODOSES
from scraper.pattern.scraper_request import ScraperRequest
from scraper.maiia.maiia_utils import get_paged, MAIIA_LIMIT

timeout = httpx.Timeout(30.0, connect=30.0)
DEFAULT_CLIENT = httpx.Client(timeout=timeout)
logger = logging.getLogger("scraper")
paris_tz = timezone("Europe/Paris")

MAIIA_URL = "https://www.maiia.com"
MAIIA_DAY_LIMIT = 50


def parse_slots(slots: list) -> Optional[datetime]:
    if not slots:
        return None
    first_availability = None
    for slot in slots:
        start_date_time = isoparse(slot["startDateTime"])
        if first_availability == None or start_date_time < first_availability:
            first_availability = start_date_time
    return first_availability


def count_slots(slots: list, start_date: str, end_date: str) -> int:
    logger.debug(f"couting slots from {start_date} to {end_date}")
    paris_tz = timezone("Europe/Paris")
    start_dt = isoparse(start_date).astimezone(paris_tz)
    end_dt = isoparse(end_date).astimezone(paris_tz)
    count = 0

    for slot in slots:
        if "startDateTime" not in slot:
            continue
        slot_dt = isoparse(slot["startDateTime"]).astimezone(paris_tz)
        if slot_dt > start_dt and slot_dt < end_dt:
            count += 1

    return count


def get_next_slot_date(
    center_id: str, consultation_reason_name: str, start_date: str, client: httpx.Client = DEFAULT_CLIENT
) -> Optional[str]:
    url = f"{MAIIA_URL}/api/pat-public/availability-closests?centerId={center_id}&consultationReasonName={consultation_reason_name}&from={start_date}"
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
    limit: int = MAIIA_LIMIT,
    client: httpx.Client = DEFAULT_CLIENT,
) -> Optional[list]:
    url = f"{MAIIA_URL}/api/pat-public/availabilities?centerId={center_id}&consultationReasonName={consultation_reason_name}&from={start_date}&to={end_date}"
    availabilities = get_paged(url, limit=limit, client=client)["items"]
    if not availabilities:
        next_slot_date = get_next_slot_date(center_id, consultation_reason_name, start_date, client=client)
        if not next_slot_date:
            return None
        next_date = datetime.strptime(next_slot_date, "%Y-%m-%dT%H:%M:%S.%fZ")
        if next_date - isoparse(start_date) > timedelta(days=MAIIA_DAY_LIMIT):
            return None
        start_date = next_date.isoformat()
        url = f"{MAIIA_URL}/api/pat-public/availabilities?centerId={center_id}&consultationReasonName={consultation_reason_name}&from={start_date}&to={end_date}"
        availabilities = get_paged(url, limit=limit, client=client)["items"]
    if availabilities:
        return availabilities
    return None


def get_reasons(center_id: str, limit: int = MAIIA_LIMIT, client: httpx.Client = DEFAULT_CLIENT) -> list:
    url = f"{MAIIA_URL}/api/pat-public/consultation-reason-hcd?rootCenterId={center_id}"
    result = get_paged(url, limit=limit, client=client)
    if not result["total"]:
        return []
    return result.get("items", [])


def get_first_availability(
    center_id: str, request_date: str, reasons: List[dict], client: httpx.Client = DEFAULT_CLIENT
) -> Tuple[Optional[datetime], int, List[dict]]:
    date = isoparse(request_date).replace(tzinfo=None)
    start_date = date.isoformat()
    end_date = (date + timedelta(days=MAIIA_DAY_LIMIT)).isoformat()
    first_availability = None
    slots_count = 0
    appointment_schedules = []
    counts = {}
    counts["chronodose"] = 0
    for n in INTERVAL_SPLIT_DAYS:
        counts[f"{n}_days"] = 0
    for consultation_reason in reasons:
        consultation_reason_name_quote = quote(consultation_reason.get("name"), "")
        if "injectionType" in consultation_reason and consultation_reason["injectionType"] in ["FIRST"]:
            slots = get_slots(center_id, consultation_reason_name_quote, start_date, end_date, client=client)
            slot_availability = parse_slots(slots)
            if slot_availability == None:
                continue
            for n in (
                INTERVAL_SPLIT_DAY
                for INTERVAL_SPLIT_DAY in INTERVAL_SPLIT_DAYS
                if INTERVAL_SPLIT_DAY <= MAIIA_DAY_LIMIT
            ):
                n_date = (isoparse(start_date) + timedelta(days=n, seconds=-1)).isoformat()
                counts[f"{n}_days"] += count_slots(slots, start_date, n_date)
            slots_count += len(slots)
            if get_vaccine_name(consultation_reason["name"]) in CHRONODOSES["Vaccine"]:
                n_date = (isoparse(start_date) + timedelta(days=CHRONODOSES["Interval"], seconds=-1)).isoformat()
                counts["chronodose"] += count_slots(slots, start_date, n_date)
            if first_availability == None or slot_availability < first_availability:
                first_availability = slot_availability
    start_date = (paris_tz.localize(date)).isoformat()
    n_date = (paris_tz.localize(date + timedelta(days=2, seconds=-1))).isoformat()
    appointment_schedules.append(
        {"name": "chronodose", "from": start_date, "to": n_date, "total": counts["chronodose"]}
    )
    for n in INTERVAL_SPLIT_DAYS:
        n_date = (paris_tz.localize(date + timedelta(days=n, seconds=-1))).isoformat()
        appointment_schedules.append(
            {"name": f"{n}_days", "from": start_date, "to": n_date, "total": counts[f"{n}_days"]}
        )
    logger.debug(f"appointment_schedules: {appointment_schedules}")
    return first_availability, slots_count, appointment_schedules


@Profiling.measure("maiia_slot")
def fetch_slots(request: ScraperRequest, client: httpx.Client = DEFAULT_CLIENT) -> Optional[str]:
    url = request.get_url()
    start_date = request.get_start_date()
    url_query = parse_qs(urlparse.urlparse(url).query)
    if "centerid" not in url_query:
        logger.warning(f"No centerId in fetch url: {url}")
        return None
    center_id = url_query["centerid"][0]

    reasons = get_reasons(center_id, client=client)
    if not reasons:
        return None

    first_availability, slots_count, appointment_schedules = get_first_availability(
        center_id, start_date, reasons, client=client
    )
    if first_availability == None:
        return None

    for reason in reasons:
        request.add_vaccine_type(get_vaccine_name(reason["name"]))
    request.update_internal_id(f"maiia{center_id}")
    request.update_appointment_count(slots_count)
    request.update_appointment_schedules(appointment_schedules)
    return first_availability.isoformat()


def centre_iterator() -> Iterator[dict]:
    try:
        center_path = "data/output/maiia_centers.json"
        url = f"https://raw.githubusercontent.com/CovidTrackerFr/vitemadose/data-auto/{center_path}"
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        file = open(center_path, "w")
        file.write(json.dumps(data, indent=2))
        file.close()
        logger.info(f"Found {len(data)} Maiia centers (external scraper).")
        for center in data:
            yield center
    except Exception as e:
        logger.warning(f"Unable to scrape Maiia centers: {e}")
