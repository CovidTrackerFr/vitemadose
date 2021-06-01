import json

from scraper.pattern.center_info import CenterInfo
from utils.vmd_config import get_conf_inputs


def is_in_blocklist(center: CenterInfo, blocklist_urls) -> bool:
    return center.url in blocklist_urls


def get_blocklist_urls() -> set:
    path_blocklist = get_conf_inputs().get("blocklist")
    centers_blocklist_urls = set([center["url"] for center in json.load(open(path_blocklist))["centers_not_displayed"]])
    return centers_blocklist_urls
