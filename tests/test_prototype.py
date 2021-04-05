import datetime as dt
import json
import pytest
from scraper.departements import import_departements, to_departement_number
from scraper.prototype import fetch_centre_slots, export_data

from .utils import mock_datetime_now

def test_insee_to_departement_code():
    right_insee_code = "12345"
    short_insee_code = "1234"
    DOM_TOM_insee_code = "97234"
    wrong_insee_code = "123"
    assert to_departement_number(right_insee_code) == right_insee_code[:2]
    assert to_departement_number(short_insee_code) == f"0{short_insee_code[:1]}"
    assert to_departement_number(DOM_TOM_insee_code) == DOM_TOM_insee_code[:3]
    with pytest.raises(ValueError):
        to_departement_number(wrong_insee_code)

def test_export_data(tmp_path):
    centres_cherchés = [
        {
            "departement": "01",
            "nom": "Bugey Sud",
            "url": "https://example.com/bugey-sud",
            "plateforme": "Doctolib",
            "prochain_rdv": "2021-04-10T00:00:00",
        },
        {
            "departement": "59",
            "nom": "CH Armentières",
            "url": "https://example.com/ch-armentieres",
            "plateforme": "Keldoc",
            "prochain_rdv": "2021-04-11:00:00",
        },
        {
            "departement": "59",
            "nom": "Clinique du Cambresis",
            "url": "https://example.com/clinique-du-cambresis",
            "plateforme": "Maiia",
            "prochain_rdv": None,
        },
        {
            # Unknown departement (edge case) => should be skipped w/o failing
            "departement": "1234",
            "nom": "Hôpital magique",
            "url": "https://example.com/hopital-magique",
            "plateforme": "Doctolib",
            "prochain_rdv": "2021-04-12:00:00",
        },
    ]

    out_dir = tmp_path / "out"
    out_dir.mkdir()
    outpath_format = str(out_dir / "{}.json")

    fake_now = dt.datetime(2021, 4, 4)
    with mock_datetime_now(fake_now):
        export_data(centres_cherchés, outpath_format=outpath_format)

    # All departements for which we don't have data should be empty.
    for departement in import_departements():
        if departement in ("01", "59"):
            continue
        content = json.loads((out_dir / f"{departement}.json").read_text())
        assert content == {
            "version": 1,
            "centres_disponibles": [],
            "centres_indisponibles": [],
            "last_updated": "2021-04-04T00:00:00",
        }

    # Departements 01 and 59 should contain expected data.

    content = json.loads((out_dir / "01.json").read_text())
    assert content == {
        "version": 1,
        "centres_disponibles": [
            {
                "departement": "01",
                "nom": "Bugey Sud",
                "url": "https://example.com/bugey-sud",
                "plateforme": "Doctolib",
                "prochain_rdv": "2021-04-10T00:00:00",
            },
        ],
        "centres_indisponibles": [],
        "last_updated": "2021-04-04T00:00:00",
    }

    content = json.loads((out_dir / "59.json").read_text())
    assert content == {
        "version": 1,
        "centres_disponibles": [
            {
                "departement": "59",
                "nom": "CH Armentières",
                "url": "https://example.com/ch-armentieres",
                "plateforme": "Keldoc",
                "prochain_rdv": "2021-04-11:00:00",
            },
        ],
        "centres_indisponibles": [
            {
                "departement": "59",
                "nom": "Clinique du Cambresis",
                "url": "https://example.com/clinique-du-cambresis",
                "plateforme": "Maiia",
                "prochain_rdv": None,
            }
        ],
        "last_updated": "2021-04-04T00:00:00",
    }


def test_fetch_centre_slots():
    """
    We detect which implementation to use based on the visit URL.
    """
    def fake_doctolib_fetch_slots(rdv_site_web, start_date):
        return "2021-04-04"

    def fake_keldoc_fetch_slots(rdv_site_web, start_date):
        return "2021-04-05"

    def fake_maiia_fetch_slots(rdv_site_web, start_date):
        return "2021-04-06"

    fetch_map = {
        "Doctolib": fake_doctolib_fetch_slots,
        "Keldoc": fake_keldoc_fetch_slots,
        "Maiia": fake_maiia_fetch_slots,
    }

    start_date = "2021-04-03"

    # Doctolib
    url = "https://partners.doctolib.fr/blabla"
    assert fetch_centre_slots(url, start_date, fetch_map=fetch_map) == (
        "Doctolib",
        "2021-04-04",
    )

    # Doctolib (old)
    url = "https://www.doctolib.fr/blabla"
    assert fetch_centre_slots(url, start_date, fetch_map=fetch_map) == (
        "Doctolib",
        "2021-04-04",
    )

    # Keldoc
    url = "https://vaccination-covid.keldoc.com/blabla"
    assert fetch_centre_slots(url, start_date, fetch_map=fetch_map) == (
        "Keldoc",
        "2021-04-05",
    )

    # Maiia
    url = "https://www.maiia.com/blabla"
    assert fetch_centre_slots(url, start_date, fetch_map=fetch_map) == (
        "Maiia",
        "2021-04-06",
    )

    # Default / unknown
    url = "https://www.example.com"
    assert fetch_centre_slots(url, start_date, fetch_map=fetch_map) == ("Autre", None)
