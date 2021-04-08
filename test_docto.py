from scraper.doctolib.doctolib import fetch_slots
from scraper.pattern.scraper_request import ScraperRequest

ir = "https://partners.doctolib.fr/etablissement-de-prevention/le-mans/pro-de-sante-le-mans-uniquement?pid=practice-171174&enable_cookies_consent=1"

request = ScraperRequest(ir, "2020-04-08")
fetc = fetch_slots(request)
print(fetc)