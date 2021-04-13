import json
from pathlib import Path

from scraper.doctolib.doctolib_center_scrap import parse_doctolib_centers
from scraper.error import BlockedByDoctolibError

import httpx
from scraper.doctolib.doctolib import (
    DoctolibSlots,
    _find_agenda_and_practice_ids,
    _find_visit_motive_category_id,
    _find_visit_motive_id,
    _parse_centre,
    _parse_practice_id,
    DOCTOLIB_SLOT_LIMIT,
)


# -- Tests de l'API (offline) --
from scraper.pattern.scraper_request import ScraperRequest


def test_doctolib_scraper():
    data = parse_doctolib_centers(page_limit=1)
    assert len(data) > 0