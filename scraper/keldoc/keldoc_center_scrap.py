import json
import multiprocessing
import os
from typing import List, Optional

import httpx

from utils.vmd_config import get_conf_platform
from utils.vmd_logger import get_logger
from utils.vmd_utils import get_departements, department_urlify

KELDOC_CONF = get_conf_platform("keldoc")
KELDOC_API = KELDOC_CONF.get("api", {})
SCRAPER_CONF = KELDOC_CONF.get("center_scraper", {})
BASE_URL = KELDOC_API.get("scraper")

timeout = httpx.Timeout(KELDOC_CONF.get("timeout", 25), connect=KELDOC_CONF.get("timeout", 25))
KELDOC_ENABLED = KELDOC_CONF.get("enabled", False)
KELDOC_HEADERS = {
    "User-Agent": os.environ.get("KELDOC_API_KEY", ""),
}
DEFAULT_SESSION = httpx.Client(timeout=timeout, headers=KELDOC_HEADERS)
logger = get_logger()


class KeldocCenterScraper:
    def __init__(self, session: httpx.Client = DEFAULT_SESSION):
        self._session = session

    def run_departement_scrap(self, departement: str) -> list:
        logger.info(f"[Keldoc centers] Parsing pages of departement {departement} through department SEO link")
        centers_departements = self.parse_pages_departement(departement)
        if not centers_departements:
            return []
        return centers_departements

    def send_keldoc_request(self, url: str) -> Optional[dict]:
        try:
            req = self._session.get(url)
            req.raise_for_status()
            return req.json()
        except httpx.TimeoutException as hex:
            logger.warning(f"Keldoc request timed out: {url}")
            return None
        except httpx.HTTPStatusError as hex:
            logger.warning(f"Keldoc request returned HTTP code {hex.response.status_code}: {url}")
            return None
        except (httpx.RemoteProtocolError, httpx.ConnectError) as hex:
            logger.warning(f"Keldoc raise error {hex} for request: {url}")
            return None

    def parse_keldoc_resources(self, center: dict) -> Optional[dict]:
        resource_url = parse_keldoc_resource_url(center)
        if resource_url is None:
            return None
        resource_data = self.send_keldoc_request(resource_url)
        return resource_data

    def parse_keldoc_motive_categories(self, center_id: int, cabinets: list, specialties: list) -> list:
        """
        Fetch available motive categories from cabinet
        """
        for specialty_id in specialties:
            for cabinet in cabinets:
                cabinet_id = cabinet.get("id")
                motive_url = KELDOC_API.get("motives").format(center_id, specialty_id, cabinet_id)
                motive_data = self.send_keldoc_request(motive_url)
                cabinet["motive_categories"] = motive_data
        return cabinets

    def parse_keldoc_center(self, center: dict) -> Optional[dict]:
        data = {
            "name": center["title"],
            "rdv_site_web": f"https://keldoc.com{center['url']}",
            "cabinets": [],
            "specialties": center.get("specialty_ids", []),
        }
        data["resources"] = self.parse_keldoc_resources(center)
        if not data["resources"]:
            return None

        # Weird Keldoc management on cabinet IDs
        cabinets = get_cabinets(data["resources"])
        data["cabinets"] = self.parse_keldoc_motive_categories(center.get("id"), cabinets, data["specialties"])
        if not data["cabinets"]:
            return None
        return data

    def parse_pages_departement(self, departement: str, page_id: int = 1, centers: list = None) -> list:
        if not centers:
            centers = []
        logger.info(f"[Keldoc centers] Parsing page {page_id} of {departement}")
        formatted_departement = department_urlify(departement)
        url = (
            "https://www.keldoc.com/api/patients/v2/searches/geo_location?specialty_id=maladies-infectieuses"
            f"&raw_location={formatted_departement}&page={page_id}"
        )
        data = self.send_keldoc_request(url)

        options = data.get("options")
        if not options:
            return centers
        results = data.get("results")
        if not results:
            return centers

        sections = {key: value for key, value in results.items() if "section_" in key}
        for section_name, data in sections.items():
            data = data.get("data")
            if not data:
                continue
            for center_data in data:
                parsed_center = self.parse_keldoc_center(center_data)
                if parsed_center:
                    logger.info(f"Found center for dep. {departement}: {parsed_center.get('name')}")
                    centers.append(parsed_center)
                else:
                    logger.warning(f"Not enough resources for center in dep. {departement}: {center_data.get('title')}")

        # Keldoc provides us the info if there is a next page to explore,
        # it's much easier than testing an extra query.
        if options.get("next_page"):
            return self.parse_pages_departement(departement, page_id=1 + page_id, centers=centers)
        return centers


def fetch_department(department: str):
    scraper = KeldocCenterScraper()
    return scraper.run_departement_scrap(department)


def parse_keldoc_centers(page_limit=None) -> List[dict]:
    centers = []
    unique_center_urls = []

    with multiprocessing.Pool(50) as pool:
        center_lists = pool.imap_unordered(fetch_department, get_departements())
        centers = []

        for center_list in center_lists:
            centers.extend(center_list)

        for item in list(centers):
            if item.get("rdv_site_web") in unique_center_urls:
                centers.remove(item)
                continue
            unique_center_urls.append(item.get("rdv_site_web"))

        return centers


def parse_keldoc_resource_url(center: dict) -> Optional[str]:
    center_url = center.get("url")
    url_split = center_url.split("/")
    if len(url_split) < 4:
        return None
    type, location, slug = url_split[1:4]
    return f"{KELDOC_API.get('booking')}?type={type}&location={location}&slug={slug}"


def get_cabinets(resources: dict) -> list:
    if "cabinet" in resources:
        return [resources["cabinet"]]
    elif "cabinets" in resources:
        return resources["cabinets"]
    return []


if __name__ == "__main__":  # pragma: no cover
    if KELDOC_CONF.get("enabled", False):
        center_scraper = KeldocCenterScraper()
        centers = parse_keldoc_centers(center_scraper)
        path_out = SCRAPER_CONF.get("result_path")
        logger.info(f"Found {len(centers)} centers on Keldoc")
        if len(centers) < 90:
            # for reference, on 17-05, there were 97 centers
            logger.error(f"[NOT SAVING RESULTS] {len(centers)} does not seem like enough Keldoc centers")
        else:
            logger.info(f"> Writing them on {path_out}")
            with open(path_out, "w") as f:
                f.write(json.dumps(centers, indent=2))
    else:
        logger.error(f"Keldoc scraper is disabled in configuration file.")
        exit(1)
