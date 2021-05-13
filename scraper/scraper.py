import os
import traceback
from collections import deque
from multiprocessing import Pool
from pprint import pformat
from random import random

from scraper.error import ScrapeError
from scraper.pattern.center_info import convert_csv_data_to_center_info, CenterInfo
from scraper.pattern.scraper_request import ScraperRequest
from scraper.pattern.scraper_result import ScraperResult, VACCINATION_CENTER
from scraper.profiler import Profiling
from utils.vmd_logger import enable_logger_for_production, enable_logger_for_debug
from utils.vmd_utils import fix_scrap_urls, get_last_scans, get_start_date
from .doctolib.doctolib import center_iterator as doctolib_center_iterator
from .doctolib.doctolib import fetch_slots as doctolib_fetch_slots
from .export.export_merge import export_data
from .export.export_pool import export_pool
from .keldoc.keldoc import fetch_slots as keldoc_fetch_slots
from .maiia.maiia import centre_iterator as maiia_centre_iterator
from .maiia.maiia import fetch_slots as maiia_fetch_slots
from .manual.manual_urls import manual_urls_iterator
from .mapharma.mapharma import centre_iterator as mapharma_centre_iterator
from .mapharma.mapharma import fetch_slots as mapharma_fetch_slots
from .opendata.opendata import center_iterator as gouv_centre_iterator
from .ordoclic import centre_iterator as ordoclic_centre_iterator
from .ordoclic import fetch_slots as ordoclic_fetch_slots

POOL_SIZE = int(os.getenv("POOL_SIZE", 50))
PARTIAL_SCRAPE = float(os.getenv("PARTIAL_SCRAPE", 1.0))
PARTIAL_SCRAPE = max(0, min(PARTIAL_SCRAPE, 1))

logger = enable_logger_for_production()


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
        if result.request.appointment_count:
            logger.debug(f'appointments: {result.request.appointment_count}:\n{pformat(result.request.appointment_schedules)}')


def scrape(platforms=None) -> None:  # pragma: no cover
    compte_centres = 0
    compte_centres_avec_dispo = 0
    compte_bloqués = 0
    profiler = Profiling()
    with profiler, Pool(POOL_SIZE, **profiler.pool_args()) as pool:
        centre_iterator_proportion = (c for c in centre_iterator(platforms=platforms) if random() < PARTIAL_SCRAPE)
        centres_cherchés = pool.imap_unordered(cherche_prochain_rdv_dans_centre, centre_iterator_proportion, 1)

        centres_cherchés = get_last_scans(centres_cherchés)
        if platforms:
            for platform in platforms:
                compte_centres, compte_centres_avec_dispo, compte_bloqués = export_pool(centres_cherchés, platform)

                logger.info(
                    f"{compte_centres_avec_dispo} centres de vaccination avaient des disponibilités sur {compte_centres} scannés"
                )
        else:
            compte_centres, compte_centres_avec_dispo, compte_bloqués = export_data(centres_cherchés, [])
            logger.info(
                f"{compte_centres_avec_dispo} centres de vaccination avaient des disponibilités sur {compte_centres} scannés"
            )
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

    logger.info(profiler.print_summary())

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


def get_default_fetch_map():
    return {
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


def get_center_platform(center_url: str, fetch_map: dict = None):
    # Determine platform based on visit URL
    platform = None

    if not fetch_map:
        return None
    for scraper_name in fetch_map:
        scraper = fetch_map[scraper_name]
        scrap = sum([1 if center_url.startswith(url) else 0 for url in scraper.get("urls", [])])
        if scrap == 0:
            continue
        platform = scraper_name
    return platform


@Profiling.measure("Any_slot")
def fetch_centre_slots(rdv_site_web, start_date, fetch_map: dict = None) -> ScraperResult:
    if fetch_map is None:
        # Map platform to implementation.
        # May be overridden for unit testing purposes.
        fetch_map = get_default_fetch_map()

    rdv_site_web = fix_scrap_urls(rdv_site_web)
    request = ScraperRequest(rdv_site_web, start_date)
    platform = get_center_platform(rdv_site_web, fetch_map=fetch_map)

    if not platform:
        return ScraperResult(request, "Autre", None)
    # Dispatch to appropriate implementation.
    fetch_impl = fetch_map[platform]["scraper_ptr"]
    result = ScraperResult(request, platform, None)
    result.next_availability = fetch_impl(request)
    return result


def centre_iterator(platforms=None):  # pragma: no cover
    visited_centers_links = set()
    for center in ialternate(
        manual_urls_iterator(),
        ordoclic_centre_iterator(),
        mapharma_centre_iterator(),
        maiia_centre_iterator(),
        doctolib_center_iterator(),
        gouv_centre_iterator()
    ):
        platform = get_center_platform(center["rdv_site_web"], get_default_fetch_map())
        if platforms and platform and platform.lower() not in platforms:
            continue
        if center["rdv_site_web"] not in visited_centers_links:
            visited_centers_links.add(center["rdv_site_web"])
            yield center


def ialternate(*iterators):  # pragma: no cover
    queue = deque(iterators)
    while len(queue) > 0:
        iterator = queue.popleft()
        try:
            yield next(iterator)
            queue.append(iterator)
        except StopIteration:
            pass
