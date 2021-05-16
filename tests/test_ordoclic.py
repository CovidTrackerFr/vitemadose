import json
import re
from pathlib import Path
import httpx
from dateutil.parser import isoparse
from jsonschema import validate

from scraper.ordoclic import (
    search,
    get_reasons,
    get_profile,
    parse_ordoclic_slots,
    fetch_slots,
    centre_iterator,
    is_reason_valid,
)

from scraper.pattern.scraper_request import ScraperRequest


def test_search():
    # Test offline
    def app(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/public/search"
        assert dict(httpx.QueryParams(request.url.query)) == {
            "page": "1",
            "per_page": "10000",
            "in.isPublicProfile": "true",
            "in.isCovidVaccineSupported": "true",
            "or.covidOnlineBookingAvailabilities.vaccineAstraZeneca1": "true",
            "or.covidOnlineBookingAvailabilities.vaccineJanssen1": "true",
            "or.covidOnlineBookingAvailabilities.vaccinePfizer1": "true",
            "or.covidOnlineBookingAvailabilities.vaccineModerna1": "true",
        }

        path = Path("tests/fixtures/ordoclic/search.json")
        return httpx.Response(200, json=json.loads(path.read_text()))

    client = httpx.Client(transport=httpx.MockTransport(app))
    data_file = Path("tests/fixtures/ordoclic/search.json")
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
    schema_file = Path("tests/fixtures/ordoclic/search.schema")
    schema = json.loads(schema_file.read_text())
    live_data = search()
    validate(instance=live_data, schema=schema)


def test_getReasons():
    # Test offline
    def app(request: httpx.Request) -> httpx.Response:
        assert (
            re.match(
                r"/v1/solar/entities/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/reasons",
                request.url.path,
            )
            != None
        )

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


def test_get_slots():
    request = ScraperRequest("https://app.ordoclic.fr/app/pharmacie/pharmacie-de-la-mairie-meru-meru", "2021-05-08")
    data = {"id": 1}
    assert not parse_ordoclic_slots(request, data)

    request = ScraperRequest("https://app.ordoclic.fr/app/pharmacie/pharmacie-de-la-mairie-meru-meru", "2021-05-08")
    data = {"slots": [{"timeEnd": "2021-05-09"}]}
    assert not parse_ordoclic_slots(request, data)


def test_get_profile():
    # Timeout test (profile)
    def app4(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException(message="Timeout", request=request)

    client = httpx.Client(transport=httpx.MockTransport(app4))
    request = ScraperRequest("https://app.ordoclic.fr/app/pharmacie/pharmacie-de-la-mairie-meru-meru", "2021-05-08")
    res = get_profile(request, client)
    assert not res

    # HTTP error test (profile)
    def app5(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={})

    client = httpx.Client(transport=httpx.MockTransport(app5))
    request = ScraperRequest("https://app.ordoclic.fr/app/pharmacie/pharmacie-de-la-mairie-meru-meru", "2021-05-08")
    res = get_profile(request, client)
    assert not res


def test_parse_ordoclic_slots():
    # Test availability_data vide
    request = ScraperRequest("", "2021-04-05")
    assert parse_ordoclic_slots(request, {}) == None

    # Test pas de slots disponibles
    empty_slots_file = Path("tests/fixtures/ordoclic/empty_slots.json")
    empty_slots = json.loads(empty_slots_file.read_text())
    request = ScraperRequest("", "2021-04-05")
    assert parse_ordoclic_slots(request, empty_slots) == None

    # Test nextAvailableSlotDate
    nextavailable_slots_file = Path("tests/fixtures/ordoclic/nextavailable_slots.json")
    nextavailable_slots = json.loads(nextavailable_slots_file.read_text())
    request = ScraperRequest("", "2021-04-05")
    assert parse_ordoclic_slots(request, nextavailable_slots) == isoparse("2021-06-12T11:30:00Z")  # timezone CET

    # Test slots disponibles
    full_slots_file = Path("tests/fixtures/ordoclic/full_slots.json")
    full_slots = json.loads(full_slots_file.read_text())
    request = ScraperRequest("", "2021-04-05")
    first_availability = parse_ordoclic_slots(request, full_slots)
    assert first_availability == isoparse("2021-04-19T16:15:00Z")  # timezone CET
    assert request.appointment_count == 42


def test_fetch_slots():
    pass


def test_centre_iterator():
    pass


def test_is_reason_valid():
    # Can't book online
    data = {"canBookOnline": False}
    assert not is_reason_valid(data)

    # Can't book online
    data = {"canBookOnline": True, "vaccineInjectionDose": 2}
    assert not is_reason_valid(data)

    # First injection
    data = {"canBookOnline": True, "vaccineInjectionDose": 1}
    assert is_reason_valid(data)

    # Mix-up
    data = {"vaccineInjectionDose": 1, "canBookOnline": False}
    assert not is_reason_valid(data)

    # No data
    assert not is_reason_valid({})


def test_center_iterator():
    def app(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/public/search"
        assert dict(httpx.QueryParams(request.url.query)) == {
            "page": "1",
            "per_page": "10000",
            "in.isPublicProfile": "true",
            "in.isCovidVaccineSupported": "true",
            "or.covidOnlineBookingAvailabilities.vaccineAstraZeneca1": "true",
            "or.covidOnlineBookingAvailabilities.vaccineJanssen1": "true",
            "or.covidOnlineBookingAvailabilities.vaccinePfizer1": "true",
            "or.covidOnlineBookingAvailabilities.vaccineModerna1": "true",
        }

        path = Path("tests/fixtures/ordoclic/search.json")
        return httpx.Response(200, json=json.loads(path.read_text(encoding="utf8")))

    client = httpx.Client(transport=httpx.MockTransport(app))
    generated = list(centre_iterator(client))
    result_path = Path("tests/fixtures/ordoclic/search-result.json")
    expected = json.loads(result_path.read_text())
    assert generated == expected


def test_fetch_slots():
    # Basic full working test
    def app(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/public/entities/profile/pharmacie-oceane-paris":
            return httpx.Response(
                200, json=json.loads(Path("tests/fixtures/ordoclic/fetchslot-profile.json").read_text())
            )
        if request.url.path == "/v1/solar/entities/03674d71-b200-4682-8e0a-3ab9687b2b59/reasons":
            return httpx.Response(
                200, json=json.loads(Path("tests/fixtures/ordoclic/fetchslot-reasons.json").read_text())
            )
        if request.url.path == "/v1/solar/slots/availableSlots":
            return httpx.Response(
                200, json=json.loads(Path("tests/fixtures/ordoclic/fetchslot-slots.json").read_text())
            )
        return httpx.Response(403, json={})

    client = httpx.Client(transport=httpx.MockTransport(app))
    request = ScraperRequest("https://app.ordoclic.fr/app/pharmacie/pharmacie-oceane-paris", "2021-05-08")
    res = fetch_slots(request, client)
    assert res == "2021-05-12T16:00:00+00:00"

    # Timeout test
    def app2(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/public/entities/profile/pharmacie-oceane-paris":
            return httpx.Response(
                200, json=json.loads(Path("tests/fixtures/ordoclic/fetchslot-profile.json").read_text())
            )
        if request.url.path == "/v1/solar/entities/03674d71-b200-4682-8e0a-3ab9687b2b59/reasons":
            return httpx.Response(
                200, json=json.loads(Path("tests/fixtures/ordoclic/fetchslot-reasons.json").read_text())
            )
        if request.url.path == "/v1/solar/slots/availableSlots":
            raise httpx.TimeoutException(message="Timeout", request=request)
        return httpx.Response(403, json={})

    client = httpx.Client(transport=httpx.MockTransport(app2))
    request = ScraperRequest("https://app.ordoclic.fr/app/pharmacie/pharmacie-oceane-paris", "2021-05-08")
    res = fetch_slots(request, client)
    assert res is None

    # HTTP error test (available slots)
    def app3(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/public/entities/profile/pharmacie-oceane-paris":
            return httpx.Response(
                200, json=json.loads(Path("tests/fixtures/ordoclic/fetchslot-profile.json").read_text())
            )
        if request.url.path == "/v1/solar/entities/03674d71-b200-4682-8e0a-3ab9687b2b59/reasons":
            return httpx.Response(
                200, json=json.loads(Path("tests/fixtures/ordoclic/fetchslot-reasons.json").read_text())
            )
        return httpx.Response(403, json={})

    client = httpx.Client(transport=httpx.MockTransport(app3))
    request = ScraperRequest("https://app.ordoclic.fr/app/pharmacie/pharmacie-oceane-paris", "2021-05-08")
    res = fetch_slots(request, client)
    assert res is None

    # HTTP error test (profile)
    def app4(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={})

    client = httpx.Client(transport=httpx.MockTransport(app4))
    request = ScraperRequest("https://app.ordoclic.fr/app/pharmacie/pharmacie-oceane-paris", "2021-05-08")
    res = fetch_slots(request, client)
    assert res is None

    # Only appointments by phone test
    def app5(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/public/entities/profile/pharmacie-oceane-paris":
            return httpx.Response(
                200, json=json.loads(Path("tests/fixtures/ordoclic/fetchslot-profile2.json").read_text())
            )
        if request.url.path == "/v1/solar/entities/03674d71-b200-4682-8e0a-3ab9687b2b59/reasons":
            return httpx.Response(
                200, json=json.loads(Path("tests/fixtures/ordoclic/fetchslot-reasons.json").read_text())
            )
        if request.url.path == "/v1/solar/slots/availableSlots":
            return httpx.Response(
                200, json=json.loads(Path("tests/fixtures/ordoclic/fetchslot-slots.json").read_text())
            )
        return httpx.Response(403, json={})

    client = httpx.Client(transport=httpx.MockTransport(app5))
    request = ScraperRequest("https://app.ordoclic.fr/app/pharmacie/pharmacie-oceane-paris", "2021-05-08")
    res = fetch_slots(request, client)
    assert res is None
