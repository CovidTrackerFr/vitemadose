import os
import json
import traceback
from collections import deque
from multiprocessing import Manager, Pool, Process, Queue  # Use actual Process for Collecting creneau (CPU intensive)
from random import random
from typing import Tuple
import sys
from .export.export_v2 import JSONExporter
from scraper.error import BlockedByDoctolibError, DoublonDoctolib
from scraper.pattern.center_info import CenterInfo
from scraper.pattern.scraper_request import ScraperRequest
from scraper.pattern.scraper_result import ScraperResult, VACCINATION_CENTER
from scraper.profiler import Profiling
from utils.vmd_config import get_conf_platform, get_config
from utils.vmd_logger import enable_logger_for_production, enable_logger_for_debug, log_requests, log_platform_requests
from utils.vmd_utils import fix_scrap_urls, get_last_scans, get_start_date, q_iter, EOQ, DummyQueue, BulkQueue
from .doctolib.doctolib import center_iterator as doctolib_center_iterator
from .doctolib.doctolib import fetch_slots as doctolib_fetch_slots
from .export.export_merge import export_data
from .export.export_pool import export_pool
from .keldoc.keldoc import fetch_slots as keldoc_fetch_slots
from .keldoc.keldoc import center_iterator as keldoc_centre_iterator
from .maiia.maiia import centre_iterator as maiia_centre_iterator
from .maiia.maiia import fetch_slots as maiia_fetch_slots
from .mapharma.mapharma import centre_iterator as mapharma_centre_iterator
from .mapharma.mapharma import fetch_slots as mapharma_fetch_slots
from .opendata.opendata import center_iterator as gouv_centre_iterator
from .ordoclic import centre_iterator as ordoclic_centre_iterator
from .ordoclic import fetch_slots as ordoclic_fetch_slots
from .avecmondoc.avecmondoc import center_iterator as avecmondoc_centre_iterator
from .avecmondoc.avecmondoc import fetch_slots as avecmondoc_fetch_slots
from .mesoigner.mesoigner import center_iterator as mesoigner_centre_iterator
from .mesoigner.mesoigner import fetch_slots as mesoigner_fetch_slots
from .circuit_breaker import CircuitBreakerOffException


POOL_SIZE = int(os.getenv("POOL_SIZE", 50))
PARTIAL_SCRAPE = float(os.getenv("PARTIAL_SCRAPE", 1.0))
PARTIAL_SCRAPE = max(0, min(PARTIAL_SCRAPE, 1))
CRENEAUX_ENABLED = get_config().get("scrape_par_creneaux", False)
logger = enable_logger_for_production()


def scrape_debug(urls):  # pragma: no cover
    enable_logger_for_debug()
    start_date = get_start_date()
    for rdv_site_web in urls:
        rdv_site_web = fix_scrap_urls(rdv_site_web)
        logger.info("scraping URL %s", rdv_site_web)
        try:
            result = fetch_centre_slots(rdv_site_web, start_date)
        except Exception:
            logger.exception(f"erreur lors du traitement")
        logger.info(f'{result.platform!s:16} {result.next_availability or ""!s:32}')
        if result.request.appointment_count:
            logger.debug(f"appointments: {result.request.appointment_count}:\n{result.request.appointment_schedules}")
        log_requests(result.request)


def scrape(platforms=None):  # pragma: no cover

    compte_centres = 0
    compte_centres_avec_dispo = 0
    compte_bloqués = 0
    profiler = Profiling()
    with Manager() as manager:
        with profiler, Pool(POOL_SIZE, **profiler.pool_args()) as pool:
            if CRENEAUX_ENABLED:
                creneau_q = BulkQueue(manager.Queue(maxsize=100))
                export_process = Process(target=export_by_creneau, args=(creneau_q,))
                export_process.start()
            centre_iterator_proportion = (
                (c, creneau_q if CRENEAUX_ENABLED else DummyQueue())
                for c in centre_iterator(platforms=platforms)
                if random() < PARTIAL_SCRAPE
            )
            centres_cherchés = pool.imap_unordered(cherche_prochain_rdv_dans_centre, centre_iterator_proportion, 1)

            centres_cherchés = get_last_scans(centres_cherchés)
            log_platform_requests(centres_cherchés)

        if CRENEAUX_ENABLED:
            creneau_q.put(EOQ)
            export_process.join()

        if platforms:
            for platform in platforms:
                compte_centres, compte_centres_avec_dispo, compte_bloqués, compte_doublons = export_pool(
                    centres_cherchés, platform
                )

                logger.info(
                    f"{compte_centres_avec_dispo} centres de vaccination avaient des disponibilités sur {compte_centres} scannés"
                )
        else:
            compte_centres, compte_centres_avec_dispo, compte_bloqués, compte_doublons = export_data(
                centres_cherchés, []
            )
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


def export_by_creneau(
    creneaux_q,
):

    print(f" ----- EXPORTER RUNNING IN PROCESS {os.getpid()} ------")
    exporter = JSONExporter()
    exporter.export(q_iter(creneaux_q))


