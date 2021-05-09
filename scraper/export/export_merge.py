import sys
import csv
import datetime as dt
import io
import json
import os
import traceback
from collections import deque
from multiprocessing import Pool
from typing import Counter, Iterator, List
from scraper.profiler import Profiling, ProfiledPool

from scraper.error import ScrapeError, BlockedByDoctolibError

import pytz
import requests

from scraper.pattern.center_info import convert_csv_data_to_center_info, CenterInfo
from scraper.pattern.scraper_request import ScraperRequest
from scraper.pattern.scraper_result import ScraperResult, VACCINATION_CENTER
from utils.vmd_blocklist import get_blocklist_urls, is_in_blocklist
from utils.vmd_logger import enable_logger_for_production, enable_logger_for_debug
from utils.vmd_utils import departementUtils, fix_scrap_urls, is_reserved_center, get_last_scans
from scraper.doctolib.doctolib import fetch_slots as doctolib_fetch_slots
from scraper.doctolib.doctolib import center_iterator as doctolib_center_iterator
from scraper.keldoc.keldoc import fetch_slots as keldoc_fetch_slots
from scraper.maiia.maiia import centre_iterator as maiia_centre_iterator
from scraper.maiia.maiia import fetch_slots as maiia_fetch_slots
from scraper.ordoclic import centre_iterator as ordoclic_centre_iterator
from scraper.ordoclic import fetch_slots as ordoclic_fetch_slots
from scraper.mapharma.mapharma import centre_iterator as mapharma_centre_iterator
from scraper.mapharma.mapharma import fetch_slots as mapharma_fetch_slots
from random import random

from scraper.scraper import copy_omit_keys, deduplicates_names, sort_center

POOL_SIZE = int(os.getenv("POOL_SIZE", 50))
PARTIAL_SCRAPE = float(os.getenv("PARTIAL_SCRAPE", 1.0))
PARTIAL_SCRAPE = max(0, min(PARTIAL_SCRAPE, 1))

logger = enable_logger_for_production()


def export_data(centres_cherchés: Iterator[CenterInfo], outpath_format="data/output/{}.json"):
    compte_centres = 0
    compte_centres_avec_dispo = 0
    bloqués_doctolib = 0
    centres_open_data = []
    internal_ids = []
    par_departement = {
        code: {
            "version": 1,
            "last_updated": dt.datetime.now(tz=pytz.timezone("Europe/Paris")).isoformat(),
            "centres_disponibles": [],
            "centres_indisponibles": [],
        }
        for code in departementUtils.import_departements()
    }

    blocklist = get_blocklist_urls()
    # This should be duplicate free, they are already checked in
    is_blocked_center = lambda center: (is_reserved_center(center) or is_in_blocklist(center, blocklist))
    blocked_centers = [center for center in centres_cherchés if is_blocked_center(center)]
    exported_centers = [center for center in centres_cherchés if not is_blocked_center(center)]

    for centre in blocked_centers:
        if centre.has_available_appointments():  # pragma: no cover
            logger.warn(f"{centre.nom} {centre.internal_id} has available appointments but is blocked")

    for centre in exported_centers:
        compte_centres += 1

        centre.nom = centre.nom.strip()
        if centre.departement not in par_departement:
            logger.warning(f"Center {centre.nom} ({centre.departement}) could not be attached to a valid department")
            continue
        erreur = centre.erreur
        if centre.internal_id and centre.internal_id in internal_ids:  # pragma: no cover
            logger.warning(
                f"Found a duplicated internal_id: {centre.nom} ({centre.departement}) -> {centre.internal_id}"
            )
            continue
        internal_ids.append(centre.internal_id)
        skipped_keys = [
            "prochain_rdv",
            "internal_id",
            "metadata",
            "location",
            "appointment_count",
            "appointment_schedules",
            "erreur",
            "ville",
            "type",
            "vaccine_type",
            "appointment_by_phone_only",
            "last_scan_with_availabilities",
        ]
        centres_open_data.append(copy_omit_keys(centre.default(), skipped_keys))

        if centre.has_available_appointments():
            compte_centres_avec_dispo += 1
            par_departement[centre.departement]["centres_disponibles"].append(centre.default())
        else:
            par_departement[centre.departement]["centres_indisponibles"].append(centre.default())
            if isinstance(erreur, BlockedByDoctolibError):
                par_departement[centre.departement]["doctolib_bloqué"] = True
                bloqués_doctolib += 1

    outpath = outpath_format.format("info_centres")
    with open(outpath, "w") as info_centres:
        json.dump(par_departement, info_centres, indent=2)

    outpath = outpath_format.format("centres_open_data")
    with open(outpath, "w") as centres_file:
        json.dump(centres_open_data, centres_file, indent=2)

    for centre.departement, disponibilités in par_departement.items():
        disponibilités["last_updated"] = dt.datetime.now(tz=pytz.timezone("Europe/Paris")).isoformat()
        if "centres_disponibles" in disponibilités:
            disponibilités["centres_disponibles"] = sorted(
                deduplicates_names(disponibilités["centres_disponibles"]), key=sort_center
            )
        disponibilités["centres_indisponibles"] = deduplicates_names(disponibilités["centres_indisponibles"])
        outpath = outpath_format.format(centre.departement)
        logger.debug(f"writing result to {outpath} file")
        with open(outpath, "w") as outfile:
            outfile.write(json.dumps(disponibilités, indent=2))

    return compte_centres, compte_centres_avec_dispo, bloqués_doctolib