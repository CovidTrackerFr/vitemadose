from enum import Enum
from datetime import datetime, timedelta
from typing import Optional, List, Dict

import pytz
import requests

from utils.vmd_utils import departementUtils
from scraper.pattern.center_location import CenterLocation, convert_csv_data_to_location
from scraper.pattern.scraper_request import ScraperRequest
from scraper.pattern.scraper_result import ScraperResult

from utils.vmd_utils import urlify, format_phone_number
from utils.vmd_logger import get_logger

logger = get_logger()


class Vaccine(str, Enum):
    PFIZER = "Pfizer-BioNTech"
    MODERNA = "Moderna"
    ASTRAZENECA = "AstraZeneca"
    JANSSEN = "Janssen"
    ARNM = "ARNm"


VACCINES_NAMES: Dict[Vaccine, List[str]] = {
    Vaccine.PFIZER: ["pfizer", "biontech"],
    Vaccine.MODERNA: ["moderna"],
    Vaccine.ARNM: ["arn", "arnm", "arn-m", "arn m"],
    Vaccine.ASTRAZENECA: ["astrazeneca", "astra-zeneca", "astra zeneca", "az"],  # Not too sure about the reliability
    Vaccine.JANSSEN: [
        "janssen",
        "jansen",
        "jansenn",
        "jannsen",
        "jenssen",
        "jensen",
        "jonson",
        "johnson",
        "johnnson",
        "j&j",
    ],
}


RESERVED_CENTERS: List[str] = ["réservé", "reserve", "professionnel"]


# Schedules array for appointments by interval
INTERVAL_SPLIT_DAYS = [1, 2, 7, 28, 49]

# Array for CHRONODOSES parameters
CHRONODOSES = {"Vaccine": [Vaccine.ARNM, Vaccine.PFIZER, Vaccine.MODERNA], "Interval": 2}


class CenterInfo:
    def __init__(self, departement: str, nom: str, url: str):
        self.departement: str = departement
        self.nom: str = nom
        self.url: str = url
        self.location: Optional[CenterLocation] = None
        self.metadata: Optional[dict] = None
        self.prochain_rdv: Optional[str]= None
        self.plateforme: Optional[str] = None
        self.type: Optional[str] = None
        self.appointment_count: int = 0
        self.internal_id: Optional[str] = None
        self.gid: Optional[str] = None
        self.vaccine_type: Optional[List[Vaccine]] = None
        self.appointment_by_phone_only: bool = False
        self.erreur: Optional[str] = None
        self.last_scan_with_availabilities: Optional[str] = None

    def fill_localization(self, location: Optional[CenterLocation]):
        self.location = location

    def fill_result(self, result: ScraperResult):
        self.prochain_rdv = result.next_availability  # TODO change with filters
        self.plateforme = result.platform
        self.type = result.request.practitioner_type
        self.appointment_count = result.request.appointment_count
        self.appointment_schedules = result.request.appointment_schedules
        self.internal_id = result.request.internal_id
        self.vaccine_type = result.request.vaccine_type
        self.appointment_by_phone_only = result.request.appointment_by_phone_only

    def handle_next_availability(self):
        if not self.prochain_rdv:
            return
        timezone = pytz.timezone("Europe/Paris")
        try:
            date = pytz.utc.localize(datetime.fromisoformat(self.prochain_rdv))
        except (TypeError, ValueError):
            # Invalid date
            return
        # Too far
        if date - datetime.now(tz=timezone) > timedelta(days=50):
            self.prochain_rdv = None

    def default(self) -> dict:
        if type(self.location) is CenterLocation:
            self.location = self.location.default()
        if self.erreur:
            self.erreur = str(self.erreur)
        if self.vaccine_type:
            self.vaccine_type = [
                (vaccine.value if isinstance(vaccine, Vaccine) else vaccine) for vaccine in self.vaccine_type
            ]
        self.handle_next_availability()
        return self.__dict__

    def has_available_appointments(self) -> bool:
        return self.prochain_rdv is not None and self.appointment_count > 0


def convert_csv_address(data: dict) -> str:
    if data.get("address", None):
        return data.get("address")
    adr_num = data.get("adr_num", "")
    adr_voie = data.get("adr_voie", "")
    adr_cp = data.get("com_cp", "")
    adr_nom = data.get("com_nom", "")
    return f"{adr_num} {adr_voie}, {adr_cp} {adr_nom}"


def convert_csv_business_hours(data: dict) -> Optional[dict]:
    if data.get("business_hours"):
        return data.get("business_hours")
    keys = ["rdv_lundi", "rdv_mardi", "rdv_mercredi", "rdv_jeudi", "rdv_vendredi", "rdv_samedi", "rdv_dimanche"]
    meta = {}

    for key in data:
        if key not in keys:
            continue
        formatted_key = key.replace("rdv_", "")
        meta[formatted_key] = data[key]
    if not meta:
        return None
    return meta


