import json
from scraper.pattern.scraper_request import ScraperRequest
from scraper.pattern.center_info import CenterInfo
import httpx
from pathlib import Path
import io
import scraper.bimedoc.bimedoc as bimedoc
from scraper.pattern.vaccine import Vaccine
from utils.vmd_config import get_conf_platform
import httpx
from scraper.error import BlockedByBimedocError
import pytest


BIMEDOC_CONF = get_conf_platform("bimedoc")
BIMEDOC_APIs = BIMEDOC_CONF.get("api", "")


TEST_CENTRE_INFO = Path("tests", "fixtures", "bimedoc", "bimedoc_center_info.json")


def test_get_appointments():

    """get_appointments should return first available appointment date"""

    center_data = dict()
    center_data = json.load(io.open(TEST_CENTRE_INFO, "r", encoding="utf-8-sig"))
    center_info = CenterInfo.from_csv_data(center_data)

    # This center has availabilities and should return a date, non null appointment_count and vaccines
    request = ScraperRequest(
        "https://server.bimedoc.com/vmd/pharmacy-with-slots/9cf46288-0080-4a8d-8856-8e9998ced9f7?start_date=2021-08-10&end_date=2021-08-17",
        "2021-08-10",
        center_info,
        "Bimedoc9cf46288-0080-4a8d-8856-8e9998ced9f"
    )
    center_with_availability = bimedoc.BimedocSlots()
    slots = json.load(
        io.open(Path("tests", "fixtures", "bimedoc", "slots_available.json"), "r", encoding="utf-8-sig")
    )

    assert center_with_availability.get_appointments(request, slots_api=slots) ==  "2021-08-11T08:15:00Z"
    assert request.appointment_count == 133
    assert request.vaccine_type == [Vaccine.PFIZER]

    # This one should return no date, neither appointment_count nor vaccine.
    request = ScraperRequest(
        "https://server.bimedoc.com/vmd/pharmacy-with-slots/9cf46288-0080-4a8d-8856-8e9998ced9f7?start_date=2021-08-10&end_date=2021-08-17",
        "2021-08-10",
        center_info,
    )
    center_without_availability = bimedoc.BimedocSlots()
    slots = json.load(
        io.open(Path("tests", "fixtures", "bimedoc", "slots_unavailable.json"), "r", encoding="utf-8-sig")
    )
    assert center_without_availability.get_appointments(request, slots_api=slots) == None
    assert request.appointment_count == 0
    assert request.vaccine_type == None


from unittest.mock import patch

# On se place dans le cas où la plateforme est désactivée
def test_fetch_slots():
    bimedoc.PLATFORM_ENABLED = False
    center_data = dict()
    center_data = json.load(io.open(TEST_CENTRE_INFO, "r", encoding="utf-8-sig"))
    center_info = CenterInfo.from_csv_data(center_data)

    request = ScraperRequest(
        "https://server.bimedoc.com/vmd/pharmacy-with-slots/9cf46288-0080-4a8d-8856-8e9998ced9f7?start_date=2021-08-10&end_date=2021-08-17",
        "2021-08-10",
        center_info
    )
    response = bimedoc.fetch_slots(request)
    # On devrait trouver None puisque la plateforme est désactivée
    assert response == None



def test_fetch():
    def app(requested: httpx.Request) -> httpx.Response:
        assert "User-Agent" in requested.headers
        return httpx.Response(responsecode, json=slots)


    bimedoc.PLATFORM_ENABLED = True

    center_data = dict()
    center_data = json.load(io.open(TEST_CENTRE_INFO, "r", encoding="utf-8-sig"))

    center_info = CenterInfo.from_csv_data(center_data)

    # This center has availabilities and should return a date, non null appointment_count and vaccines
    request = ScraperRequest(
        "https://server.bimedoc.com/vmd/pharmacy-with-slots/9cf46288-0080-4a8d-8856-8e9998ced9f7?start_date=2021-08-10&end_date=2021-08-17",
        "2021-08-10",
        center_info
    )
    slots = json.load(
        io.open(Path("tests", "fixtures", "bimedoc", "slots_available.json"), "r", encoding="utf-8-sig")
    )

    #Response 200
    responsecode=200
    client = httpx.Client(transport=httpx.MockTransport(app))
    center_with_availability = bimedoc.BimedocSlots(client=client)
    response = center_with_availability.fetch(request)
    assert response == "2021-08-11T08:15:00Z"

    #Response 403

    responsecode=403
    client = httpx.Client(transport=httpx.MockTransport(app))
    center_with_availability = bimedoc.BimedocSlots(client=client)
    with pytest.raises(Exception):
        response = center_with_availability.fetch(request)
        assert response == None


def test_center_iterator():
    result = bimedoc.center_iterator()
    if bimedoc.PLATFORM_ENABLED == False:
        assert result == None


def test_center_iterator():
    def app(request: httpx.Request) -> httpx.Response:
        path = Path("tests/fixtures/bimedoc/bimedoc_centers.json")
        return httpx.Response(200, json=json.loads(path.read_text(encoding="utf8")))

    client = httpx.Client(transport=httpx.MockTransport(app))
    centres = [centre for centre in bimedoc.center_iterator(client)]
    assert len(centres) == 3
