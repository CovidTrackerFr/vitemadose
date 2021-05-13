from scraper.doctolib.doctolib_center_scrap import (
    get_departements,
    doctolib_urlify,
    get_coordinates,
    center_type,
    parse_doctolib_business_hours,
    get_dict_infos_center_page,
    parse_page_centers,
    parse_page_centers_departement,
    parse_pages_departement,
    parse_doctolib_centers, booking_requests,
)

import requests
import json

# -- Tests de l'API (offline) --
from scraper.pattern.scraper_result import GENERAL_PRACTITIONER, DRUG_STORE, VACCINATION_CENTER


def test_doctolib_departements():
    dep = get_departements()
    assert len(dep) == 100


def test_doctolib_urlify():
    url = "FooBar 42"
    assert doctolib_urlify(url) == "foobar-42"


def test_center_type():
    type = center_type("https://doctolib.fr/center/foobar-42", "Pharmacie du centre de Saint-Malo")
    assert type == DRUG_STORE
    type = center_type("https://doctolib.fr/medecin/foobar-42", "Dr Foo Bar")
    assert type == GENERAL_PRACTITIONER
    type = center_type("https://doctolib.fr/centres-vaccination/foobar-42", "Centre Foo Bar")
    assert type == VACCINATION_CENTER


def test_business_hours():
    place = {
        "opening_hours": [
            {
                "day": 1,
                "enabled": True,
                "ranges": [
                    ["12:00", "15:00"],
                    ["16:00", "17:00"],
                ],
            },
            {
                "day": 2,
                "enabled": False,
            },
        ]
    }
    emptyPlace = {"opening_hours": []}
    assert parse_doctolib_business_hours(place) == {"lundi": "12:00-15:00, 16:00-17:00", "mardi": None}
    assert parse_doctolib_business_hours(emptyPlace) == None


def test_doctolib_coordinates():
    docto = {"position": {"lng": 1.381, "lat": 8.192}}
    long, lat = get_coordinates(docto)
    assert long == 1.381
    assert lat == 8.192


from unittest.mock import Mock, patch


@patch("requests.get")
def test_get_dict_infos_center_page(mock_get):
    with open("tests/fixtures/doctolib/booking-with-doctors.json", "r") as file:
        booking = json.load(file)

    expectedInfosCenterPageWithLandlineNumber = [
        {
            "gid": "d1",
            "address": "41 Avenue du Maréchal Juin, 93260 Les Lilas",
            "long_coor1": 2.42283520000001,
            "lat_coor1": 48.8788792,
            "com_insee": "93045",
            "phone_number": "+33600000000",
            "place_id": "practice-37157",
            "business_hours": {
                "lundi": None,
                "mardi": None,
                "mercredi": None,
                "jeudi": None,
                "vendredi": None,
                "samedi": None,
                "dimanche": None,
            },
            "visit_motives": ["Consultation de suivi spécialiste", "Première consultation de neurochirurgie"],
        },
        {
            "gid": "d1",
            "address": "11 Rue d'Orléans, 92200 Neuilly-sur-Seine",
            "long_coor1": 2.27230770000006,
            "lat_coor1": 48.8814861,
            "com_insee": "92051",
            "phone_number": "+33638952553",
            "place_id": "practice-86656",
            "business_hours": {
                "lundi": None,
                "mardi": None,
                "mercredi": None,
                "jeudi": None,
                "vendredi": None,
                "samedi": None,
                "dimanche": None,
            },
            "visit_motives": ["Consultation de suivi spécialiste", "Première consultation de neurochirurgie"],
        },
    ]
    mock_get.return_value.json.return_value = booking
    mockedResponse = get_dict_infos_center_page("someURL?pid=practice-86656")
    assert mockedResponse == expectedInfosCenterPageWithLandlineNumber

    booking_requests.clear()
    mock_get.return_value.json.return_value = {"data": {}}
    mockedResponse = get_dict_infos_center_page("someURL")
    assert mockedResponse == []


