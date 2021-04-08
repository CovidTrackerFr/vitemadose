from scraper.doctolib.doctolib import fetch_slots
from scraper.pattern.scraper_request import ScraperRequest

ir = "https://partners.doctolib.fr/hopital-public/le-cateau-cambrésis/ch-le-cateau-centre-vaccination-covid-19?speciality_id=5494&enable_cookies_consent=1"

request = ScraperRequest(ir, "2020-04-08")
fetc = fetch_slots(request)
print(fetc)