import copy
import json
from pathlib import Path

import pytest

from scraper.doctolib.doctolib_filters import (
    is_category_relevant,
    is_vaccination_center,
    is_appointment_relevant,
    parse_practitioner_type,
)
from scraper.error import BlockedByDoctolibError
from scraper.pattern.vaccine import Vaccine

import httpx
from scraper.doctolib.doctolib import (
    DoctolibSlots,
    _find_agenda_and_practice_ids,
    _find_visit_motive_category_id,
    _find_visit_motive_id,
    _parse_centre,
    _parse_practice_id,
    set_doctolib_center_internal_id,
    DOCTOLIB_CONF,
)


# -- Tests de l'API (offline) --
from scraper.pattern.scraper_request import ScraperRequest
from scraper.pattern.scraper_result import DRUG_STORE, GENERAL_PRACTITIONER


def test_blocked_by_doctolib_par_centre():
    # Cas de base.

    start_date = "2021-04-03"
    base_url = "https://partners.doctolib.fr/centre-de-vaccinations-internationales/ville1/centre1?pid=practice-165752&enable_cookies_consent=1"  # noqa
    scrap_request = ScraperRequest(base_url, start_date)

    def app(request: httpx.Request) -> httpx.Response:
        assert "User-Agent" in request.headers

        if request.url.path == "/booking/centre1.json":
            path = Path("tests", "fixtures", "doctolib", "basic-booking.json")
            return httpx.Response(403, text="Anti dDos")

        assert request.url.path == "/availabilities.json"
        params = dict(httpx.QueryParams(request.url.query))
        assert params == {
            "start_date": start_date,
            "visit_motive_ids": "2",
            "agenda_ids": "3",
            "insurance_sector": "public",
            "practice_ids": "4",
            "destroy_temporary": "true",
            "limit": str(DOCTOLIB_CONF.pagination["pages"]),
        }
        path = Path("tests", "fixtures", "doctolib", "basic-availabilities.json")
        return httpx.Response(200, json=json.loads(path.read_text(encoding="utf-8")))

    client = httpx.Client(transport=httpx.MockTransport(app))
    slots = DoctolibSlots(client=client, cooldown_interval=0)

    with pytest.raises(BlockedByDoctolibError):
        slots.fetch(scrap_request)


def test_blocked_by_doctolib_par_availabilities():
    # Cas de base.

    start_date = "2021-04-03"
    base_url = "https://partners.doctolib.fr/centre-de-vaccinations-internationales/ville1/centre1?pid=practice-165752&enable_cookies_consent=1"  # noqa
    scrap_request = ScraperRequest(base_url, start_date)

    def app(request: httpx.Request) -> httpx.Response:
        assert "User-Agent" in request.headers

        if request.url.path == "/booking/centre1.json":
            path = Path("tests", "fixtures", "doctolib", "basic-booking.json")
            return httpx.Response(200, json=json.loads(path.read_text(encoding="utf-8")))

        return httpx.Response(403, text="Anti dDos")

    client = httpx.Client(transport=httpx.MockTransport(app))
    slots = DoctolibSlots(client=client, cooldown_interval=0)

    with pytest.raises(BlockedByDoctolibError):
        slots.fetch(scrap_request)


def test_doctolib():
    # Cas de base.

    start_date = "2021-04-03"
    base_url = "https://partners.doctolib.fr/centre-de-vaccinations-internationales/ville1/centre1?pid=practice-165752&enable_cookies_consent=1"  # noqa
    scrap_request = ScraperRequest(base_url, start_date)

    def app(request: httpx.Request) -> httpx.Response:
        assert "User-Agent" in request.headers

        if request.url.path == "/booking/centre1.json":
            path = Path("tests", "fixtures", "doctolib", "basic-booking.json")
            return httpx.Response(200, json=json.loads(path.read_text(encoding="utf-8")))

        assert request.url.path == "/availabilities.json"
        path = Path("tests", "fixtures", "doctolib", "basic-availabilities.json")
        return httpx.Response(200, json=json.loads(path.read_text(encoding="utf-8")))

    client = httpx.Client(transport=httpx.MockTransport(app))
    slots = DoctolibSlots(client=client, cooldown_interval=0)

    next_date = slots.fetch(scrap_request)
    assert next_date == "2021-04-10"


