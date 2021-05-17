# -- Tests de l'API (offline) --
import datetime
import json
from pathlib import Path
import datetime as dt
import httpx
import pytest
from .utils import mock_datetime_now
from scraper.keldoc import keldoc
from scraper.keldoc.keldoc import fetch_slots
from scraper.keldoc.keldoc_center import KeldocCenter, DEFAULT_CLIENT
from scraper.keldoc.keldoc_filters import (
    get_relevant_vaccine_specialties_id,
    filter_vaccine_motives,
    is_appointment_relevant,
    is_specialty_relevant,
    parse_keldoc_availability,
)
from scraper.pattern.scraper_request import ScraperRequest

CENTER1_KELDOC = {
    "/api/patients/v2/clinics/2563/specialties/144/cabinets": "center1-cabinet",
    "/api/patients/v2/clinics/2563/specialties/144/cabinets/18780/motive_categories": "center1-cabinet-18780",
    "/api/patients/v2/clinics/2563/specialties/144/cabinets/16910/motive_categories": "center1-cabinet-16910",
    "/api/patients/v2/clinics/2563/specialties/144/cabinets/16913/motive_categories": "center1-cabinet-16913",
    "/api/patients/v2/timetables/81484": "center1-timetable-81484",
    "/api/patients/v2/timetables/81486": "center1-timetable-81486",
    "/api/patients/v2/timetables/81466": "center1-timetable-81466",
    "/api/patients/v2/timetables/82874": "center1-timetable-82874",
    "/api/patients/v2/timetables/89798": "center1-timetable-89798",
    "/api/patients/v2/searches/resource": "center1-info",
}


def online_keldoc_test():
    request = ScraperRequest(
        "https://www.keldoc.com/cabinet-medical/grenoble-38000/centre-de-vaccination-universite-inter-age-du-dauphine-uiad",
        "2021-04-13",
    )

    fetch_slots(request)


def get_test_data(file_name):
    path = Path("tests", "fixtures", "keldoc", f"{file_name}.json")
    return json.loads(path.read_text(encoding="utf-8"))


def app_center1(request: httpx.Request) -> httpx.Response:
    if (
        request.url.path
        == "/centre-hospitalier-regional/lorient-56100/groupe-hospitalier-bretagne-sud-lorient-hopital-du-scorff"
    ):
        return httpx.Response(
            302,
            headers={
                "Location": "https://vaccination-covid.keldoc.com/redirect/?dom=centre-hospitalier-regional&inst=lorient-56100&user=groupe-hospitalier-bretagne-sud-lorient-hopital-du-scorff&specialty=144 "
            },
        )
    for path in CENTER1_KELDOC:
        if request.url.path == path:
            return httpx.Response(200, json=get_test_data(CENTER1_KELDOC[path]))
    return httpx.Response(200, json={})


