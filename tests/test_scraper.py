import datetime as dt
import json

from scraper.pattern.center_info import CenterInfo, dict_to_center_info
from utils.vmd_utils import departementUtils
from scraper.scraper import fetch_centre_slots, export_data
from scraper.pattern.scraper_request import ScraperRequest
from scraper.error import BlockedByDoctolibError
from .utils import mock_datetime_now


def test_export_data(tmp_path):
    centres_cherchés_dict = [
        {
            "departement": "01",
            "nom": "Bugey Sud",
            "url": "https://example.com/bugey-sud",
            "plateforme": "Doctolib",
            "prochain_rdv": "2021-04-10T00:00:00",
            "location": None,
            "metadata": None,
            "type": None,
            "appointment_count": 0,
            "internal_id": None
        },
        {
            "departement": "59",
            "nom": "CH Armentières",
            "url": "https://example.com/ch-armentieres",
            "plateforme": "Keldoc",
            "prochain_rdv": "2021-04-11:00:00",
            "erreur": None,
            "location": None,
            "metadata": None,
            "type": None,
            "appointment_count": 0,
            "internal_id": None
        },
        {
            "departement": "59",
            "nom": "Clinique du Cambresis",
            "url": "https://example.com/clinique-du-cambresis",
            "plateforme": "Maiia",
            "prochain_rdv": None,
            "erreur": None,
            "location": None,
            "metadata": None,
            "type": None,
            "appointment_count": 0,
            "internal_id": None
        },
        {
            # Unknown departement (edge case) => should be skipped w/o failing
            "departement": "1234",
            "nom": "Hôpital magique",
            "url": "https://example.com/hopital-magique",
            "plateforme": "Doctolib",
            "prochain_rdv": "2021-04-12:00:00",
            "erreur": None,
            "location": None,
            "metadata": None,
            "type": None,
            "appointment_count": 0,
            "internal_id": None
        },
    ]
    centres_cherchés = [dict_to_center_info(center) for center in centres_cherchés_dict]
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    outpath_format = str(out_dir / "{}.json")

    fake_now = dt.datetime(2021, 4, 4)
    with mock_datetime_now(fake_now):
        export_data(centres_cherchés, outpath_format=outpath_format)

    # All departements for which we don't have data should be empty.
    for departement in departementUtils.import_departements():
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
                "location": None,
                "metadata": None,
                "type": None,
                "appointment_count": 0,
                "internal_id": None,
                "vaccine_type": None,
                "erreur": None
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
                "location": None,
                "metadata": None,
                "type": None,
                "appointment_count": 0,
                "internal_id": None,
                "vaccine_type": None,
                "erreur": None
            },
        ],
        "centres_indisponibles": [
            {
                "departement": "59",
                "nom": "Clinique du Cambresis",
                "url": "https://example.com/clinique-du-cambresis",
                "plateforme": "Maiia",
                "prochain_rdv": None,
                "location": None,
                "metadata": None,
                "type": None,
                "appointment_count": 0,
                "internal_id": None,
                "vaccine_type": None,
                "erreur": None
            }
        ],
        "last_updated": "2021-04-04T00:00:00",
    }

    # On test l'export vers le format inscrit sur la plateforme data.gouv.fr
    content = json.loads((out_dir / "centres_open_data.json").read_text())
    assert content == [
        {
            "departement": "01",
            "nom": "Bugey Sud",
            "url": "https://example.com/bugey-sud",
            "plateforme": "Doctolib"
        },
        {
            "departement": "59",
            "nom": "CH Armentières",
            "url": "https://example.com/ch-armentieres",
            "plateforme": "Keldoc"
        },
        {
            "departement": "59",
            "nom": "Clinique du Cambresis",
            "url": "https://example.com/clinique-du-cambresis",
            "plateforme": "Maiia"
        },
    ]


