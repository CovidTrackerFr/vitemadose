from scraper.doctolib.doctolib_center_scrap import (
    get_departements,
    doctolib_urlify,
    get_coordinates,
    center_type,
    parse_doctolib_business_hours,
    parse_place,
    parse_center_places,
    parse_doctor,
)

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


EXPECTED_PARSED_PAGES = [
    {
        "gid": "d1",
        "place_id": "practice-37157",
        "address": "41 Avenue du Maréchal Juin, 93260 Les Lilas",
        "ville": "Les Lilas",
        "long_coor1": 2.42283520000001,
        "lat_coor1": 48.8788792,
        "com_insee": "93045",
        "booking": {
            "profile": {"id": 1, "name_with_title": "Hopital test"},
            "visit_motives": [
                {"name": "Consultation de suivi spécialiste"},
                {"name": "Première consultation de neurochirurgie"},
            ],
            "places": [
                {
                    "id": "practice-37157",
                    "latitude": 48.8788792,
                    "longitude": 2.42283520000001,
                    "phone_number": "06 00 00 00 00",
                    "full_address": "41 Avenue du Maréchal Juin, 93260 Les Lilas",
                    "city": "Les Lilas",
                    "zipcode": "93260",
                    "opening_hours": [
                        {"day": 1, "ranges": [["09:00", "13:00"]], "enabled": False},
                        {"day": 2, "ranges": [["09:00", "13:00"]], "enabled": False},
                        {"day": 3, "ranges": [["09:00", "13:00"]], "enabled": False},
                        {"day": 4, "ranges": [["09:00", "13:00"]], "enabled": False},
                        {"day": 5, "ranges": [["09:00", "13:00"]], "enabled": False},
                        {"day": 6, "ranges": [["09:00", "13:00"]], "enabled": False},
                        {"day": 0, "ranges": [["09:00", "13:00"]], "enabled": False},
                    ],
                    "name": "Clinique des Lilas ",
                },
                {
                    "id": "practice-86656",
                    "latitude": 48.8814861,
                    "longitude": 2.27230770000006,
                    "landline_number": "06 38 95 25 53",
                    "full_address": "11 Rue d'Orléans, 92200 Neuilly-sur-Seine",
                    "city": "Neuilly-sur-Seine",
                    "zipcode": "92200",
                    "opening_hours": [
                        {"day": 1, "ranges": [["09:00", "13:00"]], "enabled": False},
                        {"day": 2, "ranges": [["09:00", "13:00"]], "enabled": False},
                        {"day": 3, "ranges": [["09:00", "13:00"]], "enabled": False},
                        {"day": 4, "ranges": [["09:00", "13:00"]], "enabled": False},
                        {"day": 5, "ranges": [["09:00", "13:00"]], "enabled": False},
                        {"day": 6, "ranges": [["09:00", "13:00"]], "enabled": False},
                        {"day": 0, "ranges": [["09:00", "13:00"]], "enabled": False},
                    ],
                    "name": "Cabinet Neuilly",
                },
            ],
            "doctors": [
                {
                    "address": "22b Rue Jean Jaurès",
                    "city": "Villejuif",
                    "zipcode": "94800",
                    "link": "/pharmacie/villejuif/pharmacie-des-ecoles",
                    "name_with_title": "Pharmacie des écoles - Leadersanté - Villejuif",
                    "position": {"lat": 48.7951181, "lng": 2.3662778},
                    "place_id": None,
                    "exact_match": True,
                },
                {
                    "address": "96 Avenue Jean Jaurès",
                    "city": "Le Petit-Quevilly",
                    "zipcode": "76140",
                    "link": "/vaccinodrome/le-petit-quevilly/dubois",
                    "name_with_title": "Vaccinodrome Jean Jaurès",
                    "position": {"lat": 49.4269181, "lng": 1.0627287},
                    "place_id": 1,
                    "exact_match": True,
                },
            ],
        },
        "visit_motives": ["Consultation de suivi spécialiste", "Première consultation de neurochirurgie"],
        "phone_number": "+33600000000",
        "business_hours": {
            "lundi": None,
            "mardi": None,
            "mercredi": None,
            "jeudi": None,
            "vendredi": None,
            "samedi": None,
            "dimanche": None,
        },
    },
    {
        "gid": "d1",
        "place_id": "practice-86656",
        "address": "11 Rue d'Orléans, 92200 Neuilly-sur-Seine",
        "ville": "Neuilly-sur-Seine",
        "long_coor1": 2.27230770000006,
        "lat_coor1": 48.8814861,
        "com_insee": "92051",
        "booking": {
            "profile": {"id": 1, "name_with_title": "Hopital test"},
            "visit_motives": [
                {"name": "Consultation de suivi spécialiste"},
                {"name": "Première consultation de neurochirurgie"},
            ],
            "places": [
                {
                    "id": "practice-37157",
                    "latitude": 48.8788792,
                    "longitude": 2.42283520000001,
                    "phone_number": "06 00 00 00 00",
                    "full_address": "41 Avenue du Maréchal Juin, 93260 Les Lilas",
                    "city": "Les Lilas",
                    "zipcode": "93260",
                    "opening_hours": [
                        {"day": 1, "ranges": [["09:00", "13:00"]], "enabled": False},
                        {"day": 2, "ranges": [["09:00", "13:00"]], "enabled": False},
                        {"day": 3, "ranges": [["09:00", "13:00"]], "enabled": False},
                        {"day": 4, "ranges": [["09:00", "13:00"]], "enabled": False},
                        {"day": 5, "ranges": [["09:00", "13:00"]], "enabled": False},
                        {"day": 6, "ranges": [["09:00", "13:00"]], "enabled": False},
                        {"day": 0, "ranges": [["09:00", "13:00"]], "enabled": False},
                    ],
                    "name": "Clinique des Lilas ",
                },
                {
                    "id": "practice-86656",
                    "latitude": 48.8814861,
                    "longitude": 2.27230770000006,
                    "landline_number": "06 38 95 25 53",
                    "full_address": "11 Rue d'Orléans, 92200 Neuilly-sur-Seine",
                    "city": "Neuilly-sur-Seine",
                    "zipcode": "92200",
                    "opening_hours": [
                        {"day": 1, "ranges": [["09:00", "13:00"]], "enabled": False},
                        {"day": 2, "ranges": [["09:00", "13:00"]], "enabled": False},
                        {"day": 3, "ranges": [["09:00", "13:00"]], "enabled": False},
                        {"day": 4, "ranges": [["09:00", "13:00"]], "enabled": False},
                        {"day": 5, "ranges": [["09:00", "13:00"]], "enabled": False},
                        {"day": 6, "ranges": [["09:00", "13:00"]], "enabled": False},
                        {"day": 0, "ranges": [["09:00", "13:00"]], "enabled": False},
                    ],
                    "name": "Cabinet Neuilly",
                },
            ],
            "doctors": [
                {
                    "address": "22b Rue Jean Jaurès",
                    "city": "Villejuif",
                    "zipcode": "94800",
                    "link": "/pharmacie/villejuif/pharmacie-des-ecoles",
                    "name_with_title": "Pharmacie des écoles - Leadersanté - Villejuif",
                    "position": {"lat": 48.7951181, "lng": 2.3662778},
                    "place_id": None,
                    "exact_match": True,
                },
                {
                    "address": "96 Avenue Jean Jaurès",
                    "city": "Le Petit-Quevilly",
                    "zipcode": "76140",
                    "link": "/vaccinodrome/le-petit-quevilly/dubois",
                    "name_with_title": "Vaccinodrome Jean Jaurès",
                    "position": {"lat": 49.4269181, "lng": 1.0627287},
                    "place_id": 1,
                    "exact_match": True,
                },
            ],
        },
        "visit_motives": ["Consultation de suivi spécialiste", "Première consultation de neurochirurgie"],
        "phone_number": "+33638952553",
        "business_hours": {
            "lundi": None,
            "mardi": None,
            "mercredi": None,
            "jeudi": None,
            "vendredi": None,
            "samedi": None,
            "dimanche": None,
        },
    },
]


