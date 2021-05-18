import json
from scraper.pattern.scraper_request import ScraperRequest
from scraper.pattern.center_location import CenterLocation
from scraper.pattern.center_info import CenterInfo
import httpx
from pathlib import Path
from jsonschema import validate
from jsonschema.exceptions import ValidationError
from datetime import datetime
from dateutil.tz import tzutc

from scraper.avecmondoc import avecmondoc

def test_search():
    # Test offline
    def app(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/Doctors/search"
        assert dict(httpx.QueryParams(request.url.query)) == {
            "params": json.dumps({
                "city": None,
                "gps": None,
                "dateBefore": None
            }),
            "options": json.dumps({
                "limit": 1000,
                "page": 1,
                "distance": None
            })
        }

        path = Path("tests/fixtures/avecmondoc/search-result.json")
        return httpx.Response(200, json=json.loads(path.read_text(encoding='utf8')))

    client = httpx.Client(transport=httpx.MockTransport(app))
    data_file = Path("tests/fixtures/avecmondoc/search-result.json")
    data = json.loads(data_file.read_text(encoding='utf8'))
    assert avecmondoc.search(client=client) == data

    # Test erreur HTTP
    def response_unavailable(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={})

    client = httpx.Client(transport=httpx.MockTransport(response_unavailable))
    assert avecmondoc.search(client) is None

    # Test timeout
    def response_timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException(message="Timeout", request=request)

    client = httpx.Client(transport=httpx.MockTransport(response_timeout))
    assert avecmondoc.search(client) is None

    # Test online
    schema_file = Path("tests/fixtures/avecmondoc/search-result.schema")
    schema = json.loads(schema_file.read_text())
    live_data = avecmondoc.search()
    if live_data:
        validate(instance=live_data, schema=schema)


def test_get_doctor_slug():
    def app(request: httpx.Request) -> httpx.Response:
        assert  request.url.path == "/api/Doctors/slug/delphine-rousseau-216"
        path = Path("tests/fixtures/avecmondoc/get_doctor_slug.json")
        return httpx.Response(200, json=json.loads(path.read_text(encoding='utf8')))

    client = httpx.Client(transport=httpx.MockTransport(app))
    data_file = Path("tests/fixtures/avecmondoc/get_doctor_slug.json")
    data = json.loads(data_file.read_text(encoding='utf8'))
    assert avecmondoc.get_doctor_slug("delphine-rousseau-216", client=client) == data


def test_get_organization_slug():
    def app(request: httpx.Request) -> httpx.Response:
        assert  request.url.path == "/api/Organizations/slug/delphine-rousseau-159"
        path = Path("tests/fixtures/avecmondoc/get_organization_slug.json")
        return httpx.Response(200, json=json.loads(path.read_text(encoding='utf8')))

    client = httpx.Client(transport=httpx.MockTransport(app))
    data_file = Path("tests/fixtures/avecmondoc/get_organization_slug.json")
    data = json.loads(data_file.read_text(encoding='utf8'))
    assert avecmondoc.get_organization_slug("delphine-rousseau-159", client=client) == data


def test_get_by_doctor():
    def app(request: httpx.Request) -> httpx.Response:
        assert  request.url.path == "/api/Organizations/getByDoctor/216"
        path = Path("tests/fixtures/avecmondoc/get_by_doctor.json")
        return httpx.Response(200, json=json.loads(path.read_text(encoding='utf8')))

    client = httpx.Client(transport=httpx.MockTransport(app))
    data_file = Path("tests/fixtures/avecmondoc/get_by_doctor.json")
    data = json.loads(data_file.read_text(encoding='utf8'))
    assert avecmondoc.get_by_doctor(216, client=client) == data


def test_get_by_organization():
    def app(request: httpx.Request) -> httpx.Response:
        assert  request.url.path == "/api/Doctors/getByOrganization/159"
        path = Path("tests/fixtures/avecmondoc/get_by_organization.json")
        return httpx.Response(200, json=json.loads(path.read_text(encoding='utf8')))

    client = httpx.Client(transport=httpx.MockTransport(app))
    data_file = Path("tests/fixtures/avecmondoc/get_by_organization.json")
    data = json.loads(data_file.read_text(encoding='utf8'))
    assert avecmondoc.get_by_organization(159, client=client) == data


def test_get_reasons():
    def app(request: httpx.Request) -> httpx.Response:
        assert  request.url.path == "/api/Organizations/getConsultationReasons"
        assert dict(httpx.QueryParams(request.url.query)) == {
            "params": json.dumps({
                "organizationId": 159,
                "doctorId": 216
            })
        }
        path = Path("tests/fixtures/avecmondoc/get_reasons.json")
        return httpx.Response(200, json=json.loads(path.read_text(encoding='utf8')))

    client = httpx.Client(transport=httpx.MockTransport(app))
    data_file = Path("tests/fixtures/avecmondoc/get_reasons.json")
    data = json.loads(data_file.read_text(encoding='utf8'))
    assert avecmondoc.get_reasons(159, 216, client=client) == data


def test_organization_to_center():
    data_file = Path("tests/fixtures/avecmondoc/get_organization_slug.json")
    data = json.loads(data_file.read_text(encoding='utf8'))
    center = CenterInfo(
        "28", 
        "Delphine ROUSSEAU", 
        "https://patient.avecmondoc.com/fiche/structure/delphine-rousseau-159"
    )
    center.metadata = {
        "address": "21 Rue Nicole 28000 Chartres",
        "phone_number": "0033143987678",
        "business_hours": {
            "Lundi": "08:30-12:30 13:30-17:00",
            "Mardi": "08:30-12:30 13:30-17:00",
            "Mercredi": "08:30-12:30 13:30-17:00",
            "Jeudi": "08:30-12:30 13:30-17:00",
            "Vendredi": "08:30-12:30 13:30-17:00",
            "Samedi": "",
            "Dimanche": "",
            }
    }
    center.location = CenterLocation(1.481373, 48.447586, "Chartres", "28000")
    center.internal_id = "amd159"
    assert avecmondoc.organization_to_center(data).default() == center.default()


def test_get_valid_reasons():
    reasons = [
        {
            "reason": "Première injection vaccinale COVID-19",
            "id": 604,
        },
        {
            "reason": "Seconde injection vaccinale COVID-19",
            "id": 605,
        },
        {
            "reason": "Vaccination grippe",
            "id": 606
        }
    ]
    assert avecmondoc.get_valid_reasons(reasons) == [
        {
            "reason": "Première injection vaccinale COVID-19",
            "id": 604,
        }
    ]


def test_get_availabilities():
    def app(request: httpx.Request) -> httpx.Response:
        assert  request.url.path == "/api/BusinessHours/availabilitiesPerDay"
        payload = json.loads(request.content)
        if payload.get("periodStart", "") == "2021-05-20T00:00:00.000Z":
            path = Path("tests/fixtures/avecmondoc/get_availabilities_week1.json")
        else:
            path = Path("tests/fixtures/avecmondoc/get_availabilities_week2.json")
        return httpx.Response(200, json=json.loads(path.read_text(encoding='utf8')))


    client = httpx.Client(transport=httpx.MockTransport(app))
    data_file = Path("tests/fixtures/avecmondoc/get_availabilities.json")
    data = json.loads(data_file.read_text(encoding='utf8'))
    assert avecmondoc.get_availabilities(604, 159, datetime(2021, 5, 20), datetime(2021, 6, 1), client=client) == data


def test_get_availabilities_week():
    def app(request: httpx.Request) -> httpx.Response:
        assert  request.url.path == "/api/BusinessHours/availabilitiesPerDay"
        payload = json.loads(request.content)
        if payload.get("periodStart", "") == "2021-05-20T00:00:00.000Z":
            assert payload == {
                "consultationReasonId": 604,
                "disabledPeriods": [],
                "fullDisplay": True,
                "organizationId": 159,
                "periodEnd":"2021-05-26T00:00:00.000Z",
                "periodStart":"2021-05-20T00:00:00.000Z",
                "type":"inOffice"
            }
            path = Path("tests/fixtures/avecmondoc/get_availabilities_week1.json")
        else:
            assert payload == {
                "consultationReasonId": 604,
                "disabledPeriods": [],
                "fullDisplay": True,
                "organizationId": 159,
                "periodEnd":"2021-06-01T00:00:00.000Z",
                "periodStart":"2021-05-26T00:00:00.000Z",
                "type":"inOffice"
            }
            path = Path("tests/fixtures/avecmondoc/get_availabilities_week2.json")
        return httpx.Response(200, json=json.loads(path.read_text(encoding='utf8')))

    client = httpx.Client(transport=httpx.MockTransport(app))

    data_file = Path("tests/fixtures/avecmondoc/get_availabilities_week1.json")
    data = json.loads(data_file.read_text(encoding='utf8'))
    assert avecmondoc.get_availabilities_week(604, 159, datetime(2021, 5, 20), client=client) == data

    data_file = Path("tests/fixtures/avecmondoc/get_availabilities_week2.json")
    data = json.loads(data_file.read_text(encoding='utf8'))
    assert avecmondoc.get_availabilities_week(604, 159, datetime(2021, 5, 26), client=client) == data


def test_parse_availabilities():
    data_file = Path("tests/fixtures/avecmondoc/get_availabilities.json")
    data = json.loads(data_file.read_text(encoding='utf8'))
    first_appointment, appointment_count = avecmondoc.parse_availabilities(data)
    assert  first_appointment == datetime(2021, 5, 20, 9, 0, tzinfo=tzutc())
    assert appointment_count == 12


def test_fetch_slots():
    def app(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/BusinessHours/availabilitiesPerDay":
            path = Path("tests/fixtures/avecmondoc/get_availabilities.json")
            return httpx.Response(200, json=json.loads(path.read_text(encoding='utf8')))
        if request.url.path == "/api/Organizations/slug/delphine-rousseau-159":
            path = Path("tests/fixtures/avecmondoc/get_organization_slug.json")
            return httpx.Response(200, json=json.loads(path.read_text(encoding='utf8')))
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(app))
    url = "https://patient.avecmondoc.com/fiche/structure/delphine-rousseau-159"
    request = ScraperRequest(url, "2021-05-20")
    first_availability = avecmondoc.fetch_slots(request, client)
    assert first_availability == "2021-05-20T09:00:00+00:00"
    assert request.appointment_count == 108
    assert request.vaccine_type == ["Pfizer-BioNTech"]

def test_center_to_centerdict():
    center = CenterInfo(
        "28", 
        "Delphine ROUSSEAU", 
        "https://patient.avecmondoc.com/fiche/structure/delphine-rousseau-159"
    )
    center.metadata = {
        "address": "21 Rue Nicole 28000 Chartres",
        "phone_number": "0033143987678",
        "business_hours": {
            "Lundi": "08:30-12:30 13:30-17:00",
            "Mardi": "08:30-12:30 13:30-17:00",
            "Mercredi": "08:30-12:30 13:30-17:00",
            "Jeudi": "08:30-12:30 13:30-17:00",
            "Vendredi": "08:30-12:30 13:30-17:00",
            "Samedi": "",
            "Dimanche": "",
            }
    }
    center.location = CenterLocation(1.481373, 48.447586, "Chartres", "28000")
    center.internal_id = "amd159"

    data_file = Path("tests/fixtures/avecmondoc/centerdict.json")
    data = json.loads(data_file.read_text(encoding='utf8'))
    
    assert avecmondoc.center_to_centerdict(center) == data


def test_has_valid_zipcode():
    assert avecmondoc.has_valid_zipcode({"zipCode": "63000"}) == True
    assert avecmondoc.has_valid_zipcode({"zipCode": "6000"}) == False
    assert avecmondoc.has_valid_zipcode({"zipCode": None}) == False


def test_center_iterator():
    def app(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/Doctors/search":
            path = Path("tests/fixtures/avecmondoc/iterator_search_result.json")
            return httpx.Response(200, json=json.loads(path.read_text(encoding='utf8')))
        elif request.url.path == "/api/Organizations/slug/delphine-rousseau-159":
            path = Path("tests/fixtures/avecmondoc/get_organization_slug.json")
            return httpx.Response(200, json=json.loads(path.read_text(encoding='utf8')))
        elif request.url.path == "/api/Organizations/getConsultationReasons":
            path = Path("tests/fixtures/avecmondoc/get_reasons.json")
            return httpx.Response(200, json=json.loads(path.read_text(encoding='utf8')))
        elif request.url.path == "/api/Organizations/getByDoctor/216":
            path = Path("tests/fixtures/avecmondoc/get_by_doctor.json")
            return httpx.Response(200, json=json.loads(path.read_text(encoding='utf8')))
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(app))
    centres = [centre for centre in avecmondoc.center_iterator(client)]
    assert len(centres) > 0
    data_file = Path("tests/fixtures/avecmondoc/centerdict.json")
    data = json.loads(data_file.read_text(encoding='utf8'))
    assert centres[0] == data
