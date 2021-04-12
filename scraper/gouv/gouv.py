import sys
import csv
import datetime as dt
import io
import json
import os

import requests

from utils.vmd_logger import enable_logger_for_production, enable_logger_for_debug
from utils.vmd_utils import fix_scrap_urls

logger = enable_logger_for_production()

def centre_iterator(outpath_format='data/output/{}.json'):
    url = "https://www.data.gouv.fr/fr/datasets/r/5cb21a85-b0b0-4a65-a249-806a040ec372"
    response = requests.get(url)
    response.raise_for_status()

    reader = io.StringIO(response.content.decode('utf8'))
    csvreader = csv.DictReader(reader, delimiter=';')

    total = 0

    centres_non_pris_en_compte = {
        "centres_fermes": {}, "centres_urls_vides": []}

    for row in csvreader:

        row["rdv_site_web"] = row["rdv_site_web"]
        if row["centre_fermeture"] == "t":
            centres_non_pris_en_compte["centres_fermes"][row["gid"]
                                                         ] = row["rdv_site_web"]

        if len(row["rdv_site_web"]):
            yield row
        else:
            centres_non_pris_en_compte["centres_urls_vides"].append(row["gid"])

        total += 1

    nb_fermes = len(centres_non_pris_en_compte["centres_fermes"])
    nb_urls_vides = len(centres_non_pris_en_compte["centres_urls_vides"])

    logger.info(
        f"Il y a {nb_fermes} centres fermes dans le fichier gouv sur un total de {total}")

    nb_urls_vides = len(centres_non_pris_en_compte["centres_urls_vides"])
    logger.info(
        f"Il y a {nb_urls_vides} centres avec une URL vide dans le fichier gouv sur un total de {total}")

    outpath = outpath_format.format("centres_non_pris_en_compte_gouv")
    with open(outpath, "w") as fichier:
        json.dump(centres_non_pris_en_compte, fichier, indent=2)