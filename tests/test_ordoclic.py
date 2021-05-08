import json
import re
from pathlib import Path
import httpx
from datetime import datetime
from dateutil.parser import isoparse
from jsonschema import validate
from jsonschema.exceptions import ValidationError
import pytest

from scraper.ordoclic import (
    search,
    get_reasons,
    get_slots,
    get_profile,
    parse_ordoclic_slots,
    fetch_slots,
    centre_iterator, is_reason_valid
)

from scraper.pattern.scraper_request import ScraperRequest
from scraper.pattern.scraper_result import INTERVAL_SPLIT_DAYS


def test_search():
    # Test offline
    def app(request: httpx.Request) -> httpx.Response:
        assert request.url.path == '/v1/public/search'
        assert dict(httpx.QueryParams(request.url.query)) == {
            'page': '1',
            'per_page': '10000',
            'in.isPublicProfile': 'true',
            'in.isCovidVaccineSupported': 'true',
            'or.covidOnlineBookingAvailabilities.Vaccination AstraZeneca': 'true',
            'or.covidOnlineBookingAvailabilities.Vaccination Pfizer': 'true',
        }

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
    assert search(client) is None

    # Test timeout
    def app2(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException(message="Timeout", request=request)

    client = httpx.Client(transport=httpx.MockTransport(app2))
    assert search(client) is None

    # Test online
    schema_file = Path('tests/fixtures/ordoclic/search.schema')
    schema = json.loads(schema_file.read_text())
    live_data = search()
    validate(instance=live_data, schema=schema)


def test_getReasons():
    # Test offline
    def app(request: httpx.Request) -> httpx.Response:
        assert re.match(
            r"/v1/solar/entities/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/reasons",
            request.url.path,
        ) != None

        path = Path("tests/fixtures/ordoclic/reasons.json")
        return httpx.Response(200, json=json.loads(path.read_text()))

    client = httpx.Client(transport=httpx.MockTransport(app))
    data_file = Path("tests/fixtures/ordoclic/reasons.json")
    data = json.loads(data_file.read_text())
    assert get_reasons("e9c4990e-711f-4af6-aee2-354de59c9e4e", client) == data

    # Test erreur HTTP
    def app(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={})

    client = httpx.Client(transport=httpx.MockTransport(app))
    assert get_reasons("e9c4990e-711f-4af6-aee2-354de59c9e4e", client) is None

    # Test timeout
    def app2(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException(message="Timeout", request=request)

    client = httpx.Client(transport=httpx.MockTransport(app2))
    assert get_reasons("e9c4990e-711f-4af6-aee2-354de59c9e4e", client) is None

    # Test online
    schema_file = Path("tests/fixtures/ordoclic/reasons.schema")
    schema = json.loads(schema_file.read_text())
    live_data = get_reasons("e9c4990e-711f-4af6-aee2-354de59c9e4e")
    validate(instance=live_data, schema=schema)


def test_getSlots():
    pass


def test_getProfile():
    pass


def fill_appointment_schedule(request: ScraperRequest):
    appointment_schedules = {}
    for n in INTERVAL_SPLIT_DAYS:
        appointment_schedules[f"{n}_days"] = 0
        request.update_appointment_schedules(appointment_schedules)
    return appointment_schedules


def test_parse_ordoclic_slots():
    # Test availability_data vide
    request = ScraperRequest("", "2021-04-05")
    assert parse_ordoclic_slots(request, {}) == None

    # Test pas de slots disponibles
    empty_slots_file = Path('tests/fixtures/ordoclic/empty_slots.json')
    empty_slots = json.loads(empty_slots_file.read_text())
    request = ScraperRequest("", "2021-04-05")
    fill_appointment_schedule(request)
    assert parse_ordoclic_slots(request, empty_slots) == None

    # Test nextAvailableSlotDate
    nextavailable_slots_file = Path('tests/fixtures/ordoclic/nextavailable_slots.json')
    nextavailable_slots = json.loads(nextavailable_slots_file.read_text())
    request = ScraperRequest("", "2021-04-05")
    fill_appointment_schedule(request)
    assert parse_ordoclic_slots(request, nextavailable_slots) == isoparse("2021-06-12T11:30:00Z")  # timezone CET

    # Test slots disponibles
    full_slots_file = Path('tests/fixtures/ordoclic/full_slots.json')
    full_slots = json.loads(full_slots_file.read_text())
    request = ScraperRequest("", "2021-04-05")
    fill_appointment_schedule(request)
    first_availability = parse_ordoclic_slots(request, full_slots)
    assert first_availability == isoparse("2021-04-19T16:15:00Z")  # timezone CET
    assert request.appointment_count == 42


def test_fetch_slots():
    pass


def test_centre_iterator():
    pass


def test_is_reason_valid():
    # Can't book online
    data = {
        "canBookOnline": False
    }
    assert not is_reason_valid(data)

    # Can't book online
    data = {
        "canBookOnline": True,
        "vaccineInjectionDose": 2
    }
    assert not is_reason_valid(data)

    # First injection
    data = {
        "canBookOnline": True,
        "vaccineInjectionDose": 1
    }
    assert is_reason_valid(data)

    # Mix-up
    data = {
        "vaccineInjectionDose": 1,
        "canBookOnline": False
    }
    assert not is_reason_valid(data)

    # No data
    assert not is_reason_valid({})
