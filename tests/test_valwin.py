import json
from scraper.pattern.scraper_request import ScraperRequest
from scraper.pattern.center_info import CenterInfo
import httpx
from pathlib import Path
import io
import scraper.valwin.valwin as valwin
from scraper.pattern.vaccine import Vaccine
from utils.vmd_config import get_conf_platform
import httpx
import pytest


VALWIN_conf = get_conf_platform("Valwin")
VALWIN_APIs = VALWIN_conf.get("api", "")


TEST_CENTRE_INFO = Path("tests", "fixtures", "valwin", "valwin_center_info.json")


def test_get_appointments():

    """get_appointments should return first available appointment date"""

    center_data = dict()
    center_data = json.load(io.open(TEST_CENTRE_INFO, "r", encoding="utf-8-sig"))
    center_info = CenterInfo.from_csv_data(center_data)

    # This center has availabilities and should return a date, non null appointment_count and vaccines
    request = ScraperRequest(
        "https://pharma-api.epharmacie.pro/global/api/meetings/v2/aptiphar18-priker-magny-hameaux/slots",
        "2021-09-11",
        center_info,
        "Valwinaptiphar18-priker-magny-hameau"
    )
    center_with_availability = valwin.Slots()
    slots = json.load(
        io.open(Path("tests", "fixtures", "valwin", "slots_available.json"), "r", encoding="utf-8-sig")
    )

    assert center_with_availability.get_appointments(request, slots_api=slots) ==  "2021-09-17T11:50:00"
    assert request.appointment_count == 12
    assert request.vaccine_type == [Vaccine.ASTRAZENECA]

    # This one should return no date, neither appointment_count nor vaccine.
    request = ScraperRequest(
        "https://pharma-api.epharmacie.pro/global/api/meetings/v2/pharmabest75-plateau-lyon/slots",
        "2021-08-10",
        center_info,
        "Valwinpharmabest75-plateau-lyon"
    )
    center_without_availability = valwin.Slots()
    slots = json.load(
        io.open(Path("tests", "fixtures", "bimedoc", "slots_unavailable.json"), "r", encoding="utf-8-sig")
    )
    assert center_without_availability.get_appointments(request, slots_api=slots) == None
    assert request.appointment_count == 0
    assert request.vaccine_type == None


from unittest.mock import patch

# On se place dans le cas où la plateforme est désactivée
def test_fetch_slots():
    valwin.PLATFORM_ENABLED = False
    center_data = dict()
    center_data = json.load(io.open(TEST_CENTRE_INFO, "r", encoding="utf-8-sig"))
    center_info = CenterInfo.from_csv_data(center_data)

    request = ScraperRequest(
        "https://pharma-api.epharmacie.pro/global/api/meetings/v2/pharmabest75-plateau-lyon/slots",
        "2021-08-10",
        center_info,
    )
    response = valwin.fetch_slots(request)
    # On devrait trouver None puisque la plateforme est désactivée
    assert response == None



def test_fetch():
    def app(requested: httpx.Request) -> httpx.Response:
        assert "User-Agent" in requested.headers
        return httpx.Response(responsecode, json=slots)


    valwin.PLATFORM_ENABLED = True

    center_data = dict()
    center_data = json.load(io.open(TEST_CENTRE_INFO, "r", encoding="utf-8-sig"))

    center_info = CenterInfo.from_csv_data(center_data)

    # This center has availabilities and should return a date, non null appointment_count and vaccines
    request = ScraperRequest(
        "https://pharma-api.epharmacie.pro/global/api/meetings/v2/pharmabest75-plateau-lyon/slots",
        "2021-08-10",
        center_info,
    )
    slots = json.load(
        io.open(Path("tests", "fixtures", "valwin", "slots_available.json"), "r", encoding="utf-8-sig")
    )

    #Response 200
    responsecode=200
    client = httpx.Client(transport=httpx.MockTransport(app))
    center_with_availability = valwin.Slots(client=client)
    response = center_with_availability.fetch(request)
    assert response == "2021-09-17T11:50:00"

    #Response 403

    responsecode=403
    client = httpx.Client(transport=httpx.MockTransport(app))
    center_with_availability = valwin.Slots(client=client)
    with pytest.raises(Exception):
        response = center_with_availability.fetch(request)
        assert response == None


def test_center_iterator():
    result = valwin.center_iterator()
    if valwin.PLATFORM_ENABLED == False:
        assert result == None


def test_center_iterator():
    def app(request: httpx.Request) -> httpx.Response:
        path = Path("tests/fixtures/valwin/valwin_centers.json")
        return httpx.Response(200, json=json.loads(path.read_text(encoding="utf8")))

    client = httpx.Client(transport=httpx.MockTransport(app))
    centres = [centre for centre in valwin.center_iterator(client)]
    print(centres)
    assert len(centres) == 3