def test_export_data_when_blocked(tmp_path):
    center_info1 = CenterInfo("59", "Clinique du Cambresis", "https://example.com/clinique-du-cambresis")
    center_info1.plateforme = "Maiia"
    center_info1.prochain_rdv = "2021-04-12:00:00"
    center_info1.erreur = None

    center_info2 = CenterInfo("14", "Hôpital magique", "https://example.com/hopital-magique")
    center_info2.plateforme = "Doctolib"
    center_info2.prochain_rdv = None
    center_info2.erreur = BlockedByDoctolibError("https://example.com/hopital-magique")
    centres_cherchés = [
        center_info1,
        center_info2
    ]

    out_dir = tmp_path / "out"
    out_dir.mkdir()
    outpath_format = str(out_dir / "{}.json")

    fake_now = dt.datetime(2021, 4, 4)
    with mock_datetime_now(fake_now):
        total, actifs, bloqués = export_data(centres_cherchés, outpath_format=outpath_format)

    # les totaux doivent être bons
    assert total == 2
    assert actifs == 1
    assert bloqués == 1

    # Departements 14 and 59 should contain expected data.
    content = json.loads((out_dir / "14.json").read_text())
    assert content == {
        "version": 1,
        "last_updated": "2021-04-04T00:00:00",
        "centres_disponibles": [],
        "centres_indisponibles": [{
            "departement": "14",
            "nom": "Hôpital magique",
            "url": "https://example.com/hopital-magique",
            "location": None,
            "metadata": None,
            "prochain_rdv": None,
            "type": None,
            "plateforme": "Doctolib",
            "appointment_count": 0,
            "internal_id": None,
            "vaccine_type": None,
            "erreur": "ERREUR DE SCRAPPING (Doctolib): Doctolib bloque nos appels: 403 https://example.com/hopital-magique"
        }],
        "doctolib_bloqué": True
    }

    content = json.loads((out_dir / "59.json").read_text())
    assert content == {
        "version": 1,
        "centres_disponibles": [
            {
                "departement": "59",
                "nom": "Clinique du Cambresis",
                "url": "https://example.com/clinique-du-cambresis",
                "plateforme": "Maiia",
                "prochain_rdv": "2021-04-12:00:00",
                "location": None,
                "metadata": None,
                "type": None,
                "appointment_count": 0,
                "internal_id": None,
                "vaccine_type": None,
                "erreur": None
            },
        ],
        "centres_indisponibles": [],
        "last_updated": "2021-04-04T00:00:00",
    }



def test_fetch_centre_slots():
    """
    We detect which implementation to use based on the visit URL.
    """
    def fake_doctolib_fetch_slots(request: ScraperRequest):
        return "2021-04-04"

    def fake_keldoc_fetch_slots(request: ScraperRequest):
        return "2021-04-05"

    def fake_maiia_fetch_slots(request: ScraperRequest):
        return "2021-04-06"

    fetch_map = {
        'Doctolib': {'urls': [
            'https://partners.doctolib.fr',
            'https://www.doctolib.fr'
        ], 'scraper_ptr': fake_doctolib_fetch_slots},
        'Keldoc': {'urls': [
            'https://vaccination-covid.keldoc.com',
            'https://keldoc.com'
        ], 'scraper_ptr': fake_keldoc_fetch_slots},
        'Maiia': {'urls': [
            'https://www.maiia.com'
        ], 'scraper_ptr': fake_maiia_fetch_slots}
    }

    start_date = "2021-04-03"

    # Doctolib
    url = "https://partners.doctolib.fr/blabla"
    res = fetch_centre_slots(url, start_date, fetch_map=fetch_map)
    assert res.platform == "Doctolib"
    assert res.next_availability == "2021-04-04"

    # Doctolib (old)
    url = "https://www.doctolib.fr/blabla"
    res = fetch_centre_slots(url, start_date, fetch_map=fetch_map)
    assert res.platform == "Doctolib"
    assert res.next_availability == "2021-04-04"

    # Keldoc
    url = "https://vaccination-covid.keldoc.com/blabla"
    res = fetch_centre_slots(url, start_date, fetch_map=fetch_map)
    assert res.platform == "Keldoc"
    assert res.next_availability == "2021-04-05"

    # Maiia
    url = "https://www.maiia.com/blabla"
    res = fetch_centre_slots(url, start_date, fetch_map=fetch_map)
    assert res.platform == "Maiia"
    assert res.next_availability == "2021-04-06"

    # Default / unknown
    url = "https://www.example.com"
    res = fetch_centre_slots(url, start_date, fetch_map=fetch_map)
    assert res.platform == "Autre"
    assert res.next_availability is None