def test_parse_places():
    with open("tests/fixtures/doctolib/booking-with-doctors.json", "r", encoding='utf8') as f:
        booking = json.load(f)
        assert parse_center_places(booking["data"]) == EXPECTED_PARSED_PAGES


def test_parse_place():
    test_place = {
        "id": "practice-166932",
        "zipcode": "97150",
        "city": "97150",
        "latitude": 18.0665433,
        "longitude": -63.0754092,
        "landline_number": "05 90 52 27 22",
        "full_address": "Rue Jean-Luc Hamlet Marigot, 97150 97150",
        "opening_hours": [{"day": 1, "ranges": [["09:00", "12:00"], ["14:00", "17:00"]], "enabled": True}],
    }

    expected_result = {
        "place_id": "practice-166932",
        "address": "Rue Jean-Luc Hamlet Marigot, 97150 97150",
        "ville": "97150",
        "long_coor1": -63.0754092,
        "lat_coor1": 18.0665433,
        "com_insee": "97801",
        "phone_number": "+33590522722",
        "business_hours": {"lundi": "09:00-12:00, 14:00-17:00"},
    }

    assert parse_place(test_place) == expected_result
    # test it still works if landline is replaced by phone
    test_place["phone_number"] = test_place["landline_number"]
    del test_place["landline_number"]
    assert parse_place(test_place) == expected_result


