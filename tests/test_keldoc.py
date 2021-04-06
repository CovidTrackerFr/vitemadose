# -- Tests de l'API (offline) --
import datetime
import json
from pathlib import Path

import httpx

from scraper.keldoc.keldoc_center import KeldocCenter
from scraper.keldoc.keldoc_filters import filter_vaccine_specialties, filter_vaccine_motives

CENTER1_KELDOC = {
    "/api/patients/v2/clinics/2563/specialties/144/cabinets": "center1-cabinet",
    "/api/patients/v2/clinics/2563/specialties/144/cabinets/18780/motive_categories": "center1-cabinet-18780",
    "/api/patients/v2/clinics/2563/specialties/144/cabinets/16910/motive_categories": "center1-cabinet-16910",
    "/api/patients/v2/clinics/2563/specialties/144/cabinets/16913/motive_categories": "center1-cabinet-16913",
    "/api/patients/v2/timetables/81484": "center1-timetable-81484",
    "/api/patients/v2/timetables/81486": "center1-timetable-81486",
    "/api/patients/v2/timetables/81466": "center1-timetable-81466",
    "/api/patients/v2/timetables/82874": "center1-timetable-82874",
    "/api/patients/v2/searches/resource": "center1-info"
}


def get_test_data(file_name):
    path = Path("tests", "fixtures", "keldoc", f"{file_name}.json")
    return json.loads(path.read_text())


def app_center1(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/centre-hospitalier-regional/lorient-56100/groupe-hospitalier-bretagne-sud-lorient-hopital-du-scorff":
        return httpx.Response(302, headers={
            "Location": "https://vaccination-covid.keldoc.com/redirect/?dom=centre-hospitalier-regional&inst=lorient-56100&user=groupe-hospitalier-bretagne-sud-lorient-hopital-du-scorff&specialty=144 "})
    for path in CENTER1_KELDOC:
        if request.url.path == path:
            return httpx.Response(200, json=get_test_data(CENTER1_KELDOC[path]))
    return httpx.Response(200, json={})


def test_keldoc_parse_center():
    center1_url = "https://vaccination-covid.keldoc.com/centre-hospitalier-regional/lorient-56100/groupe-hospitalier" \
                  "-bretagne-sud-lorient-hopital-du-scorff?specialty=144 "

    center1_data = json.loads(Path("tests", "fixtures", "keldoc", "center1-info.json").read_text())

    client = httpx.Client(transport=httpx.MockTransport(app_center1))
    test_center_1 = KeldocCenter(base_url=center1_url, client=client)
    assert test_center_1.parse_resource()

    # Check if parameters are parsed correctly
    assert test_center_1.resource_params
    res = test_center_1.resource_params
    assert res['type'] == 'centre-hospitalier-regional'
    assert res['location'] == 'lorient-56100'
    assert res['slug'] == 'groupe-hospitalier-bretagne-sud-lorient-hopital-du-scorff'

    # Fetch center data (id/center specialties)
    assert test_center_1.fetch_center_data()
    assert test_center_1.id == center1_data['id']
    assert test_center_1.specialties == center1_data['specialties']

    # Filter center specialties
    filtered_specialties = filter_vaccine_specialties(test_center_1.specialties)
    assert filtered_specialties == [144]

    # Fetch vaccine cabinets
    assert not test_center_1.fetch_vaccine_cabinets()
    test_center_1.vaccine_specialties = filtered_specialties
    cabinets = test_center_1.fetch_vaccine_cabinets()
    assert cabinets == [18780, 16913, 16910, 16571, 16579]

    # Fetch motives
    motives = filter_vaccine_motives(client, test_center_1.selected_cabinet, test_center_1.id,
                                     test_center_1.vaccine_specialties, test_center_1.vaccine_cabinets)
    assert motives == json.loads(Path("tests", "fixtures", "keldoc", "center1-motives.json").read_text())

    # Find first availability date
    date = test_center_1.find_first_availability("2020-04-04", "2020-04-05")
    assert not date
    test_center_1.vaccine_motives = motives
    date = test_center_1.find_first_availability("2020-04-04", "2020-04-05")
    tz = datetime.timezone(datetime.timedelta(seconds=7200))
    assert date == datetime.datetime(2021, 4, 20, 16, 55, tzinfo=tz)


def test_keldoc_missing_params():
    center1_url = "https://vaccination-covid.keldoc.com/centre-hospitalier-regional/foo/bar?specialty=no"
    center1_redirect = "https://vaccination-covid.keldoc.com/redirect/?dom=foo&user=ok&specialty=no"

    def app(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/centre-hospitalier-regional/foo/bar?specialty=no":
            return httpx.Response(302, headers={
                "Location": center1_redirect
            })

        return httpx.Response(200, json={})

    client = httpx.Client(transport=httpx.MockTransport(app))
    test_center_1 = KeldocCenter(base_url=center1_url, client=client)
    assert not test_center_1.parse_resource()
