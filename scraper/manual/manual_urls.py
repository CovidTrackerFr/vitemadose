import csv
from typing import Iterator


from utils.vmd_logger import get_logger


logger = get_logger()


def manual_urls_iterator() -> Iterator[dict]:
    logger.info("Recherche des urls manuel")
    path_file = "data/input/manual_urls.csv"
    total = 0
    with open(path_file, encoding="utf8") as csvfile:
        reader = csv.DictReader(csvfile, delimiter=";")
        for row in reader:
            total = total + 1
            # row["rdv_site_web"] = fix_scrap_urls(row["rdv_site_web"])
        logger.info("Nombre d'urls manuel " + str(total))
        yield row
