import httpx
from bs4 import BeautifulSoup
from urllib.parse import urlencode

from functools import wraps
from typing import NamedTuple, Optional
from datetime import datetime, timedelta, date

from utils.vmd_logger import get_logger
from utils.vmd_config import get_conf_platform
from scraper.pattern.scraper_request import ScraperRequest


CLIKODOC_CONF = get_conf_platform("clikodoc")
CLIKODOC_API = CLIKODOC_CONF.get("api", {})
CLIKODOC_DOCTORS_OPTIONS = CLIKODOC_CONF.get("doctors_options", {})
DEFAULT_SPECIALITY_ID = CLIKODOC_DOCTORS_OPTIONS.get("speciality_id", "9")
DEFAULT_CITY_ID = CLIKODOC_DOCTORS_OPTIONS.get("city_id", "0")
SLOT_LIMIT = CLIKODOC_CONF.get("slot_limit", 3)


class Token(NamedTuple):
    token: str
    expiration_date: datetime


_token: Optional[Token] = None


logger = get_logger()


timeout = httpx.Timeout(CLIKODOC_CONF.get("timeout", 25), connect=CLIKODOC_CONF.get("timeout", 25))
DEFAULT_CLIENT = httpx.Client(timeout=timeout)


def with_token(func, client: httpx.Client = DEFAULT_CLIENT):
    @wraps(func)
    def inner(*args, **kwargs):
        global _token
        now = datetime.now()

        if _token and _token.expiration_date < now:
            kwargs["token"] = _token.token
        else:
            logger.info("Retrieving token for Clikodoc")
            r = client.get(CLIKODOC_API.get("homepage", "https://www.clikodoc.com"))
            soup = BeautifulSoup(r.content, "html.parser")
            token = soup.find("input", {"name": "_token"})["value"]
            _token = Token(token, now + timedelta(days=1, seconds=-1))
            kwargs["token"] = token

        value = func(*args, **kwargs)
        return value

    return inner


@with_token
def get_doctors(
    client: httpx.Client = DEFAULT_CLIENT,
    speciality_id: str = DEFAULT_SPECIALITY_ID,
    city_id: str = DEFAULT_CITY_ID,
    token: Optional[str] = None,
) -> Optional[str]:
    url = CLIKODOC_API.get("doctors", "https://www.clikodoc.com/getDoctorsListForAllState")
    payload = {
        "state_id": 45,
        "city_id": city_id,
        "id": speciality_id,
        "type": "Speciality",
        "page": 1,
        "_token": token,
    }
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "X-CSRF-TOKEN": token,
        "X-Requested-With": "XMLHttpRequest",
    }

    try:
        r = client.post(url=url, data=urlencode(payload), headers=headers)
        r.raise_for_status()
    except httpx.TimeoutException as hex:
        logger.warning(f"request timed out for url: {url}")
        return None
    except httpx.HTTPStatusError as hex:
        logger.warning(f"{url} returned error {hex.response.status_code}")
        return None
    return r.json()


@with_token
def get_next_available_date(
    doctor_id: str, client: httpx.Client = DEFAULT_CLIENT, request: ScraperRequest = None, token: Optional[str] = None
) -> Optional[str]:
    url = CLIKODOC_API.get(
        "next_available_date", "https://www.clikodoc.com/foreapicntrl/nextavaildatelite?module=patients"
    )
    payload = {"doctorid": doctor_id}
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "X-CSRF-TOKEN": token,
        "X-Requested-With": "XMLHttpRequest",
    }

    if request:
        request.increase_request_count("booking")
    try:
        r = client.post(url=url, data=urlencode(payload), headers=headers)
        r.raise_for_status()
    except httpx.TimeoutException as hex:
        logger.warning(f"request timed out for url: {url}")
        if request:
            request.increase_request_count("time-out")
        return None
    except httpx.HTTPStatusError as hex:
        logger.warning(f"{url} returned error {hex.response.status_code}")
        if request:
            request.increase_request_count("error")
        return None
    return r.json()


@with_token
def get_slots(
    doctor_id: str,
    type_id: str,
    first_availability: date,
    client: httpx.Client = DEFAULT_CLIENT,
    request: ScraperRequest = None,
    token: Optional[str] = None,
) -> Optional[str]:
    url = CLIKODOC_API.get("slots", "https://www.clikodoc.com/getSlotsForBookingV2")
    payload = {
        "doctorid": doctor_id,
        "typeid": type_id,
        "from": first_availability.isoformat(),
        "to": (first_availability + timedelta(days=SLOT_LIMIT)).isoformat(),
        "slotfor": "next",
        "work_location_id": 0,
        "date_mandatory_value": "",
    }
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "X-CSRF-TOKEN": token,
        "X-Requested-With": "XMLHttpRequest",
    }

    if request:
        request.increase_request_count("slots")
    try:
        r = client.post(url, data=urlencode(payload), headers=headers)
        r.raise_for_status()
    except httpx.TimeoutException as hex:
        logger.warning(f"request timed out for url: {url} with doctor_id {doctor_id}")
        if request:
            request.increase_request_count("time-out")
        return None
    except httpx.HTTPStatusError as hex:
        logger.warning(f"{url} returned error {hex.response.status_code}")
        if request:
            request.increase_request_count("error")
        return None
    return r.json()


@with_token
def get_token(token: Optional[str] = None) -> Optional[str]:
    return token


if __name__ == "__main__":
    print(get_slots("43487", "13", date(2021, 6, 10)))
