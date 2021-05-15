import datetime as dt
import json

from scraper.export.export_merge import export_data
from scraper.pattern.center_info import CenterInfo
from scraper.pattern.scraper_result import GENERAL_PRACTITIONER, ScraperResult
from scraper.pattern.vaccine import Vaccine, get_vaccine_name
from utils.vmd_utils import departementUtils
from scraper.scraper import fetch_centre_slots, get_start_date, gouv_centre_iterator
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
            "appointment_count": 1,
            "internal_id": None,
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
            "appointment_count": 1,
            "internal_id": None,
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
            "appointment_count": 1,
            "internal_id": None,
        },
        {
            "departement": "92",
            "nom": "Médiathèque Jacques GAUTIER",
            "url": "https://example.com/mediatheque-jacques-gautier",
            "plateforme": "Maiia",
            "prochain_rdv": "2021-04-11:00:00",
            "erreur": None,
            "location": None,
            "metadata": None,
            "type": None,
            "appointment_count": 0,
            "internal_id": None,
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
            "appointment_count": 1,
            "internal_id": None,
        },
        {
            # Not technically a department, should be in om.json
            "departement": "975",
            "nom": "Exemple Saint Pierre et Miquelon",
            "url": "https://example.com/st-pierre-miquelon",
            "plateforme": "Doctolib",
            "prochain_rdv": "2021-05-10T00:00:00",
            "location": None,
            "metadata": None,
            "type": None,
            "appointment_by_phone_only": False,
            "appointment_count": 1,
            "internal_id": None,
        },
    ]
    centres_cherchés = [CenterInfo.from_dict(center) for center in centres_cherchés_dict]

    for center in centres_cherchés:
        if center.nom != "Médiathèque Jacques GAUTIER":
            center.appointment_count = 1

    out_dir = tmp_path / "out"
    out_dir.mkdir()
    outpath_format = str(out_dir / "{}.json")

    fake_now = dt.datetime(2021, 4, 4)
    get_start_date()
    with mock_datetime_now(fake_now):
        export_data(centres_cherchés, [], outpath_format=outpath_format)

    # All departements for which we don't have data should be empty.
    for departement in departementUtils.import_departements():
        if departement in ("01", "59", "92"):
            continue
        content = json.loads((out_dir / f"{departement}.json").read_text())
        assert content == {
            "version": 1,
            "last_scrap": [],
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
                "appointment_by_phone_only": False,
                "appointment_count": 1,
                "internal_id": None,
                "appointment_by_phone_only": False,
                "vaccine_type": None,
                "erreur": None,
                "last_scan_with_availabilities": None,
                "request_counts": None,
            },
        ],
        "centres_indisponibles": [],
        "last_scrap": [],
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
                "appointment_by_phone_only": False,
                "type": None,
                "appointment_count": 1,
                "internal_id": None,
                "vaccine_type": None,
                "erreur": None,
                "last_scan_with_availabilities": None,
                "request_counts": None,
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
                "appointment_count": 1,
                "internal_id": None,
                "appointment_by_phone_only": False,
                "vaccine_type": None,
                "erreur": None,
                "last_scan_with_availabilities": None,
                "request_counts": None,
            }
        ],
        "last_scrap": [],
        "last_updated": "2021-04-04T00:00:00",
    }

    content = json.loads((out_dir / "92.json").read_text())
    assert content == {
        "version": 1,
        "centres_disponibles": [],
        "centres_indisponibles": [
            {
                "departement": "92",
                "nom": "Médiathèque Jacques GAUTIER",
                "url": "https://example.com/mediatheque-jacques-gautier",
                "location": None,
                "metadata": None,
                "prochain_rdv": "2021-04-11:00:00",
                "plateforme": "Maiia",
                "type": None,
                "appointment_by_phone_only": False,
                "appointment_count": 0,
                "internal_id": None,
                "vaccine_type": None,
                "erreur": None,
                "last_scan_with_availabilities": None,
                "request_counts": None,
            },
        ],
        "last_scrap": [],
        "last_updated": "2021-04-04T00:00:00",
    }

    # outre-mer file should contain St Pierre et Miquelon data
    content = json.loads((out_dir / "om.json").read_text())
    assert content == {
        "version": 1,
        "centres_disponibles": [
            {
                "departement": "om",
                "nom": "Exemple Saint Pierre et Miquelon",
                "url": "https://example.com/st-pierre-miquelon",
                "plateforme": "Doctolib",
                "prochain_rdv": "2021-05-10T00:00:00",
                "location": None,
                "metadata": None,
                "type": None,
                "appointment_by_phone_only": False,
                "appointment_count": 1,
                "internal_id": None,
                "vaccine_type": None,
                "erreur": None,
                "last_scan_with_availabilities": None,
                "request_counts": None,
            },
        ],
        "centres_indisponibles": [],
        "last_scrap": [],
        "last_updated": "2021-04-04T00:00:00",
    }

    # On test l'export vers le format inscrit sur la plateforme data.gouv.fr
    content = json.loads((out_dir / "centres_open_data.json").read_text())
    assert content == [
        {"departement": "01", "nom": "Bugey Sud", "url": "https://example.com/bugey-sud", "plateforme": "Doctolib"},
        {
            "departement": "59",
            "nom": "CH Armentières",
            "url": "https://example.com/ch-armentieres",
            "plateforme": "Keldoc",
        },
        {
            "departement": "59",
            "nom": "Clinique du Cambresis",
            "url": "https://example.com/clinique-du-cambresis",
            "plateforme": "Maiia",
        },
        {
            "departement": "92",
            "nom": "Médiathèque Jacques GAUTIER",
            "url": "https://example.com/mediatheque-jacques-gautier",
            "plateforme": "Maiia",
        },
        {
            "departement": "om",
            "nom": "Exemple Saint Pierre et Miquelon",
            "plateforme": "Doctolib",
            "url": "https://example.com/st-pierre-miquelon",
        },
    ]