def test_doctolib_motive_categories():
    # Certains centres opèrent une distinction de motifs pour les professionnels de santé /
    # non professionnels de santé.
    # On doit gérer ces cas-là.

    start_date = "2021-04-03"
    base_url = "https://partners.doctolib.fr/centre-de-vaccinations-internationales/ville1/centre1?pid=practice-165752&enable_cookies_consent=1"  # noqa
    scrap_request = ScraperRequest(base_url, start_date)

    def app(request: httpx.Request) -> httpx.Response:
        assert "User-Agent" in request.headers

        if request.url.path == "/booking/centre1.json":
            path = Path("tests", "fixtures", "doctolib", "category-booking.json")
            return httpx.Response(200, json=json.loads(path.read_text(encoding="utf-8")))

        assert request.url.path == "/availabilities.json"
        path = Path("tests", "fixtures", "doctolib", "category-availabilities.json")
        return httpx.Response(200, json=json.loads(path.read_text(encoding="utf-8")))

    client = httpx.Client(transport=httpx.MockTransport(app))
    slots = DoctolibSlots(client=client, cooldown_interval=0)

    next_date = slots.fetch(scrap_request)
    assert next_date == "2021-04-10"


def test_doctolib_next_slot():
    # Cas de repli : c'est surprenant, mais parfois la liste des dispos
    # est vide, mais il y a un champ 'next_slot' qui contient la date de
    # la prochaine visite, que l'on utilise dans ce cas.

    start_date = "2021-04-03"
    base_url = "https://partners.doctolib.fr/centre-de-vaccinations-internationales/ville1/centre1?pid=practice-165752&enable_cookies_consent=1"  # noqa
    scrap_request = ScraperRequest(base_url, start_date)

    def app(request: httpx.Request) -> httpx.Response:
        assert "User-Agent" in request.headers

        if request.url.path == "/booking/centre1.json":
            path = Path("tests", "fixtures", "doctolib", "next-slot-booking.json")
            return httpx.Response(200, json=json.loads(path.read_text(encoding="utf-8")))

        assert request.url.path == "/availabilities.json"
        path = Path("tests", "fixtures", "doctolib", "next-slot-availabilities.json")
        return httpx.Response(200, json=json.loads(path.read_text(encoding="utf-8")))

    client = httpx.Client(transport=httpx.MockTransport(app))
    slots = DoctolibSlots(client=client, cooldown_interval=0)

    next_date = slots.fetch(scrap_request)
    # Next slot should not be used
    assert next_date is None


# -- Tests unitaires --


def test_parse_centre():
    # Nouvelle URL
    url = "https://partners.doctolib.fr/centre-de-vaccinations-internationales/ville1/centre1?pid=practice-165752&enable_cookies_consent=1"  # noqa
    assert _parse_centre(url) == "centre1"

    # Ancienne URL
    url = "https://www.doctolib.fr/centre-de-vaccinations-internationales/ville2/Centre2"  # noqa
    assert _parse_centre(url) == "centre2"

    # URL invalide
    url = "https://partners.doctolib.fr/centre-de-vaccinations-internationales/ville2/"
    assert _parse_centre(url) is None


def test_parse_practice_id():
    # Cas de base
    url = "https://partners.doctolib.fr/centre-de-vaccinations-internationales/ville1/centre1?pid=practice-165752&enable_cookies_consent=1"  # noqa
    assert _parse_practice_id(url) == [165752]

    # Format bizarre 1
    url = "https://partners.doctolib.fr/centre-de-vaccinations-internationales/ville1/centre1?pid=practice-162589&?speciality_id=5494&enable_cookies_consent=1"  # noqa
    assert _parse_practice_id(url) == [162589]

    # Format bizarre 2
    url = "https://partners.doctolib.fr/centre-de-vaccinations-internationales/ville1/centre1?pid=practice-162589?speciality_id=5494&enable_cookies_consent=1"  # noqa
    assert _parse_practice_id(url) == [162589]

    # Broken 1 : manque le numéro
    url = "https://partners.doctolib.fr/centre-de-vaccinations-internationales/ville1/centre1?pid=practice-&enable_cookies_consent=1"  # noqa
    assert _parse_practice_id(url) is None

    # Broken 2 : pid vide
    url = "https://partners.doctolib.fr/centre-de-vaccinations-internationales/ville1/centre1?pid=&enable_cookies_consent=1"  # noqa
    assert _parse_practice_id(url) is None


def test_find_visit_motive_category_id():
    data = {
        "visit_motive_categories": [
            {"id": 41, "name": "Professionnels de santé"},
            {"id": 42, "name": "Non professionnels de santé"},
        ]
    }
    assert _find_visit_motive_category_id(data) == [42]


