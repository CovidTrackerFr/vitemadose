from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional, List

import pytz

from utils.vmd_config import get_config
from utils.vmd_utils import departementUtils
from scraper.pattern.center_location import CenterLocation
from scraper.pattern.scraper_result import ScraperResult
from scraper.pattern.vaccine import Vaccine

from utils.vmd_utils import urlify, format_phone_number
from utils.vmd_logger import get_logger

logger = get_logger()


# Schedules array for appointments by interval
INTERVAL_SPLIT_DAYS = get_config().get("appointment_split_days", [])

# Array for CHRONODOSES parameters
CHRONODOSE_CONF = get_config().get("chronodoses", {})
CHRONODOSES = {"Vaccine": CHRONODOSE_CONF.get("vaccine", []), "Interval": CHRONODOSE_CONF.get("interval", 0)}


class CenterInfo:
    def __init__(
        self,
        departement: str,
        nom: str,
        url: str,
        location: Optional[CenterLocation] = None,
        metadata: Optional[dict] = None,
        plateforme: Optional[str] = None,
        prochain_rdv: Optional[str] = None,
        erreur: Optional[str] = None,
    ):
        self.departement = departement
        self.nom = nom
        self.url = url
        self.location = location
        self.metadata = metadata
        self.prochain_rdv = prochain_rdv
        self.plateforme = plateforme
        self.type = None
        self.appointment_count = 0
        self.internal_id = None
        self.vaccine_type = None
        self.appointment_by_phone_only = False
        self.erreur = erreur
        self.last_scan_with_availabilities = None
        self.request_counts = None

    @classmethod
    def from_dict(cls, data: dict) -> CenterInfo:
        kwargs = {
            key: value
            for key, value in data.items()
            if key in ("departement", "nom", "url", "plateforme", "prochain_rdv", "erreur")
        }
        return CenterInfo(**kwargs)

    @classmethod
    def from_csv_data(cls, data: dict) -> CenterInfo:
        departement = ""
        try:
            departement = departementUtils.to_departement_number(data.get("com_insee"))
        except ValueError as e:
            logger.error(
                f"erreur lors du traitement de la ligne avec le gid {data['gid']}, com_insee={data['com_insee']} : {e}"
            )

        center = CenterInfo(
            departement,
            data.get("nom"),
            data.get("rdv_site_web"),
            location=CenterLocation.from_csv_data(data),
            metadata=cls._metadata_from_csv_data(data),
        )

        # TODO: Behaviour about particular implementations shouldln’t bubble up to the pattern.
        if data.get("iterator") == "ordoclic":
            return convert_ordoclic_to_center_info(data, center)

        return center

    @staticmethod
    def _metadata_from_csv_data(data: dict) -> dict:
        metadata = {"address": convert_csv_address(data), "business_hours": convert_csv_business_hours(data)}
        if data.get("rdv_tel"):
            metadata.update({"phone_number": format_phone_number(data.get("rdv_tel"))})
        if data.get("phone_number"):
            metadata.update({"phone_number": format_phone_number(data.get("phone_number"))})
        return metadata

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
        self.request_counts = result.request.requests

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

    def default(self):
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


def _address_from_data(data: dict) -> str:
    adr_num = data.get("adr_num", "")
    adr_voie = data.get("adr_voie", "")
    adr_cp = data.get("com_cp", "")
    adr_nom = data.get("com_nom", "")
    return f"{adr_num} {adr_voie}, {adr_cp} {adr_nom}"


def convert_csv_address(data: dict) -> str:
    return data.get("address") or _address_from_data(data)


def _extract_business_hours(data: dict) -> Optional[dict]:
    to_extract = [f"rdv_{day}" for day in ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche")]
    extracted = {key.replace("rdv_", ""): value for key, value in data.items() if key in to_extract}
    return extracted or None


def convert_csv_business_hours(data: dict) -> Optional[dict]:
    return data.get("business_hours") or _extract_business_hours(data)


# TODO: This should be in the `ordoclinic` module.
def convert_ordoclic_to_center_info(data: dict, center: CenterInfo) -> CenterInfo:
    localization = data.get("location")
    coordinates = localization.get("coordinates")

    if coordinates["lon"] or coordinates["lat"]:
        city = urlify(localization.get("city"))
        zip = localization.get("zip")
        loc = CenterLocation(coordinates["lon"], coordinates["lat"], city, zip)
        center.fill_localization(loc)
    center.metadata = dict()
    center.metadata["address"] = f'{localization["address"]}, {localization["zip"]} {localization["city"]}'
    if len(data.get("phone_number", "")) > 3:
        center.metadata["phone_number"] = format_phone_number(data.get("phone_number"))
    center.metadata["business_hours"] = None
    return center