def test_export_reserved_centers(tmp_path):
    centres_cherchés_dict = [
        {
            "departement": "01",
            "nom": "Bugey Sud - Réservé aux médecins du groupe hospitalier",
            "url": "https://example.com/bugey-sud",
            "plateforme": "Doctolib",
            "prochain_rdv": "2021-04-10T00:00:00",
            "location": None,
            "metadata": None,
            "type": None,
            "appointment_by_phone_only": False,
            "appointment_count": 1,
            "internal_id": None,
        }
    ]
    centres_cherchés = [CenterInfo.from_dict(center) for center in centres_cherchés_dict]

    out_dir = tmp_path / "out"
    out_dir.mkdir()
    outpath_format = str(out_dir / "{}.json")

    fake_now = dt.datetime(2021, 4, 4)
    get_start_date()
    with mock_datetime_now(fake_now):
        export_data(centres_cherchés, [], outpath_format=outpath_format)

    # Departements 01 and 59 should contain expected data.

    content = json.loads((out_dir / "01.json").read_text())
    assert content == {
        "version": 1,
        "centres_disponibles": [],
        "centres_indisponibles": [],
        "last_scrap": [],
        "last_updated": "2021-04-04T00:00:00",
    }


def test_get_vaccine_name():
    assert get_vaccine_name("Vaccination Covid -55ans suite à une première injection d'AZ (ARNm)") == Vaccine.ARNM
    assert get_vaccine_name("Vaccination ARN suite à une 1ere injection Astra Zeneca") == Vaccine.ARNM
    assert (
        get_vaccine_name("Vaccination Covid de moins de 55ans (vaccin ARNm) suite à une 1ère injection d'AZ")
        == Vaccine.ARNM
    )
    assert get_vaccine_name("Vaccination Covid +55ans AZ") == Vaccine.ASTRAZENECA
    assert get_vaccine_name("Vaccination Covid Pfizer") == Vaccine.PFIZER
    assert get_vaccine_name("Vaccination Covid Moderna") == Vaccine.MODERNA


def test_export_data_when_blocked(tmp_path):
    center_info1 = CenterInfo("59", "Clinique du Cambresis", "https://example.com/clinique-du-cambresis")
    center_info1.plateforme = "Maiia"
    center_info1.prochain_rdv = "2021-04-12:00:00"
    center_info1.erreur = None
    center_info1.appointment_count = 1

    center_info2 = CenterInfo("14", "Hôpital magique", "https://example.com/hopital-magique")
    center_info2.plateforme = "Doctolib"
    center_info2.prochain_rdv = None
    center_info2.erreur = BlockedByDoctolibError("https://example.com/hopital-magique")
    centres_cherchés = [center_info1, center_info2]

    out_dir = tmp_path / "out"
    out_dir.mkdir()
    outpath_format = str(out_dir / "{}.json")

    fake_now = dt.datetime(2021, 4, 4)
    with mock_datetime_now(fake_now):
        total, actifs, bloqués = export_data(centres_cherchés, [], outpath_format=outpath_format)

    # les totaux doivent être bons
    assert total == 2
    assert actifs == 1
    assert bloqués == 1

    # Departements 14 and 59 should contain expected data.
    content = json.loads((out_dir / "14.json").read_text())
    assert content == {
        "version": 1,
        "last_updated": "2021-04-04T00:00:00",
        "last_scrap": [],
        "centres_disponibles": [],
        "centres_indisponibles": [
            {
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
                "appointment_by_phone_only": False,
                "erreur": "ERREUR DE SCRAPPING (Doctolib): Doctolib bloque nos appels: 403 https://example.com/hopital-magique",
                "last_scan_with_availabilities": None,
                "request_counts": None,
            }
        ],
        "doctolib_bloqué": True,
    }

    content = json.loads((out_dir / "59.json").read_text())
    assert content == {
        "version": 1,
        "last_scrap": [],
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
                "appointment_count": 1,
                "internal_id": None,
                "appointment_by_phone_only": False,
                "vaccine_type": None,
                "erreur": None,
                "last_scan_with_availabilities": None,
                "request_counts": None,
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
        "Doctolib": {
            "urls": ["https://partners.doctolib.fr", "https://www.doctolib.fr"],
            "scraper_ptr": fake_doctolib_fetch_slots,
        },
        "Keldoc": {
            "urls": ["https://vaccination-covid.keldoc.com", "https://keldoc.com"],
            "scraper_ptr": fake_keldoc_fetch_slots,
        },
        "Maiia": {"urls": ["https://www.maiia.com"], "scraper_ptr": fake_maiia_fetch_slots},
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


def test_scraper_request():
    request = ScraperRequest("https://doctolib.fr/center/center-test", "2021-04-14")

    request.update_internal_id("d739")
    request.update_practitioner_type(GENERAL_PRACTITIONER)
    request.update_appointment_count(42)
    request.add_vaccine_type(get_vaccine_name("Injection pfizer 1ère dose"))

    assert request is not None
    assert request.internal_id == "d739"
    assert request.appointment_count == 42
    assert request.vaccine_type == [Vaccine.PFIZER]

    result = ScraperResult(request, "Doctolib", "2021-04-14T14:00:00.0000")
    assert result.default() == {
        "next_availability": "2021-04-14T14:00:00.0000",
        "platform": "Doctolib",
        "request": request,
    }


def test_has_gouv_centers():
    itr = gouv_centre_iterator()
    assert sum(1 for center in itr) > 0