def test_find_visit_motive_id():
    # Un seul motif dispo
    data = {
        "visit_motives": [
            {
                "id": 1,
                "visit_motive_category_id": 42,
                "name": "1ère injection vaccin COVID-19 (Moderna)",
                "vaccination_motive": True,
                "first_shot_motive": True,
            }
        ]
    }
    assert _find_visit_motive_id(data, visit_motive_category_id=[42]) == {1: Vaccine.MODERNA}

    # Plusieurs motifs dispo
    data = {
        "visit_motives": [
            {
                "id": 1,
                "visit_motive_category_id": 42,
                "name": "1ère injection vaccin COVID-19 (Pfizer/BioNTech)",
                "vaccination_motive": True,
                "first_shot_motive": True,
            },
            {
                "id": 2,
                "name": "1ère injection vaccin COVID-19 (Moderna)",
                "visit_motive_category_id": 42,
                "vaccination_motive": True,
                "first_shot_motive": True,
            },
        ]
    }
    assert _find_visit_motive_id(data, visit_motive_category_id=[42]) == {1: Vaccine.PFIZER, 2: Vaccine.MODERNA}

    # Mix avec un motif autre
    data = {
        "visit_motives": [
            {"id": 1, "visit_motive_category_id": 42, "name": "Autre motif"},
            {
                "id": 2,
                "visit_motive_category_id": 42,
                "name": "1ère injection vaccin COVID-19 (Moderna)",
                "vaccination_motive": True,
                "first_shot_motive": True,
            },
        ]
    }
    assert _find_visit_motive_id(data, visit_motive_category_id=[42]) == {2: Vaccine.MODERNA}

    # Mix avec une catégorie autre
    data = {
        "visit_motives": [
            {
                "id": 1,
                "visit_motive_category_id": 41,
                "name": "1ère injection vaccin COVID-19 (Moderna)",
                "vaccination_motive": True,
                "first_shot_motive": True,
            },
            {
                "id": 2,
                "visit_motive_category_id": 42,
                "name": "1ère injection vaccin COVID-19 (AstraZeneca)",
                "vaccination_motive": True,
                "first_shot_motive": True,
            },
        ]
    }
    assert _find_visit_motive_id(data, visit_motive_category_id=[42]) == {2: Vaccine.ASTRAZENECA}

    # Plusieurs types de vaccin
    data = {
        "visit_motives": [
            {
                "id": 1,
                "visit_motive_category_id": 42,
                "name": "1ère injection vaccin COVID-19 (Moderna)",
                "vaccination_motive": True,
                "first_shot_motive": True,
            },
            {
                "id": 2,
                "visit_motive_category_id": 42,
                "name": "1ère injection vaccin COVID-19 (AstraZeneca)",
                "vaccination_motive": True,
                "first_shot_motive": True,
            },
            {
                "id": 3,
                "visit_motive_category_id": 42,
                "name": "1ère injection vaccin COVID-19 (Pfizer-BioNTech)",
                "vaccination_motive": True,
                "first_shot_motive": True,
            },
            {
                "id": 4,
                "visit_motive_category_id": 42,
                "name": "2nde injection vaccin COVID-19 (Moderna)",
                "vaccination_motive": True,
                "first_shot_motive": False,
            },
            {
                "id": 5,
                "visit_motive_category_id": 42,
                "name": "2nde injection vaccin COVID-19 (AstraZeneca)",
                "vaccination_motive": True,
                "first_shot_motive": False,
            },
            {
                "id": 6,
                "visit_motive_category_id": 42,
                "name": "2nde injection vaccin COVID-19 (Pfizer-BioNTech)",
                "vaccination_motive": True,
                "first_shot_motive": False,
            },
        ]
    }
    assert _find_visit_motive_id(data, visit_motive_category_id=[42]) == {
        1: Vaccine.MODERNA,
        2: Vaccine.ASTRAZENECA,
        3: Vaccine.PFIZER,
    }


