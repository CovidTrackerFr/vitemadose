import sys
import csv
import datetime as dt
import io
import json
import os
import traceback
from collections import deque
from multiprocessing import Pool
from typing import Counter, Iterator
from scraper.profiler import Profiling, ProfiledPool

from scraper.error import ScrapeError, BlockedByDoctolibError

import pytz
import requests

from scraper.pattern.center_info import convert_csv_data_to_center_info, CenterInfo
from scraper.pattern.scraper_request import ScraperRequest
from scraper.pattern.scraper_result import ScraperResult, VACCINATION_CENTER
from utils.vmd_logger import enable_logger_for_production, enable_logger_for_debug
from utils.vmd_utils import departementUtils, fix_scrap_urls, is_reserved_center, get_last_scans
from .doctolib.doctolib import fetch_slots as doctolib_fetch_slots
from .doctolib.doctolib import center_iterator as doctolib_center_iterator
from .keldoc.keldoc import fetch_slots as keldoc_fetch_slots
from .maiia.maiia import centre_iterator as maiia_centre_iterator
from .maiia.maiia import fetch_slots as maiia_fetch_slots
from .ordoclic import centre_iterator as ordoclic_centre_iterator
from .ordoclic import fetch_slots as ordoclic_fetch_slots
from .mapharma.mapharma import centre_iterator as mapharma_centre_iterator
from .mapharma.mapharma import fetch_slots as mapharma_fetch_slots
from random import random

POOL_SIZE = int(os.getenv("POOL_SIZE", 50))
PARTIAL_SCRAPE = float(os.getenv("PARTIAL_SCRAPE", 1.0))
PARTIAL_SCRAPE = max(0, min(PARTIAL_SCRAPE, 1))

logger = enable_logger_for_production()


def main():  # pragma: no cover
    if len(sys.argv) == 1:
        scrape()
    else:
        scrape_debug(sys.argv[1:])


def get_start_date():
    return dt.date.today().isoformat()


def scrape_debug(urls):  # pragma: no cover
    enable_logger_for_debug()
    start_date = get_start_date()
    for rdv_site_web in urls:
        rdv_site_web = fix_scrap_urls(rdv_site_web)
        logger.info("scraping URL %s", rdv_site_web)
        try:
            result = fetch_centre_slots(rdv_site_web, start_date)
        except Exception as e:
            logger.exception(f"erreur lors du traitement")
        logger.info(f'{result.platform!s:16} {result.next_availability or ""!s:32}')


def scrape() -> None:  # pragma: no cover
    compte_centres = 0
    compte_centres_avec_dispo = 0
    compte_bloqués = 0
    profiler = Profiling()
    with profiler, Pool(POOL_SIZE, **profiler.pool_args()) as pool:
        centre_iterator_proportion = (c for c in centre_iterator() if random() < PARTIAL_SCRAPE)
        centres_cherchés = pool.imap_unordered(cherche_prochain_rdv_dans_centre, centre_iterator_proportion, 1)

        centres_cherchés = get_last_scans(centres_cherchés)
        compte_centres, compte_centres_avec_dispo, compte_bloqués = export_data(centres_cherchés)

    logger.info(
        f"{compte_centres_avec_dispo} centres de vaccination avaient des disponibilités sur {compte_centres} scannés"
    )
    logger.info(profiler.print_summary())
    if compte_centres_avec_dispo == 0:
        logger.error(
            "Aucune disponibilité n'a été trouvée sur aucun centre, c'est bizarre, alors c'est probablement une erreur"
        )
        exit(code=1)

    if compte_bloqués > 10:
        logger.error(
            "Notre IP a été bloquée par le CDN Doctolib plus de 10 fois. Pour éviter de pousser des données erronées, on s'arrête ici"
        )
        exit(code=2)


def cherche_prochain_rdv_dans_centre(centre: dict) -> CenterInfo:  # pragma: no cover
    center_data = convert_csv_data_to_center_info(centre)
    start_date = get_start_date()
    has_error = None
    result = None
    try:
        result = fetch_centre_slots(centre["rdv_site_web"], start_date)
        center_data.fill_result(result)
    except ScrapeError as scrape_error:
        logger.error(f"erreur lors du traitement de la ligne avec le gid {centre['gid']} {str(scrape_error)}")
        has_error = scrape_error
    except Exception as e:
        logger.error(f"erreur lors du traitement de la ligne avec le gid {centre['gid']}")
        traceback.print_exc()

    if has_error is None:
        logger.info(
            f'{centre.get("gid", "")!s:>8} {center_data.plateforme!s:16} {center_data.prochain_rdv or ""!s:32} {center_data.departement!s:6}'
        )
    else:
        logger.info(
            f'{centre.get("gid", "")!s:>8} {center_data.plateforme!s:16} {"Erreur" or ""!s:32} {center_data.departement!s:6}'
        )

    if result is not None and result.request.url is not None:
        center_data.url = result.request.url.lower()
        if result.request.internal_id is None:
            center_data.internal_id = f'{result.platform.lower()}{centre.get("gid", "")}'

    if "type" in centre:
        center_data.type = centre["type"]
    if not center_data.type:
        center_data.type = VACCINATION_CENTER
    center_data.gid = centre.get("gid", "")
    logger.debug(center_data.default())
    return center_data


