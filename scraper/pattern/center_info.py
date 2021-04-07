import json
from typing import Optional

from scraper.departements import to_departement_number
from scraper.pattern.center_location import CenterLocation, convert_csv_data_to_location
from scraper.pattern.scraper_request import ScraperRequest
from scraper.pattern.scraper_result import ScraperResult
from utils.vmd_logger import get_logger

logger = get_logger()


class CenterInfo:
    def __init__(self, departement: str, nom: str, url: str):
        self.departement = departement
        self.nom = nom
        self.url = url
        self.location = None
        self.metadata = None
        self.prochain_rdv = None
        self.plateforme = None

    def fill_localization(self, location: Optional[CenterLocation]):
        self.location = location

    def fill_result(self, result: ScraperResult):
        self.prochain_rdv = result.next_availability # TODO change with filters
        self.plateforme = result.platform

    def default(self):
        self.location = self.location.default()
        return self.__dict__


def convert_csv_data_to_center_info(data: dict) -> CenterInfo:
    name = data.get('nom', None)
    departement = ''
    url = data.get('rdv_site_web', None)
    try:
        departement = to_departement_number(data.get('com_insee', None))
    except ValueError:
        logger.error(
            f"erreur lors du traitement de la ligne avec le gid {data['gid']}, com_insee={data['com_insee']}")

    center = CenterInfo(departement, name, url)
    center.fill_localization(convert_csv_data_to_location(data))
    return center
