"""Scrapes a given list of URLs.

They come from a Google sheets configured in `config.json`.
"""

from typing import Dict, Iterator

from pydantic import BaseModel

from utils.vmd_config import get_conf_platform, get_config
from utils.vmd_logger import get_logger
from utils.vmd_utils import fix_scrap_urls
from scraper import sheets

NAME = "manual"


class Config(BaseModel):
    enabled: bool
    sheet_id: str  # ID of the spreadsheet.
    page_number: int  # Index of the sheet inside the spreadsheet (starts at 1).
    column_names: Dict[int, str]  # Mapping of column ID to column name (starts at 1).


logger = get_logger()

config = Config(**get_conf_platform(NAME))


def iterator() -> Iterator[dict]:
    logger.info("Recherche des urls manuels")
    for entry in sheets.load(config.sheet_id, config.page_number, config.column_names):
        yield {
            "rdv_site_web": fix_scrap_urls(entry["url"]),
            "nom": entry["name"],
            "address": entry["address"],
            "lat_coor1": entry["lat"],
            "lon_coor1": entry["lon"],
            "com_insee": entry["insee"],
        }
