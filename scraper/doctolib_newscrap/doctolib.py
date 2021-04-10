import httpx

from scraper.pattern.scraper_request import ScraperRequest


session = httpx.client()

def fetch_slots(request: ScraperRequest) -> str:
    pass

# TODO: temp, remove
url = "https://partners.doctolib.fr/centre-de-sante/saint-denis/centre-de-vaccination-covid-19-stade-de-france"
scrp = ScraperRequest(url, "2021-04-10")
fetch_slots(scrp)