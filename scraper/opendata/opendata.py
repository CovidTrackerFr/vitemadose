import csv
import io
import json
from typing import Iterator
import requests

from utils.vmd_logger import get_logger
from utils.vmd_utils import fix_scrap_urls

logger = get_logger()


def center_iterator(outpath_format="data/output/{}.json") -> Iterator[dict]:
    url = "https://www.data.gouv.fr/fr/datasets/r/5cb21a85-b0b0-4a65-a249-806a040ec372"
    response = requests.get(url)
    response.raise_for_status()

    reader = io.StringIO(response.content.decode("utf8"))
    csvreader = csv.DictReader(reader, delimiter=";")

    total = 0

    centres_non_pris_en_compte = {"centres_fermes": {}, "centres_urls_vides": []}

    for row in csvreader:

        row["rdv_site_web"] = fix_scrap_urls(row["rdv_site_web"])
        if row["centre_fermeture"] == "t":
            centres_non_pris_en_compte["centres_fermes"][row["gid"]] = row["rdv_site_web"]
        if should_use_opendata_csv(row["rdv_site_web"]):
            yield row
        else:
            centres_non_pris_en_compte["centres_urls_vides"].append(row["gid"])

        total += 1

    nb_fermes = len(centres_non_pris_en_compte["centres_fermes"])
    nb_urls_vides = len(centres_non_pris_en_compte["centres_urls_vides"])

    logger.info(f"Il y a {nb_fermes} centres fermes dans le fichier gouv sur un total de {total}")

    nb_urls_vides = len(centres_non_pris_en_compte["centres_urls_vides"])
    logger.info(f"Il y a {nb_urls_vides} centres avec une URL vide dans le fichier gouv sur un total de {total}")

    outpath = outpath_format.format("centres_non_pris_en_compte_gouv")
    with open(outpath, "w") as fichier:
        json.dump(centres_non_pris_en_compte, fichier, indent=2)


def should_use_opendata_csv(rdv_site_web: str) -> bool:
    plateformes_hors_csv = ["doctolib", "maiia"]

    if any(p in rdv_site_web for p in plateformes_hors_csv):
        return False
    return True
