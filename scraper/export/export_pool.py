import datetime as dt
import json
import os
from typing import Iterator

from scraper.error import BlockedByDoctolibError

import pytz

from scraper.pattern.center_info import CenterInfo
from utils.vmd_blocklist import is_in_blocklist, get_blocklist_urls
from utils.vmd_center_sort import sort_center
from utils.vmd_duplicated import deduplicates_names
from utils.vmd_logger import get_logger
from utils.vmd_opendata import copy_omit_keys
from utils.vmd_utils import is_reserved_center

POOL_SIZE = int(os.getenv("POOL_SIZE", 50))
PARTIAL_SCRAPE = float(os.getenv("PARTIAL_SCRAPE", 1.0))
PARTIAL_SCRAPE = max(0, min(PARTIAL_SCRAPE, 1))

logger = get_logger()


def export_pool(centres_cherchés: Iterator[CenterInfo], platform: str, outpath_format="data/output/pool/{}.json"):
    compte_centres = 0
    compte_centres_avec_dispo = 0
    bloqués_doctolib = 0
    centres_open_data = []
    internal_ids = []
    global_data = {
        "version": 1,
        "pool": platform,
        "last_updated": dt.datetime.now(tz=pytz.timezone("Europe/Paris")).isoformat(),
        "centres_disponibles": [],
        "centres_indisponibles": [],
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
        erreur = centre.erreur
        if not centre.plateforme:
            continue
        if centre.plateforme.lower() != platform:
            continue
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
            global_data["centres_disponibles"].append(centre.default())
        else:
            global_data["centres_indisponibles"].append(centre.default())
            if isinstance(erreur, BlockedByDoctolibError):
                global_data["doctolib_bloqué"] = True
                bloqués_doctolib += 1

    global_data["centres_disponibles"] = sorted(deduplicates_names(global_data["centres_disponibles"]), key=sort_center)
    global_data["centres_indisponibles"] = deduplicates_names(global_data["centres_indisponibles"])
    outpath = outpath_format.format(platform)
    with open(outpath, "w") as info_centres:
        json.dump(global_data, info_centres, indent=2)

    return compte_centres, compte_centres_avec_dispo, bloqués_doctolib
