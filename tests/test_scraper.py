import datetime as dt
import json

from scraper.pattern.center_info import CenterInfo
from scraper.pattern.scraper_result import GENERAL_PRACTITIONER, ScraperResult
from scraper.pattern.vaccine import Vaccine, get_vaccine_name
from utils.vmd_utils import departementUtils
from scraper.scraper import fetch_centre_slots
from scraper.pattern.scraper_request import ScraperRequest
from scraper.error import BlockedByDoctolibError
from .utils import mock_datetime_now
from utils.vmd_utils import DummyQueue
from scraper.pattern.center_info import CenterInfo


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


def test_fetch_centre_slots():
    """
    We detect which implementation to use based on the visit URL.
    """

    def fake_doctolib_fetch_slots(request: ScraperRequest, sdate, **kwargs):
        return "2021-04-04"

    def fake_keldoc_fetch_slots(request: ScraperRequest, sdate, **kwargs):
        return "2021-04-05"

    def fake_maiia_fetch_slots(request: ScraperRequest, sdate, **kwargs):
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
    center_info = CenterInfo(departement="08", nom="Mon Centre", url="https://some.url/")

    # Doctolib
    url = "https://partners.doctolib.fr/blabla"
    res = fetch_centre_slots(
        url, None, start_date, fetch_map=fetch_map, creneau_q=DummyQueue(), center_info=center_info
    )
    assert res.platform == "Doctolib"
    assert res.next_availability == "2021-04-04"

    # Doctolib (old)
    url = "https://www.doctolib.fr/blabla"
    res = fetch_centre_slots(
        url, None, start_date, fetch_map=fetch_map, creneau_q=DummyQueue(), center_info=center_info
    )
    assert res.platform == "Doctolib"
    assert res.next_availability == "2021-04-04"

    # Keldoc
    url = "https://vaccination-covid.keldoc.com/blabla"
    res = fetch_centre_slots(
        url, None, start_date, fetch_map=fetch_map, creneau_q=DummyQueue(), center_info=center_info
    )
    assert res.platform == "Keldoc"
    assert res.next_availability == "2021-04-05"

    # Maiia
    url = "https://www.maiia.com/blabla"
    res = fetch_centre_slots(
        url, None, start_date, fetch_map=fetch_map, creneau_q=DummyQueue(), center_info=center_info
    )
    assert res.platform == "Maiia"
    assert res.next_availability == "2021-04-06"

    # Default / unknown
    url = "https://www.example.com"
    res = fetch_centre_slots(
        url, None, start_date, fetch_map=fetch_map, creneau_q=DummyQueue(), center_info=center_info
    )
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
