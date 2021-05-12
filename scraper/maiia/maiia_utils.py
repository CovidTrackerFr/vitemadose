import httpx
import json
import logging

from utils.vmd_config import get_conf_platform

MAIIA_CONF = get_conf_platform("maiia")
MAIIA_SCRAPER = MAIIA_CONF.get("center_scraper", {})

timeout = httpx.Timeout(MAIIA_CONF.get("timeout", 25), connect=MAIIA_CONF.get("timeout", 25))
DEFAULT_CLIENT = httpx.Client(timeout=timeout)
logger = logging.getLogger("scraper")

MAIIA_LIMIT = MAIIA_SCRAPER.get("centers_per_page")


def get_paged(url: str, limit: MAIIA_LIMIT, client: httpx.Client = DEFAULT_CLIENT) -> dict:
    result = dict()
    result["items"] = []
    result["total"] = 0
    page = 0
    loops = 0
    while loops <= result["total"]:
        base_url = f"{url}&limit={limit}&page={page}"
        try:
            r = client.get(base_url)
            r.raise_for_status()
        except httpx.HTTPStatusError as hex:
            logger.warning(f"{base_url} returned error {hex.response.status_code}")
            break
        try:
            payload = r.json()
        except json.decoder.JSONDecodeError as jde:
            logger.warning(f"{base_url} raised {jde}")
            break
        result["total"] = payload["total"]
        if not payload["items"]:
            break
        for item in payload.get("items"):
            result["items"].append(item)
        if len(result["items"]) >= result["total"]:
            break
        page += 1
        loops += 1
    return result