def sort_center(center: dict) -> str:
    return center.get("prochain_rdv", "-") if center else "-"


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


@Profiling.measure("Any_slot")
def fetch_centre_slots(rdv_site_web, start_date, fetch_map: dict = None):
    if fetch_map is None:
        # Map platform to implementation.
        # May be overridden for unit testing purposes.
        fetch_map = {
            "Doctolib": {
                "urls": ["https://partners.doctolib.fr", "https://www.doctolib.fr"],
                "scraper_ptr": doctolib_fetch_slots,
            },
            "Keldoc": {
                "urls": ["https://vaccination-covid.keldoc.com", "https://keldoc.com"],
                "scraper_ptr": keldoc_fetch_slots,
            },
            "Maiia": {"urls": ["https://www.maiia.com"], "scraper_ptr": maiia_fetch_slots},
            "Mapharma": {
                "urls": [
                    "https://mapharma.net/",
                ],
                "scraper_ptr": mapharma_fetch_slots,
            },
            "Ordoclic": {
                "urls": [
                    "https://app.ordoclic.fr/",
                ],
                "scraper_ptr": ordoclic_fetch_slots,
            },
        }

    rdv_site_web = fix_scrap_urls(rdv_site_web)
    request = ScraperRequest(rdv_site_web, start_date)

    # Determine platform based on visit URL
    platform = None
    for scraper_name in fetch_map:
        scraper = fetch_map[scraper_name]
        scrap = sum([1 if rdv_site_web.startswith(url) else 0 for url in scraper.get("urls", [])])
        if scrap == 0:
            continue
        platform = scraper_name

    if not platform:
        return ScraperResult(request, "Autre", None)
    # Dispatch to appropriate implementation.
    fetch_impl = fetch_map[platform]["scraper_ptr"]
    result = ScraperResult(request, platform, None)
    result.next_availability = fetch_impl(request)
    return result


def centre_iterator():  # pragma: no cover
    visited_centers_links = set()
    for center in ialternate(
        ordoclic_centre_iterator(),
        mapharma_centre_iterator(),
        maiia_centre_iterator(),
        doctolib_center_iterator(),
        gouv_centre_iterator(),
    ):
        if center["rdv_site_web"] not in visited_centers_links:
            visited_centers_links.add(center["rdv_site_web"])
            yield center


def gouv_centre_iterator(outpath_format="data/output/{}.json"):
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


def copy_omit_keys(d, omit_keys):
    return {k: d[k] for k in set(list(d.keys())) - set(omit_keys)}


def ialternate(*iterators):  # pragma: no cover
    queue = deque(iterators)
    while len(queue) > 0:
        iterator = queue.popleft()
        try:
            yield next(iterator)
            queue.append(iterator)
        except StopIteration:
            pass

def deduplicates_names(departement_centers):
    """
    Removes unique names by appending city name
    in par_departement

    see https://github.com/CovidTrackerFr/vitemadose/issues/173
    """
    deduplicated_centers = []
    departement_center_names_count = Counter([center["nom"] for center in departement_centers])
    names_to_remove = {
        departement for departement in departement_center_names_count if departement_center_names_count[departement] > 1
    }

    for center in departement_centers:
        if center["nom"] in names_to_remove:
            center["nom"] = f"{center['nom']} - {departementUtils.get_city(center['metadata']['address'])}"
        deduplicated_centers.append(center)
    return deduplicated_centers

def is_in_blocklist(center : CenterInfo, blocklist_urls) -> bool:
    return center.url in blocklist_urls

def get_blocklist_urls() -> set:
    path_blocklist = "data/input/centers_blocklist.json"
    centers_blocklist_urls = set([center["url"] for center in json.load(open(path_blocklist))["centers_not_displayed"]])
    return centers_blocklist_urls

def is_in_blocklist(center: CenterInfo, blocklist_urls) -> bool:
    return center.url in blocklist_urls


def get_blocklist_urls() -> set:
    path_blocklist = "data/input/centers_blocklist.json"
    centers_blocklist_urls = set([center["url"] for center in json.load(open(path_blocklist))["centers_not_displayed"]])
    return centers_blocklist_urls


if __name__ == "__main__":  # pragma: no cover
    main()