def test_keldoc_parse_center():
    center1_url = (
        "https://vaccination-covid.keldoc.com/centre-hospitalier-regional/lorient-56100/groupe-hospitalier"
        "-bretagne-sud-lorient-hopital-du-scorff?specialty=144 "
    )

    center1_data = json.loads(Path("tests", "fixtures", "keldoc", "center1-info.json").read_text())

    request = ScraperRequest(center1_url, "2020-04-04")
    client = httpx.Client(transport=httpx.MockTransport(app_center1))
    test_center_1 = KeldocCenter(request, client=client)
    assert test_center_1.parse_resource()

    # Check if parameters are parsed correctly
    assert test_center_1.resource_params
    res = test_center_1.resource_params
    assert res["type"] == "centre-hospitalier-regional"
    assert res["location"] == "lorient-56100"
    assert res["slug"] == "groupe-hospitalier-bretagne-sud-lorient-hopital-du-scorff"

    # Fetch center data (id/center specialties)
    assert test_center_1.fetch_center_data()
    assert test_center_1.id == center1_data["id"]
    assert test_center_1.specialties == center1_data["specialties"]

    # Filter center specialties
    filtered_specialties = get_relevant_vaccine_specialties_id(test_center_1.specialties)
    assert filtered_specialties == [144]

    # Fetch vaccine cabinets
    assert not test_center_1.fetch_vaccine_cabinets()
    test_center_1.vaccine_specialties = filtered_specialties
    cabinets = test_center_1.fetch_vaccine_cabinets()
    assert cabinets == [18780, 16913, 16910, 16571, 16579]

    # Fetch motives
    motives = filter_vaccine_motives(
        client,
        test_center_1.selected_cabinet,
        test_center_1.id,
        test_center_1.vaccine_specialties,
        test_center_1.vaccine_cabinets,
    )
    assert motives == json.loads(Path("tests", "fixtures", "keldoc", "center1-motives.json").read_text())

    # Find first availability date
    fake_now = dt.datetime(2020, 4, 4, 8, 15)
    with mock_datetime_now(fake_now):
        date, count, appointment_schedules = test_center_1.find_first_availability("2020-04-04")
    assert not date
    test_center_1.vaccine_motives = motives
    with mock_datetime_now(fake_now):
        date, count, appointment_schedules = test_center_1.find_first_availability("2020-04-04")
    tz = datetime.timezone(datetime.timedelta(seconds=7200))
    assert date == datetime.datetime(2021, 4, 20, 16, 55, tzinfo=tz)
    assert appointment_schedules == [
        {"name": "chronodose", "from": "2020-04-04T08:15:00+02:00", "to": "2020-04-05T08:14:59+02:00", "total": 0},
        {"name": "1_days", "from": "2020-04-04T00:00:00+02:00", "to": "2020-04-04T23:59:59+02:00", "total": 0},
        {"name": "2_days", "from": "2020-04-04T00:00:00+02:00", "to": "2020-04-05T23:59:59+02:00", "total": 0},
        {"name": "7_days", "from": "2020-04-04T00:00:00+02:00", "to": "2020-04-10T23:59:59+02:00", "total": 0},
        {"name": "28_days", "from": "2020-04-04T00:00:00+02:00", "to": "2020-05-01T23:59:59+02:00", "total": 0},
        {"name": "49_days", "from": "2020-04-04T00:00:00+02:00", "to": "2020-05-22T23:59:59+02:00", "total": 0},
    ]


