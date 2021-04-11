import json
from typing import Optional
from utils.vmd_utils import departementUtils
from scraper.pattern.center_location import CenterLocation, convert_csv_data_to_location
from scraper.pattern.scraper_request import ScraperRequest
from scraper.pattern.scraper_result import ScraperResult

from utils.vmd_utils import urlify, format_phone_number
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
        self.type = None
        self.appointment_count = 0
        self.internal_id = None

    def fill_localization(self, location: Optional[CenterLocation]):
        self.location = location

    def fill_result(self, result: ScraperResult):
        self.prochain_rdv = result.next_availability # TODO change with filters
        self.plateforme = result.platform
        self.type = result.request.practitioner_type
        self.appointment_count = result.request.appointment_count
        self.internal_id = result.request.internal_id

    def default(self):
        if type(self.location) is CenterLocation:
            self.location = self.location.default()
        return self.__dict__


def convert_csv_address(data: dict) -> str:
    if data.get('address', None):
        return data.get('address')
    adr_num = data.get('adr_num', '')
    adr_voie = data.get('adr_voie', '')
    adr_cp = data.get('com_cp', '')
    adr_nom = data.get('com_nom', '')
    return f'{adr_num} {adr_voie}, {adr_cp} {adr_nom}'


def convert_csv_business_hours(data: dict) -> str:
    if data.get('business_hours'):
        return data.get('business_hours')
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
    localization = data['location']
    coordinates = localization['coordinates']

    if coordinates['lon'] or coordinates['lat']:
        loc = CenterLocation(coordinates['lon'], coordinates['lat'])
        center.fill_localization(loc)
    center.ville=urlify(localization["city"])
    center.metadata = dict()
    center.metadata['address'] = f'{localization["address"]}, {localization["zip"]} {localization["city"]}'
    if len(data.get('phone_number', '')) > 3:
        center.metadata['phone_number'] = format_phone_number(data.get('phone_number'))
    center.metadata['business_hours'] = None
    return center


def convert_csv_data_to_center_info(data: dict) -> CenterInfo:
    name = data.get('nom', None)
    departement = ''
    ville=''
    url = data.get('rdv_site_web', None)
    try:
        departement = departementUtils.to_departement_number(data.get('com_insee', None))
    except ValueError:
        logger.error(
            f"erreur lors du traitement de la ligne avec le gid {data['gid']}, com_insee={data['com_insee']}")

    center = CenterInfo(departement, name, url)
    if data.get('iterator', '') == 'ordoclic':
        return convert_ordoclic_to_center_info(data, center)
    center.fill_localization(convert_csv_data_to_location(data))
    center.metadata = dict()
    center.metadata['address'] = convert_csv_address(data)
    if data.get('rdv_tel'):
        center.metadata['phone_number'] = format_phone_number(data.get('rdv_tel'))
    if data.get('phone_number'):
        center.metadata['phone_number'] = format_phone_number(data.get('phone_number'))
    center.metadata['business_hours'] = convert_csv_business_hours(data)
    return center