def cherche_prochain_rdv_dans_centre(data: Tuple[dict, Queue]) -> CenterInfo:  # pragma: no cover

    centre, creneau_q = data
    # print(centre)
    center_data = CenterInfo.from_csv_data(centre)
    start_date = get_start_date()
    has_error = None
    result = None
    try:
        result = fetch_centre_slots(
            centre["rdv_site_web"],
            centre["platform_is"] if "platform_is" in centre.keys() else None,
            start_date,
            creneau_q=creneau_q,
            center_info=center_data,
            input_data=centre.get("booking"),
        )

        center_data.fill_result(result)

    except BlockedByDoctolibError as blocked_doctolib__error:
        logger.error(
            f"erreur lors du traitement de la ligne avec le gid {centre['gid']} {str(blocked_doctolib__error)}"
        )
        has_error = blocked_doctolib__error

    except DoublonDoctolib as doublon_doctolib:
        logger.warning(f"Exception lors du traitement du centre {centre['gid']} {str(doublon_doctolib)}")
        has_error = doublon_doctolib

    except CircuitBreakerOffException as error:
        logger.error(
            f"circuit '{error.name}' désactivé lors du traîtement de la ligne avec le gid {centre['gid']}: {str(error)}"
        )
        has_error = error
    except Exception:

        logger.error(f"erreur lors du traitement de la ligne avec le gid {centre['gid']}")
        traceback.print_exc()

    center_data.erreur = has_error

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
    return center_data


def get_default_fetch_map():
    return {
        "Doctolib": {
            "urls": get_conf_platform("doctolib").get("recognized_urls", []),
            "scraper_ptr": doctolib_fetch_slots,
        },
        "Keldoc": {
            "urls": get_conf_platform("keldoc").get("recognized_urls", []),
            "scraper_ptr": keldoc_fetch_slots,
        },
        "Maiia": {"urls": get_conf_platform("maiia").get("recognized_urls", []), "scraper_ptr": maiia_fetch_slots},
        "Mapharma": {
            "urls": get_conf_platform("mapharma").get("recognized_urls", []),
            "scraper_ptr": mapharma_fetch_slots,
        },
        "Ordoclic": {
            "urls": get_conf_platform("ordoclic").get("recognized_urls", []),
            "scraper_ptr": ordoclic_fetch_slots,
        },
        "AvecMonDoc": {
            "urls": get_conf_platform("avecmondoc").get("recognized_urls", []),
            "scraper_ptr": avecmondoc_fetch_slots,
        },
        "mesoigner": {
            "platform_name": "mesoigner",
            "scraper_ptr": mesoigner_fetch_slots,
        },
    }


def get_center_platform(center_url: str, center_platform: str = None, fetch_map: dict = None):
    # Determine platform based on visit URL
    platform = None

    if not fetch_map:
        return None
    for scraper_name in fetch_map:
        scraper = fetch_map[scraper_name]

        scrap = sum([1 if url in center_url else 0 for url in scraper.get("urls", [])])
        if center_platform and center_platform in scraper.get("platform_name", []):
            scrap += 1

        if scrap == 0:
            continue
        platform = scraper_name

    return platform


@Profiling.measure("any_slot")
def fetch_centre_slots(
    rdv_site_web, center_platform, start_date, creneau_q, center_info, fetch_map: dict = None, input_data: dict = None
) -> ScraperResult:
    practitioner_type = None
    internal_id = None
    if fetch_map is None:
        # Map platform to implementation.
        # May be overridden for unit testing purposes.
        fetch_map = get_default_fetch_map()
    if center_info.type:
        practitioner_type = center_info.type
    if center_info.internal_id:
        internal_id = center_info.internal_id
    rdv_site_web = fix_scrap_urls(rdv_site_web)
    request = ScraperRequest(
        rdv_site_web, start_date, center_info, internal_id=internal_id, practitioner_type=practitioner_type
    )
    platform = get_center_platform(rdv_site_web, center_platform, fetch_map=fetch_map)

    if not platform:
        return ScraperResult(request, "Autre", None)
    if input_data:
        request.input_data = input_data
    # Dispatch to appropriate implementation.
    fetch_impl = fetch_map[platform]["scraper_ptr"]
    result = ScraperResult(request, platform, None)
    result.next_availability = fetch_impl(request, creneau_q)
    return result


def centre_iterator(platforms=None):  # pragma: no cover
    visited_centers_links = set()
    for center in ialternate(
        ordoclic_centre_iterator(),
        mapharma_centre_iterator(),
        maiia_centre_iterator(),
        avecmondoc_centre_iterator(),
        mesoigner_centre_iterator(),
        doctolib_center_iterator(),
        keldoc_centre_iterator(),
    ):

        platform = get_center_platform(
            center["rdv_site_web"],
            center["platform_is"] if "platform_is" in center.keys() else None,
            get_default_fetch_map(),
        )

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
