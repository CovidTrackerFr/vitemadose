import httpx
import multiprocessing

from utils.vmd_config import get_conf_platform
from utils.vmd_logger import get_logger
from utils.vmd_utils import get_departements, department_urlify

from scraper.doctolib.doctolib import DOCTOLIB_HEADERS
from scraper.doctolib.doctolib_filters import is_vaccination_center
from scraper.doctolib.doctolib_parsers import (
    get_coordinates,
    center_type,
    parse_doctolib_business_hours,
    parse_place,
    parse_center_places,
    parse_doctor,
    center_reducer,
)

from typing import List, Tuple, Dict
import json
from urllib import parse

DOCTOLIB_CONF = get_conf_platform("doctolib")
SCRAPER_CONF = DOCTOLIB_CONF.get("center_scraper")

BASE_URL_DEPARTEMENT = DOCTOLIB_CONF.get("api").get("scraper_dep")
BOOKING_URL = DOCTOLIB_CONF.get("api").get("booking")

BASE_URL = DOCTOLIB_CONF.get("build_url")

DEFAULT_CLIENT = httpx.Client()

logger = get_logger()


class DoctolibCenterScraper:
    def __init__(self, client: httpx.Client = DEFAULT_CLIENT):
        self._client = client

    def run_departement_scrap(self, departement: str):
        logger.info(f"[Doctolib centers] Parsing pages of departement {departement} through department SEO link")
        centers_departements = self.parse_pages_departement(departement)
        if centers_departements == 0:
            raise Exception("No Value found for department {}, crashing")
        return centers_departements

    def parse_pages_departement(self, departement: str) -> list:
        departement = department_urlify(departement)
        page_id = 1
        page_has_centers = True
        liste_urls = []

        for weird_dep in SCRAPER_CONF.get("dep_conversion"):
            if weird_dep == departement:
                departement = SCRAPER_CONF.get("dep_conversion")[weird_dep]
                break
        centers = []
        while page_has_centers:
            logger.info(f"[Doctolib centers] Parsing page {page_id} of {departement}")
            centers_page, stop = self.parse_page_centers_departement(departement, page_id, liste_urls)
            centers += centers_page

            page_id += 1

            if len(centers_page) == 0 or stop:
                page_has_centers = False

        return centers

    def parse_page_centers_departement(
        self, departement: str, page_id: int, liste_urls: list
    ) -> Tuple[List[dict], bool]:
        try:
            r = self._client.get(
                BASE_URL_DEPARTEMENT.format(department_urlify(departement), page_id),
                headers=DOCTOLIB_HEADERS,
                follow_redirects=True,
            )
            data = r.json()
        except:

            logger.warn(f"> Could not retrieve centers from department {departement} page_id {page_id}  => {r}.")
            return [], False

        return self.centers_from_page(data, liste_urls, departement, page_id)

    def centers_from_page(self, department_page_data: Dict, liste_urls, departement, page_id):
        centers_page = []
        # TODO parallelism can be put here
        for payload in department_page_data["data"]["doctors"]:
            # If the "doctor" hasn't already been checked
            if payload["link"] not in liste_urls:
                liste_urls.append(payload["link"])
                # One "doctor" can have multiple places, hence center_from_doctor_dict returns a list
                centers, stop = self.center_from_doctor_dict(payload, departement, page_id)
                centers_page += centers
                if stop:
                    return centers_page, True
        return centers_page, False

    def center_from_doctor_dict(self, doctor_dict, departement, page_id) -> Tuple[dict, bool]:
        liste_centres = []
        dict_infos_browse_page = parse_doctor(doctor_dict)
        url_path = doctor_dict["link"]
        url_path_splited = "/".join([url_path.split("/")[i] for i in range(2, len(url_path.split("/")))])
        dict_infos_centers_page = self.get_dict_infos_center_page(url_path, departement, page_id)

        for info_center in dict_infos_centers_page:
            info_center["rdv_site_web"] = BASE_URL.format(url_path=url_path_splited, place_id=info_center["place_id"])

            # info center overrides the keys found in the SEO page if they are different
            # This is for when centers have multiple practice-ids which are also centers with different addresses
            liste_centres.append({**dict_infos_browse_page, **info_center})

        stop = not doctor_dict["exact_match"]
        return liste_centres, stop

    def get_dict_infos_center_page(self, url_path: str, departement, page_id) -> dict:
        internal_api_url = BOOKING_URL.format(centre=parse.urlsplit(url_path).path.split("/")[-1])
        logger.info(f"> Parsing {internal_api_url} from dep {departement} - page {page_id}")
        output = None

        try:
            req = self._client.get(internal_api_url, headers=DOCTOLIB_HEADERS, follow_redirects=True)
            req.raise_for_status()
            data = req.json()
            output = data.get("data", {})
        except:
            logger.warn(f"> Could not retrieve data from {internal_api_url} => {req}")
            return []

        return parse_center_places(output)


def fetch_department(department: str):
    if not DOCTOLIB_CONF.get("enabled"):
        return None
    scraper = DoctolibCenterScraper()
    return scraper.run_departement_scrap(department)


def parse_doctolib_centers(page_limit=None) -> List[dict]:
    centers = []
    unique_center_urls = []

    with multiprocessing.Pool(50) as pool:
        center_lists = pool.imap_unordered(fetch_department, get_departements(excluded_departments=["Guyane"]))
        centers = []

        for center_list in center_lists:
            centers.extend(center_list)

        centers = list(filter(is_vaccination_center, centers))  # Filter vaccination centers
        centers = list(map(center_reducer, centers))  # Remove fields irrelevant to the front

        for item in list(centers):
            if item.get("rdv_site_web") in unique_center_urls:
                centers.remove(item)
                continue
            unique_center_urls.append(item.get("rdv_site_web"))

        return centers


if __name__ == "__main__":  # pragma: no cover
    if DOCTOLIB_CONF.get("enabled"):
        centers = parse_doctolib_centers()
        path_out = SCRAPER_CONF.get("result_path")
        logger.info(f"Found {len(centers)} centers on Doctolib")
        if len(centers) < 2000:
            # for reference, on 13-05, there were 12k centers
            logger.error(f"[NOT SAVING RESULTS]{len(centers)} does not seem like enough Doctolib centers")
        else:
            logger.info(f"> Writing them on {path_out}")
            with open(path_out, "w") as f:
                f.write(json.dumps(centers))
    else:
        logger.error(f"Doctolib scraper is disabled in configuration file.")
        exit(1)
