from urllib.parse import parse_qs, urlsplit

import httpx

from scraper.pattern.scraper_request import ScraperRequest


session = httpx.client()


class DoctolibCenter:
    def __init__(self, request: ScraperRequest):
        self.request = request
        self.internal_name = self.parse_internal_name()

    def parse_internal_name(self) -> str:
        query = urlsplit(self.request.url).query
        params = parse_qs(query)
        return params.path
