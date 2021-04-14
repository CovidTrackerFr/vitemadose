import json
from pathlib import Path

from scraper.doctolib.doctolib_center_scrap import parse_doctolib_centers, get_departements, doctolib_urlify
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


def test_doctolib_departements():
    dep = get_departements()
    assert len(dep) == 100


def test_doctolib_urlify():
    url = 'FooBar 42'
    assert doctolib_urlify(url) == 'foobar-42'
