import json
from pathlib import Path
import httpx
from datetime import datetime
from dateutil.parser import isoparse
from jsonschema import validate
from jsonschema.exceptions import ValidationError
import pytest

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
    # Test offline
    def app(request: httpx.Request) -> httpx.Response:
        assert request.url.path == '/v1/public/search'
        assert dict(httpx.QueryParams(request.url.query)) == {'page': '1', 'per_page': '10000', 'in.isPublicProfile': 'true', 'in.isCovidVaccineSupported': 'true', 'in.covidOnlineBookingAvailabilities.covidInjection1': 'true' }

        path = Path('tests/fixtures/ordoclic/search.json')
        return httpx.Response(200, json=json.loads(path.read_text()))

    client = httpx.Client(transport=httpx.MockTransport(app))
    data_file = Path('tests/fixtures/ordoclic/search.json')
    data = json.loads(data_file.read_text())
    assert search(client) == data

    # Test erreur HTTP
    def app(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={})

    client = httpx.Client(transport=httpx.MockTransport(app))
    with pytest.raises(httpx.HTTPStatusError):
        search(client)

    # Test online
    schema_file = Path('tests/fixtures/ordoclic/search.schema')
    schema = json.loads(schema_file.read_text())
    live_data = search()
    validate(instance=live_data, schema=schema)


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