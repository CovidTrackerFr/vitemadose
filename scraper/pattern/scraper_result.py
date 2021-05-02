import json
from enum import Enum

from scraper.pattern.scraper_request import ScraperRequest


# Practitioner type enum
GENERAL_PRACTITIONER = 'general-practitioner'
VACCINATION_CENTER = 'vaccination-center'
DRUG_STORE = 'drugstore'

# Schedules array for appointments by interval
INTERVAL_SPLIT_DAYS = [1, 7, 28, 49]

class ScraperResult:
    def __init__(self, request: ScraperRequest, platform, next_availability):
        self.request = request
        self.platform = platform
        self.next_availability = next_availability

    def default(self):
        return self.__dict__
