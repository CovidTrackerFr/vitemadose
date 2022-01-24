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
from scraper.pattern.center_location import CenterLocation
from scraper.keldoc.keldoc_routes import API_SPECIALITY_IDS
from urllib import parse

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
    with open(get_conf_inputs()["from_main_branch"]["departements"], encoding="utf8", newline="\n") as csvfile:
        reader = list(csv.DictReader(csvfile, delimiter=","))

        departements = [
            f'{department_urlify(row["nom_departement"])}-{row["code_departement"]}'
            if row["nom_departement"] not in KELDOC_WEIRD_DEPS
            else f'{department_urlify(KELDOC_WEIRD_DEPS[row["nom_departement"]])}-{row["code_departement"]}'
            for row in reader
        ]
        departements = departements + KELDOC_MISSING_DEPS
        return departements


def set_center_type(center_data: dict):
    center_type = None
    if not center_data or not center_data["rdv_site_web"]:
        return
    center_types = SCRAPER_CONF.get("center_types", {})
    center_type = [value for value in center_types.keys() if value in center_data["rdv_site_web"]]
    if len(center_type) > 0:
        center_type = center_type[0]
    else:
        center_type = center_types["*"]
    return center_type


def parse_atlas():
    url = get_conf_inputs().get("from_data_gouv_website").get("centers_gouv")
    data = requests.get(url).json()
    keldoc_gouv_centers = {}
    for center in data["features"]:
        centre_pro = center["properties"].get("c_reserve_professionels_sante", False)
        url = center["properties"].get("c_rdv_site_web", None)
        id_adresse = center["properties"].get("c_id_adr", None)
        gid = center["properties"].get("c_gid", None)

        if centre_pro:
            continue
        if not url:
            continue
        if not gid:
            continue

        if not "keldoc" in url:
            continue
        if "redirect" in url:
            parsed = parse.parse_qs(
                parse.urlparse(center["properties"]["c_rdv_site_web"]).query, keep_blank_values=True
            )
            url = f'http://keldoc.com/{parsed["dom"][0]}/{parsed["inst"][0]}/{parsed["user"][0]}'

        end_url = f'{parse.urlsplit(url).path.split("/")[3]}'

        keldoc_gouv_centers[gid] = {"url_end": end_url, "id_adresse": id_adresse}
    return keldoc_gouv_centers


def get_atlas_correct_match(infos_page, atlas_center_list):
    data = requests.get(
        "https://api-adresse.data.gouv.fr/search/",
        params=[("q", infos_page["address"]), ("postcode", infos_page["cp"])],
    ).json()
    correct_atlas_gid = None

    try:
        id_adr = data["features"][0]["properties"]["id"]
        matching_atlas_for_id = [
            center_id for center_id, center_data in atlas_center_list.items() if center_data["id_adresse"] == id_adr
        ]
        if matching_atlas_for_id:
            correct_atlas_gid = matching_atlas_for_id[0]
    except:
        return None
    return correct_atlas_gid


class KeldocCenterScraper:
    def __init__(self, vaccination_url_path=None, session: httpx.Client = DEFAULT_SESSION):
        self._session = session
        self.vaccination_url_path = vaccination_url_path
        self.atlas_centers = parse_atlas()

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

    def parse_keldoc_resources(self, url: str) -> Optional[dict]:
        resource_url = parse_keldoc_resource_url(url)
        if resource_url is None:
            return None
        resource_data = self.send_keldoc_request(resource_url)
        return resource_data

    def parse_keldoc_motive_categories(self, clinic_id: int, cabinet_id: int, specialty: int) -> list:
        """
        Fetch available motive categories from cabinet
        """
        if not clinic_id or not cabinet_id or not specialty:
            return None
        motive_url = KELDOC_API.get("motives").format(clinic_id, specialty, cabinet_id)
        motive_data = self.send_keldoc_request(motive_url)
        return motive_data

    def parse_keldoc_center(self, center: dict) -> Optional[dict]:
        url_with_query = None
        motive_url = CENTER_DETAILS.format(center.get("id"))
        motive_data = requests.get(motive_url).json()
        phone_number = None
        if "phone_number" in motive_data:
            phone_number = motive_data["phone_number"]

        for speciality in center.get("specialty_ids", []):
            if str(speciality) in API_SPECIALITY_IDS:
                vaccine_speciality = speciality
                url_with_query = (
                    f"https://keldoc.com{center['url']}?cabinet={center.get('id')}&specialty={vaccine_speciality}"
                )

        resources = self.parse_keldoc_resources(url_with_query)
        if not resources:
            return None
        motives = self.parse_keldoc_motive_categories(resources["id"], center["id"], vaccine_speciality)
        if resources["id"] != center["id"]:
            gid = f'{resources["id"]}pid{center["id"]}'
        else:
            gid = f'{resources["id"]}'
        atlas_gid = None

        atlas_matches = [
            center_id
            for center_id, center_data in self.atlas_centers.items()
            if parse.urlsplit(url_with_query).path.split("/")[-1] in center_data["url_end"]
            or parse.urlsplit(url_with_query).path.split("/")[-2] in center_data["url_end"]
        ]

        data = {
            "nom": center["title"],
            "rdv_site_web": url_with_query,
            "atlas_gid": atlas_gid,
            "com_insee": departementUtils.cp_to_insee(center["cabinet"]["zipcode"]),
            "cp": center["cabinet"]["zipcode"],
            "gid": gid,
            "address": center["cabinet"]["location"].strip(),
            "lat_coor1": center["coordinates"].split(",")[0],
            "long_coor1": center["coordinates"].split(",")[1],
            "city": center["cabinet"]["city"].strip(),
            "phone_number": phone_number,
            "booking": motives,
        }
        if len(atlas_matches) == 0:
            atlas_gid = None
        if len(atlas_matches) == 1:
            atlas_gid = max(atlas_matches)
        if len(atlas_matches) > 1:
            atlas_gid = get_atlas_correct_match(data, self.atlas_centers)

        data["type"] = set_center_type(data)
        data["atlas_gid"] = atlas_gid
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


def parse_keldoc_resource_url(center_url: str) -> Optional[str]:
    if not center_url or not isinstance(center_url, str):
        return None
    if "?" in center_url:
        url_split = center_url.split("?")[0].split("/")
    else:
        url_split = center_url.split("/")
    if len(url_split) < 6:
        return None
    if len(url_split) == 6:
        type, location, slug = url_split[3:6]
        cabinet = None
    if len(url_split) == 7:
        type, location, slug, cabinet = url_split[3:7]
    if cabinet:
        resource_url = f"{KELDOC_API.get('booking')}?type={type}&location={location}&slug={slug}&cabinet={cabinet}"
    else:
        resource_url = f"{KELDOC_API.get('booking')}?type={type}&location={location}&slug={slug}"
    return resource_url


if __name__ == "__main__":  # pragma: no cover
    if KELDOC_CONF.get("enabled", False):
        center_scraper = KeldocCenterScraper()
        centers = parse_keldoc_centers(center_scraper)
        path_out = SCRAPER_CONF.get("result_path")
        logger.info(f"Found {len(centers)} centers on Keldoc")
        if len(centers) < 90:
            # for reference, on 17-05, there were 97 centers
            logger.error(f"[NOT SAVING RESULTS] {len(centers)} does not seem like enough Keldoc centers")
            exit(1)
        else:
            logger.info(f"> Writing them on {path_out}")
            with open(path_out, "w") as f:
                f.write(json.dumps(centers, indent=2))
    else:
        logger.error(f"Keldoc scraper is disabled in configuration file.")
        exit(1)
