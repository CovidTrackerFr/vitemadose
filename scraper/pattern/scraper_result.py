
from scraper.pattern.scraper_request import ScraperRequest


# Practitioner type enum
GENERAL_PRACTITIONER = "general-practitioner"
VACCINATION_CENTER = "vaccination-center"
DRUG_STORE = "drugstore"


class ScraperResult:
    def __init__(self, request: ScraperRequest, platform, next_availability):
        self.request = request
        self.platform = platform
        self.next_availability = next_availability

    def default(self):
        return self.__dict__
