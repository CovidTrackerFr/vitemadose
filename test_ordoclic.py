from datetime import datetime
from multiprocessing import Pool

from scraper.ordoclic import fetch_slots as ordoclic_fetch_slots
from scraper.ordoclic import centre_iterator as ordoclic_centre_iterator


def async_ordoclic_scrape(centre):
    vaccine_center = centre["nom"]
    website = centre["rdv_site_web"]
    #print("Vaccine Center {0}: looking for an appointment".format(vaccine_center))
    date = ordoclic_fetch_slots(website, datetime.now().strftime('%Y-%m-%d'))
    if not date:
        print("Vaccine Center {0}: no appointment found".format(vaccine_center))
        return
    print("Vaccine Center {0}: next appointment found: {1}".format(vaccine_center, date))


def main():
    centres = ordoclic_centre_iterator()
    pool = Pool(20)
    pool.map(async_ordoclic_scrape, centres)


if __name__ == "__main__":
    main()