def test_find_agenda_and_practice_ids():
    data = {
        "agendas": [
            {
                "id": 10,
                "practice_id": 20,
                "booking_disabled": False,
                "visit_motive_ids_by_practice_id": {
                    "20": [1, 2],
                    "21": [1],
                    "22": [2],  # => Pas inclus
                },
            },
            {
                "id": 11,
                "booking_disabled": True,  # => Pas inclus
                "visit_motive_ids_by_practice_id": {
                    "23": [1, 2],
                },
            },
            {
                "id": 12,
                "practice_id": 21,
                "booking_disabled": False,
                "visit_motive_ids_by_practice_id": {
                    "21": [1, 2],
                    "24": [1],
                },
            },
        ],
    }
    agenda_ids, practice_ids = _find_agenda_and_practice_ids(data, visit_motive_id=1)
    assert agenda_ids == ["10", "12"]
    assert practice_ids == ["20", "21", "24"]

    agenda_ids, practice_ids = _find_agenda_and_practice_ids(data, visit_motive_id=1, practice_id_filter=[21])
    assert agenda_ids == ["12"]
    assert practice_ids == ["21", "24"]


def test_category_relevant():
    assert is_category_relevant("Pfizer")
    assert is_category_relevant("Astra Zeneca")


def test_is_vaccination_center():
    data = {"visit_motives": []}
    assert is_vaccination_center(data)


def test_is_category_relevant():
    assert not is_category_relevant(None)
    assert is_category_relevant("vaccination")


def test_is_appointment_relevant():
    assert not is_appointment_relevant(None)


def test_parse_practitioner_type():
    name = parse_practitioner_type("Pharmacie de la Gare", {})
    assert name == DRUG_STORE
    data = {"profile": {"speciality": {"slug": "medecin-generaliste"}}}
    name = parse_practitioner_type("Dr Coq", data)
    assert name == GENERAL_PRACTITIONER


def test_pop_practice_id():
    base_url = "https://partners.doctolib.fr/centre-de-vaccinations-internationales/ville1/centre1?pid=practice-165752&enable_cookies_consent=1"
    expected_result = (
        "https://partners.doctolib.fr/centre-de-vaccinations-internationales/ville1/centre1?enable_cookies_consent=1"
    )
    start_date = "2021-04-03"
    scraper_request = ScraperRequest(base_url, start_date)
    doctolib_slots = DoctolibSlots()
    doctolib_slots.pop_practice_id(scraper_request)
    assert scraper_request.url == expected_result


def test_set_doctolib_center_internal_id():
    base_url = "https://partners.doctolib.fr/centre-de-vaccinations-internationales/ville1/centre1?pid=practice-165752&enable_cookies_consent=1"
    start_date = "2021-04-03"
    scraper_request = ScraperRequest(base_url, start_date)

    TEST_CASES = [
        {
            "input": {
                "request": copy.copy(scraper_request),
                "data": {"profile": {"id": 245547}},
                "practice_ids": [123456],
                "practice_same_adress": False,
            },
            "expected_result": "doctolib245547pid123456",
        },
        {
            "input": {
                "request": copy.copy(scraper_request),
                "data": {"profile": {"id": 245547}},
                "practice_ids": [123456],
                "practice_same_adress": True,
            },
            "expected_result": "doctolib245547pid123456",
        },
        {
            "input": {
                "request": copy.copy(scraper_request),
                "data": {"profile": {"id": 245547}},
                "practice_ids": [],
                "practice_same_adress": False,
            },
            "expected_result": "doctolib245547",
        },
        {
            "input": {
                "request": copy.copy(scraper_request),
                "data": {"profile": {"id": 245547}},
                "practice_ids": None,
                "practice_same_adress": False,
            },
            "expected_result": "doctolib245547",
        },
        {
            "input": {
                "request": copy.copy(scraper_request),
                "data": {"profile": {}},
                "practice_ids": [123456],
                "practice_same_adress": False,
            },
            "expected_result": None,
        },
        {
            "input": {
                "request": copy.copy(scraper_request),
                "data": {},
                "practice_ids": [123456],
                "practice_same_adress": False,
            },
            "expected_result": None,
        },
        {
            "input": {
                "request": copy.copy(scraper_request),
                "data": {"profile": {"id": 245547}},
                "practice_ids": [123456, 789123],
                "practice_same_adress": False,
            },
            "expected_result": "doctolib245547",
        },
        {
            "input": {
                "request": copy.copy(scraper_request),
                "data": {"profile": {"id": 245547}},
                "practice_ids": [123456, 789123],
                "practice_same_adress": True,
            },
            "expected_result": "doctolib245547pid123456",
        },
    ]

    for case in TEST_CASES:
        set_doctolib_center_internal_id(**case["input"])
        assert case["input"]["request"].internal_id == case["expected_result"]