@patch("requests.get")
def test_centers_parsing(mock_get):
    with open("tests/fixtures/doctolib/booking-with-doctors.json", "r") as file:
        doctors = json.load(file)

    expectedCentersPage = [
        {
            "address": "22b Rue Jean Jaurès, 94800 Villejuif",
            "business_hours": {
                "dimanche": None,
                "jeudi": None,
                "lundi": None,
                "mardi": None,
                "mercredi": None,
                "samedi": None,
                "vendredi": None,
            },
            "com_insee": "94076",
            "gid": "d1",
            "lat_coor1": 48.7951181,
            "long_coor1": 2.3662778,
            "nom": "Pharmacie des écoles - Leadersanté - Villejuif",
            "phone_number": "+33600000000",
            "place_id": "practice-37157",
            "rdv_site_web": "https://www.doctolib.fr/pharmacie/villejuif/pharmacie-des-ecoles?pid=practice-37157",
            "type": "drugstore",
            "ville": "Villejuif",
            "visit_motives": ["Consultation de suivi spécialiste", "Première consultation de neurochirurgie"],
        },
        {
            "address": "22b Rue Jean Jaurès, 94800 Villejuif",
            "business_hours": {
                "dimanche": None,
                "jeudi": None,
                "lundi": None,
                "mardi": None,
                "mercredi": None,
                "samedi": None,
                "vendredi": None,
            },
            "com_insee": "94076",
            "gid": "d1",
            "lat_coor1": 48.7951181,
            "long_coor1": 2.3662778,
            "nom": "Pharmacie des écoles - Leadersanté - Villejuif",
            "phone_number": "+33638952553",
            "place_id": "practice-86656",
            "rdv_site_web": "https://www.doctolib.fr/pharmacie/villejuif/pharmacie-des-ecoles?pid=practice-86656",
            "type": "drugstore",
            "ville": "Villejuif",
            "visit_motives": ["Consultation de suivi spécialiste", "Première consultation de neurochirurgie"],
        },
        {
            "address": "96 Avenue Jean Jaurès, 76140 Le Petit-Quevilly",
            "business_hours": {
                "dimanche": None,
                "jeudi": None,
                "lundi": None,
                "mardi": None,
                "mercredi": None,
                "samedi": None,
                "vendredi": None,
            },
            "com_insee": "76498",
            "gid": "d1",
            "lat_coor1": 49.4269181,
            "long_coor1": 1.0627287,
            "nom": "Vaccinodrome Jean Jaurès",
            "phone_number": "+33600000000",
            "place_id": "practice-37157",
            "rdv_site_web": "https://www.doctolib.fr/vaccinodrome/le-petit-quevilly/dubois?pid=practice-37157",
            "type": "vaccination-center",
            "ville": "Le Petit-Quevilly",
            "visit_motives": ["Consultation de suivi spécialiste", "Première consultation de neurochirurgie"],
        },
        {
            "address": "96 Avenue Jean Jaurès, 76140 Le Petit-Quevilly",
            "business_hours": {
                "dimanche": None,
                "jeudi": None,
                "lundi": None,
                "mardi": None,
                "mercredi": None,
                "samedi": None,
                "vendredi": None,
            },
            "com_insee": "76498",
            "gid": "d1",
            "lat_coor1": 49.4269181,
            "long_coor1": 1.0627287,
            "nom": "Vaccinodrome Jean Jaurès",
            "phone_number": "+33638952553",
            "place_id": "practice-86656",
            "rdv_site_web": "https://www.doctolib.fr/vaccinodrome/le-petit-quevilly/dubois?pid=practice-86656",
            "type": "vaccination-center",
            "ville": "Le Petit-Quevilly",
            "visit_motives": ["Consultation de suivi spécialiste", "Première consultation de neurochirurgie"],
        },
    ]

    mock_get.return_value.json.return_value = doctors

    mockedResponse = parse_page_centers(0)
    assert mockedResponse == expectedCentersPage

    mockedResponse = parse_page_centers_departement("", 1, [])
    assert mockedResponse == expectedCentersPage

    mockedResponse = parse_pages_departement("indre")
    assert mockedResponse == expectedCentersPage
