from scraper.doctolib.doctolib import fetch_slots
from scraper.pattern.scraper_request import ScraperRequest

ir = "https://partners.doctolib.fr/centre-de-sante/paris/centre-de-vaccination-covid-19-ville-de-paris?pid=practice-164924&enable_cookies_consent=1"

request = ScraperRequest(ir, "2020-04-08")
fetc = fetch_slots(request)
print(fetc)
