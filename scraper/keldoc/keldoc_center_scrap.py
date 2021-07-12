import json
import multiprocessing
import os
from typing import List, Optional
import requests
import httpx
import csv
from utils.vmd_config import get_conf_platform, get_conf_inputs
from utils.vmd_logger import get_logger
from utils.vmd_utils import department_urlify, departementUtils
import pprint
from scraper.pattern.center_location import CenterLocation

KELDOC_CONF = get_conf_platform("keldoc")
KELDOC_API = KELDOC_CONF.get("api", {})
SCRAPER_CONF = KELDOC_CONF.get("center_scraper", {})
CENTER_DETAILS = KELDOC_API.get("center_details")
KELDOC_FILTERS = KELDOC_CONF.get("filters", {})
KELDOC_COVID_SPECIALTIES_URLS = KELDOC_FILTERS.get("appointment_speciality_urls", [])


timeout = httpx.Timeout(KELDOC_CONF.get("timeout", 25), connect=KELDOC_CONF.get("timeout", 25))
KELDOC_ENABLED = KELDOC_CONF.get("enabled", False)
KELDOC_HEADERS = {
    "User-Agent": os.environ.get("KELDOC_API_KEY", ""),
}
DEFAULT_SESSION = httpx.Client(timeout=timeout, headers=KELDOC_HEADERS)

KELDOC_WEIRD_DEPS = KELDOC_CONF.get("dep_conversion", "")
KELDOC_MISSING_DEPS = KELDOC_CONF.get("missing_deps", "")

logger = get_logger()


def get_departements() -> List[str]:
    with open(get_conf_inputs()["departements"], encoding="utf8", newline="\n") as csvfile:
        reader = list(csv.DictReader(csvfile, delimiter=","))

        departements = [
            f'{department_urlify(row["nom_departement"])}-{row["code_departement"]}'
            if row["nom_departement"] not in KELDOC_WEIRD_DEPS
            else f'{department_urlify(KELDOC_WEIRD_DEPS[row["nom_departement"]])}-{row["code_departement"]}'
            for row in reader
        ]
        departements = departements + KELDOC_MISSING_DEPS
        return departements


def set_center_type(center_type: str):
    center_types = SCRAPER_CONF.get("center_types", {})
    if center_type in center_types.keys():
        return center_types[center_type]


class KeldocCenterScraper:
    def __init__(self, vaccination_url_path=None, session: httpx.Client = DEFAULT_SESSION):
        self._session = session
        self.vaccination_url_path = vaccination_url_path

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
        motive_url = CENTER_DETAILS.format(center.get("id"))
        motive_data = requests.get(motive_url).json()
        phone_number = None
        if "phone_number" in motive_data:
            phone_number = motive_data["phone_number"]

        data = {
            "nom": center["title"],
            "rdv_site_web": f"https://keldoc.com{center['url']}",
            "cabinets": [],
            "specialties": center.get("specialty_ids", []),
            "com_insee": departementUtils.cp_to_insee(center["cabinet"]["zipcode"]),
            "gid": center["id"],
            "address": center["cabinet"]["location"].strip(),
            "lat_coor1": center["coordinates"].split(",")[0],
            "long_coor1": center["coordinates"].split(",")[1],
            "city": center["cabinet"]["city"].strip(),
            "type": set_center_type(center["type"]),
            "phone_number": phone_number,
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
        url = KELDOC_API.get("center_list").format(
            motive=self.vaccination_url_path, dep=formatted_departement, page_id=page_id
        )
        data = self.send_keldoc_request(url)

        if not data:
            return centers
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
                    logger.info(f"Found center for dep. {departement}: {parsed_center.get('nom')}")
                    centers.append(parsed_center)
                else:
                    logger.warning(f"Not enough resources for center in dep. {departement}: {center_data.get('title')}")

        # Keldoc provides us the info if there is a next page to explore,
        # it's much easier than testing an extra query.
        if options.get("next_page"):
            return self.parse_pages_departement(departement, page_id=1 + page_id, centers=centers)
        return centers


def fetch_department(department: str):
    all_motives_center = []
    for motive in KELDOC_COVID_SPECIALTIES_URLS:
        scraper = KeldocCenterScraper(motive)
        all_motives_center.extend(scraper.run_departement_scrap(department))
    return all_motives_center


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
