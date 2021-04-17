import json
from pathlib import Path
import httpx
from datetime import datetime
from dateutil.parser import isoparse

from scraper.ordoclic import (
    search,
    getReasons,
    getSlots,
    getProfile,
    parse_ordoclic_slots,
    fetch_slots,
    centre_iterator
)

from scraper.pattern.scraper_request import ScraperRequest


def test_search():
    pass


def test_getReasons():
    pass


def test_getSlots():
    pass


def test_getProfile():
    pass


def test_parse_ordoclic_slots():
    # Test availability_data vide
    request = ScraperRequest("", "")
    assert parse_ordoclic_slots(request, {}) == None

    # Test pas de slots disponibles
    empty_slots_file = Path('tests/fixtures/ordoclic/empty_slots.json')
    empty_slots = json.loads(empty_slots_file.read_text())
    request = ScraperRequest("", "")
    assert parse_ordoclic_slots(request, empty_slots) == None

    # Test nextAvailableSlotDate
    nextavailable_slots_file = Path('tests/fixtures/ordoclic/nextavailable_slots.json')
    nextavailable_slots = json.loads(nextavailable_slots_file.read_text())
    request = ScraperRequest("", "")
    assert parse_ordoclic_slots(request, nextavailable_slots) == isoparse("2021-06-12T11:30:00Z")  # timezone CET

    # Test slots disponibles
    full_slots_file = Path('tests/fixtures/ordoclic/full_slots.json')
    full_slots = json.loads(full_slots_file.read_text())
    request = ScraperRequest("", "")
    first_availability = parse_ordoclic_slots(request, full_slots)
    assert first_availability == isoparse("2021-04-19T16:15:00Z")  # timezone CET
    assert request.appointment_count == 42


def test_fetch_slots():
    pass


def test_centre_iterator():
    pass