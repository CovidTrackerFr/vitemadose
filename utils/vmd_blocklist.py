import json

from scraper.pattern.center_info import CenterInfo

def is_in_blocklist(center: CenterInfo, blocklist_urls) -> bool:
    return center.url in blocklist_urls


def get_blocklist_urls() -> set:
    path_blocklist = "data/input/centers_blocklist.json"
    centers_blocklist_urls = set([center["url"] for center in json.load(open(path_blocklist))["centers_not_displayed"]])
    return centers_blocklist_urls