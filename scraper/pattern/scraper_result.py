import json
from enum import Enum
from typing import List

from scraper.pattern.scraper_request import ScraperRequest


# Practitioner type enum
GENERAL_PRACTITIONER: str = "general-practitioner"
VACCINATION_CENTER: str = "vaccination-center"
DRUG_STORE: str = "drugstore"


class ScraperResult:
    def __init__(self, request: ScraperRequest, platform: str, next_availability: str):
        self.request: ScraperRequest = request
        self.platform: str = platform
        self.next_availability: str = next_availability

    def default(self) -> dict:
        return self.__dict__