def test_parse_doctor():
    test_doctor = EXPECTED_PARSED_PAGES[0]["booking"]["doctors"][0]
    expected_result = {
        "nom": "Pharmacie des écoles - Leadersanté - Villejuif",
        "ville": "Villejuif",
        "address": "22b Rue Jean Jaurès, 94800 Villejuif",
        "long_coor1": 2.3662778,
        "lat_coor1": 48.7951181,
        "type": "drugstore",
        "com_insee": "94076",
    }
    assert parse_doctor(test_doctor) == expected_result


from unittest.mock import patch


@patch("requests.get")
def test_get_dict_infos_center_page(mock_get):
    with open("tests/fixtures/doctolib/booking-with-doctors.json", "r") as file:
        json.load(file)

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


#    mock_get.return_value.json.return_value = booking
#    mockedResponse = get_dict_infos_center_page("someURL?pid=practice-86656")
#    assert mockedResponse == expectedInfosCenterPageWithLandlineNumber

#    booking_requests.clear()
#    mock_get.return_value.json.return_value = {"data": {}}
#    mockedResponse = get_dict_infos_center_page("someURL")
#    assert mockedResponse == []


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
            "booking": {
                "profile": {"id": 1, "name_with_title": "Hopital test"},
                "visit_motives": [
                    {"name": "Consultation de suivi spécialiste"},
                    {"name": "Première consultation de neurochirurgie"},
                ],
            },
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
            "booking": {
                "profile": {"id": 1, "name_with_title": "Hopital test"},
                "visit_motives": [
                    {"name": "Consultation de suivi spécialiste"},
                    {"name": "Première consultation de neurochirurgie"},
                ],
            },
        },
    ]

    mock_get.return_value.json.return_value = doctors


#
#    mockedResponse, stop = parse_page_centers_departement("", 1, [])
#    with open('tests/fixtures/doctolib/booking-with-doctors.json', 'w') as f:
#        f.write(json.dumps(mockedResponse, indent=2))
#    assert mockedResponse == expectedCentersPage

#    mockedResponse = parse_pages_departement("indre")
#    assert mockedResponse == expectedCentersPage
