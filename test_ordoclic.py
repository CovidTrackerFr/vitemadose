from datetime import datetime
from multiprocessing import Pool

from scraper.ordoclic import centre_iterator as ordoclic_centre_iterator
from scraper.ordoclic import fetch_slots as ordoclic_fetch_slots

today = datetime.now().strftime("%Y-%m-%d")


def async_ordoclic_scrape(centre):
    vaccine_center = centre["nom"]
    website = centre["rdv_site_web"]
    # print("Vaccine Center {0}: looking for an appointment".format(vaccine_center))
    date = ordoclic_fetch_slots(website, today)
    if not date:
        print(f"Vaccine Center {vaccine_center}: no appointment found")
        return
    print(f"Vaccine Center {vaccine_center}: next appointment found: {date}")


def main():
    centres = ordoclic_centre_iterator()
    pool = Pool(20)
    pool.map(async_ordoclic_scrape, centres)


if __name__ == "__main__":
    main()