def convert_ordoclic_to_center_info(data: dict, center: CenterInfo) -> CenterInfo:
    localization = data.get("location")
    coordinates = localization.get("coordinates")

    if coordinates["lon"] or coordinates["lat"]:
        city = urlify(localization.get("city"))
        loc = CenterLocation(coordinates["lon"], coordinates["lat"], city)
        center.fill_localization(loc)
    center.metadata = dict()
    center.metadata["address"] = f'{localization["address"]}, {localization["zip"]} {localization["city"]}'
    if len(data.get("phone_number", "")) > 3:
        center.metadata["phone_number"] = format_phone_number(data.get("phone_number"))
    center.metadata["business_hours"] = None
    return center


def convert_csv_data_to_center_info(data: dict) -> CenterInfo:
    name = data.get("nom", None)
    departement = ""
    ville = ""
    url = data.get("rdv_site_web", None)
    try:
        departement = departementUtils.to_departement_number(data.get("com_insee", None))
    except ValueError as e:
        logger.error(
            f"erreur lors du traitement de la ligne avec le gid {data['gid']}, com_insee={data['com_insee']} : {e}"
        )

    center = CenterInfo(departement, name, url)
    if data.get("iterator", "") == "ordoclic":
        return convert_ordoclic_to_center_info(data, center)
    center.fill_localization(convert_csv_data_to_location(data))
    center.metadata = dict()
    center.metadata["address"] = convert_csv_address(data)
    if data.get("rdv_tel"):
        center.metadata["phone_number"] = format_phone_number(data.get("rdv_tel"))
    if data.get("phone_number"):
        center.metadata["phone_number"] = format_phone_number(data.get("phone_number"))
    center.metadata["business_hours"] = convert_csv_business_hours(data)
    return center


def get_vaccine_name(name: str, fallback: Optional[Vaccine] = None) -> Optional[Vaccine]:
    if not name:
        return fallback
    name = name.lower().strip()
    for vaccine in (Vaccine.ARNM, Vaccine.MODERNA, Vaccine.PFIZER, Vaccine.ASTRAZENECA, Vaccine.JANSSEN):
        vaccine_names = VACCINES_NAMES[vaccine]
        for vaccine_name in vaccine_names:
            if vaccine_name in name:
                if vaccine == Vaccine.ASTRAZENECA:
                    return get_vaccine_astrazeneca_minus_55_edgecase(name)
                return vaccine
    return fallback


def get_vaccine_astrazeneca_minus_55_edgecase(name: str) -> Vaccine:
    has_minus = "-" in name or "–" in name or "–" in name or "moins" in name
    if has_minus and "55" in name and "suite" in name:
        return Vaccine.ARNM
    return Vaccine.ASTRAZENECA


def dict_to_center_info(data: dict) -> CenterInfo:
    center = CenterInfo(data.get("departement"), data.get("nom"), data.get("url"))
    center.plateforme = data.get("plateforme")
    center.prochain_rdv = data.get("prochain_rdv")
    center.erreur = data.get("erreur")
    return center


def full_dict_to_center(data: dict) -> CenterInfo:
    center = CenterInfo("", "", "")
    for key in data:
        setattr(center, key, data.get(key))
    return center


def is_reserved_center(center: Optional[CenterInfo]) -> bool:
    if not center:
        return False
    name = center.nom.lower().strip()
    for reserved_names in RESERVED_CENTERS:
        if reserved_names in name:
            return True
    return False


def get_last_scans(centres: List[CenterInfo]) -> List:
    url = "https://vitemadose.gitlab.io/vitemadose/info_centres.json"
    last_scans = {}
    liste_centres = centres.copy()

    try:
        response = requests.get(url)
        response.raise_for_status()
        info_centres = response.json()

    except Exception as e:
        logger.warning(f"Impossible de récupérer le fichier info_centres: {e}")
        info_centres = {}

    for last_centres in info_centres.values():
        for centre in last_centres["centres_disponibles"] + last_centres["centres_indisponibles"]:
            if "last_scan_with_availabilities" in centre:
                last_scans[centre["url"]] = centre["last_scan_with_availabilities"]

    for centre in liste_centres:
        if not centre.prochain_rdv:
            if centre.url in last_scans:
                centre.last_scan_with_availabilities = last_scans[centre.url]
        else:
            centre.last_scan_with_availabilities = datetime.datetime.now(tz=pytz.timezone("Europe/Paris")).isoformat()

    return liste_centres
