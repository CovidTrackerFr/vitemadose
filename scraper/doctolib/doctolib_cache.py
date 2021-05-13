import re

import httpx

from scraper.error import BlockedByDoctolibError
from scraper.pattern.scraper_request import ScraperRequest
from scraper.pattern.scraper_result import DRUG_STORE, GENERAL_PRACTITIONER, VACCINATION_CENTER
from utils.vmd_config import get_conf_platform

DOCTOLIB_CONF = get_conf_platform("doctolib")
DOCTOLIB_API = DOCTOLIB_CONF.get("api", {})

BOOKING = {}


def get_center_booking(request: ScraperRequest, center: str, client: httpx.Client) -> dict:
    """
    Memory cache for booking requests. About 40% of centers are divided into subcenters
    on Doctolib, so we were making the same booking request for a lot these subcenters.
    """
    if center in BOOKING:
        return BOOKING.get(center)

    centre_api_url = DOCTOLIB_API.get("booking", "").format(centre=center)
    request.increase_request_count("booking")
    response = client.get(centre_api_url)

    if response.status_code == 403:
        raise BlockedByDoctolibError(centre_api_url)
    response.raise_for_status()
    data = response.json()
    BOOKING[center] = data

    file_object = open('test.txt', 'a')
    file_object.write(f"{center}\n")
    file_object.close()
    return data
