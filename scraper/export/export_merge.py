import datetime as dt
import json
import os
from typing import Iterator

import pytz

from scraper.error import BlockedByDoctolibError
from scraper.pattern.center_info import CenterInfo
from utils.vmd_blocklist import get_blocklist_urls, is_in_blocklist
from utils.vmd_center_sort import sort_center
from utils.vmd_duplicated import deduplicates_names
from utils.vmd_logger import get_logger
from utils.vmd_opendata import copy_omit_keys
from utils.vmd_utils import departementUtils, is_reserved_center

POOL_SIZE = int(os.getenv("POOL_SIZE", 50))
PARTIAL_SCRAPE = float(os.getenv("PARTIAL_SCRAPE", 1.0))
PARTIAL_SCRAPE = max(0, min(PARTIAL_SCRAPE, 1))
OM_CODES = {"975", "977", "978", "98"}

logger = get_logger()


def export_data(centres_cherchés: Iterator[CenterInfo], last_scrap, outpath_format="data/output/{}.json"):
    compte_centres = 0
    compte_centres_avec_dispo = 0
    bloqués_doctolib = 0
    centres_open_data = []
    internal_ids = []
    par_departement = {
        code: {
            "version": 1,
            "last_updated": dt.datetime.now(tz=pytz.timezone("Europe/Paris")).isoformat(),
            "last_scrap": last_scrap,
            "centres_disponibles": [],
            "centres_indisponibles": [],
        }
        for code in departementUtils.import_departements()
    }

    # code spécifique aux collectivités d'outre-mer
    par_departement["om"] = {
        "version": 1,
        "last_updated": dt.datetime.now(tz=pytz.timezone("Europe/Paris")).isoformat(),
        "last_scrap": last_scrap,
        "centres_disponibles": [],
        "centres_indisponibles": [],
    }

    blocklist = get_blocklist_urls()
    # This should be duplicate free, they are already checked in
    is_blocked_center = lambda center: (is_reserved_center(center) or is_in_blocklist(center, blocklist))

    for centre in centres_cherchés:
        if is_blocked_center(centre):
            if centre.has_available_appointments():
                logger.warn(f"{centre.nom} {centre.internal_id} has available appointments but is blocked")
            continue

        compte_centres += 1

        centre.nom = centre.nom.strip()

        if centre.departement in OM_CODES:
            centre.departement = "om"

        if centre.departement not in par_departement:
            logger.warning(
                f"Center {centre.nom} ({centre.departement}) could not be attached to a valid department or collectivity"
            )
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
            "request_counts",
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

    for departement, disponibilités in par_departement.items():
        disponibilités["last_updated"] = dt.datetime.now(tz=pytz.timezone("Europe/Paris")).isoformat()
        if "centres_disponibles" in disponibilités:
            disponibilités["centres_disponibles"] = sorted(
                deduplicates_names(disponibilités["centres_disponibles"]), key=sort_center
            )
        disponibilités["centres_indisponibles"] = deduplicates_names(disponibilités["centres_indisponibles"])
        outpath = outpath_format.format(departement)
        logger.debug(f"writing result to {outpath} file")
        with open(outpath, "w") as outfile:
            outfile.write(json.dumps(disponibilités, indent=2))

    return compte_centres, compte_centres_avec_dispo, bloqués_doctolib


def merge_centers(centers: list, center_dicts):
    for center_dict in center_dicts:
        centers.append(CenterInfo(**center_dict))
    return centers


def merge_platforms():
    platforms = ["doctolib", "ordoclic", "keldoc", "maiia", "mapharma"]
    platform_path = "data/output/pool/{}.json"
    centers = []
    last_scrap = {}
    for platform in platforms:
        fpath = platform_path.format(platform)
        if not os.path.exists(fpath):
            logger.error(f"Unable to find file: {fpath}")
            exit(1)
        file = open(fpath, "r")
        if not file:
            logger.error(f"Unable to open file: {fpath}")
            exit(1)
        data = json.load(file)
        center_count = len(data["centres_disponibles"]) + len(data["centres_indisponibles"])
        last_scrap[platform] = data["last_updated"]
        logger.info(f"[{platform}] found {center_count} centers. (last updated: {data['last_updated']})")
        centers = merge_centers(centers, data["centres_disponibles"])
        centers = merge_centers(centers, data["centres_indisponibles"])
        file.close()
    logger.info(f"Total: found {len(centers)} centers.")
    total, available, blocked = export_data(centers, last_scrap)
    logger.info(f"Exported {total} vaccination locations ({available} available, {blocked} blocked)")
    logger.info(f"Availabilities: {round(available / total * 100, 2)}%")