def test_keldoc_missing_params():
    center1_url = "https://vaccination-covid.keldoc.com/centre-hospitalier-regional/foo/bar?specialty=no"
    center1_redirect = "https://vaccination-covid.keldoc.com/redirect/?dom=foo&user=ok&specialty=no"

    def app(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/centre-hospitalier-regional/foo/bar?specialty=no":
            return httpx.Response(302, headers={"Location": center1_redirect})

        return httpx.Response(200, json={})

    client = httpx.Client(transport=httpx.MockTransport(app))
    request = ScraperRequest(center1_url, "2020-04-04")
    test_center_1 = KeldocCenter(request, client=client)
    assert not test_center_1.parse_resource()


def test_keldoc_timeout():
    center1_url = "https://vaccination-covid.keldoc.com/centre-hospitalier-regional/foo/bar?specialty=no"

    def app(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/centre-hospitalier-regional/foo/bar":
            raise TimeoutError
        if request.url.path == "/api/patients/v2/searches/resource":
            raise TimeoutError
        if request.url.path == "/api/patients/v2/clinics/1/specialties/1/cabinets":
            raise TimeoutError
        return httpx.Response(200, json={})

    client = httpx.Client(transport=httpx.MockTransport(app))
    request = ScraperRequest(center1_url, "2020-04-04")
    test_center_1 = KeldocCenter(request, client=client)

    # Test center info TA
    with pytest.raises(TimeoutError):
        test_center_1.parse_resource()
    with pytest.raises(TimeoutError):
        test_center_1.fetch_center_data()

    # Test cabinet TA
    test_center_1.id = 1
    test_center_1.vaccine_specialties = [1]
    with pytest.raises(TimeoutError):
        test_center_1.fetch_vaccine_cabinets()
    assert not test_center_1.vaccine_cabinets


def test_keldoc_filters():
    # Test appointments
    assert is_appointment_relevant("Vaccin 1ère inj. +70 ans COVID")
    assert is_appointment_relevant("1ère dose (Pfizer)")
    assert is_appointment_relevant("Première injection de vaccin (Moderna)")
    assert not is_appointment_relevant("Vaccin 2nde inj. +70 ans COVID")
    assert not is_appointment_relevant(None)

    # Test specialties
    assert not is_specialty_relevant(None)
    assert not is_specialty_relevant({"name": "Maladies infectieuses"})
    assert not is_specialty_relevant({"id": 144})
    assert is_specialty_relevant({"id": 1, "name": "Maladies infectieuses", "skills": []})
    assert is_specialty_relevant(
        {"id": 1, "name": "Vaccination contre la COVID", "skills": [{"name": "Centre de vaccination COVID-19"}]}
    )
    assert not is_specialty_relevant({"id": 1, "name": "Vaccination contre la COVID", "skills": [{"id": 123}]})


def test_keldoc_scrape():
    center1_url = "https://www.keldoc.com/centre-hospitalier-regional/lorient-56100/groupe-hospitalier-bretagne-sud-lorient-hopital-du-scorff?specialty=144"
    request = ScraperRequest(center1_url, "2020-04-04")
    keldoc.session = httpx.Client(transport=httpx.MockTransport(app_center1))

    date = fetch_slots(request)
    # When it's already killed
    if not keldoc.KELDOC_ENABLED:
        assert date is None
    else:
        assert date == "2021-04-20T16:55:00.000000+0200"
    keldoc.KELDOC_ENABLED = False
    test_killswitch = fetch_slots(request)
    assert not test_killswitch


def test_keldoc_scrape_nodate():
    center1_url = (
        "https://www.keldoc.com/centre-hospitalier-regional/lorient-56100/groupe-hospitalier"
        "-bretagne-sud-lorient-hopital-du-scorff?specialty=144 "
    )

    keldoc.KELDOC_ENABLED = True

    def app_center2(request: httpx.Request) -> httpx.Response:
        if "timetables/" in request.url.path:
            return httpx.Response(200, json={})
        if (
            request.url.path
            == "/centre-hospitalier-regional/lorient-56100/groupe-hospitalier-bretagne-sud-lorient-hopital-du-scorff"
        ):
            return httpx.Response(
                302,
                headers={
                    "Location": "https://vaccination-covid.keldoc.com/redirect/?dom=centre-hospitalier-regional&inst=lorient-56100&user=groupe-hospitalier-bretagne-sud-lorient-hopital-du-scorff&specialty=144 "
                },
            )
        for path in CENTER1_KELDOC:
            if request.url.path == path:
                return httpx.Response(200, json=get_test_data(CENTER1_KELDOC[path]))
        return httpx.Response(200, json={})

    request = ScraperRequest(center1_url, "2099-12-12")
    keldoc.session = httpx.Client(transport=httpx.MockTransport(app_center2))

    date = fetch_slots(request)
    assert not date


def test_keldoc_parse_simple():
    appointments = []
    data = {"date": "2021-04-20T16:55:00.000000+0200"}
    availability, new_count = parse_keldoc_availability(data, appointments)
    assert availability.isoformat() == "2021-04-20T16:55:00+02:00"


def test_keldoc_parse_complex():
    appointments = []
    data = {
        "availabilities": {
            "2021-04-20": [
                {"start_time": "2021-04-20T16:53:00.000000+0200"},
                {"start_time": "2021-04-20T16:50:00.000000+0200"},
                {"start_time": "2021-04-20T18:59:59.000000+0200"},
            ],
            "2021-04-21": [{"start_time": "2021-04-21T08:12:12.000000+0200"}],
        }
    }
    availability, new_count = parse_keldoc_availability(data, appointments)
    assert availability.isoformat() == "2021-04-20T16:50:00+02:00"


def test_keldoc_parse_complex():
    appointments = []
    data = {
        "availabilities": {
            "2021-04-15": [],
            "2021-04-16": [],
            "2021-04-17": [],
            "2021-04-18": [],
            "2021-04-19": [{"agenda_id": None}],
            "2021-04-20": [
                {"start_time": "2021-04-20T16:53:00.000000+0200"},
                {"start_time": "2021-04-20T16:50:00.000000+0200"},
                {"start_time": "2021-04-20T18:59:59.000000+0200"},
            ],
            "2021-04-21": [{"start_time": "2021-04-21T08:12:12.000000+0200"}],
        }
    }
    availability, new_count = parse_keldoc_availability(data, appointments)
    assert availability.isoformat() == "2021-04-20T16:50:00+02:00"


def test_null_motives():
    client = DEFAULT_CLIENT
    motives = filter_vaccine_motives(client, 4233, 1, None, None)
    assert not motives
