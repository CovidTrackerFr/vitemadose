from datetime import datetime
import json

import requests
from bs4 import BeautifulSoup

import scraper
from scraper.maiia import (
    fetch_slots,
    get_slots_from,
)
from scraper.pattern.scraper_request import ScraperRequest


class MockResponse:
    text = ""

    @staticmethod
    def raise_for_status():
        raise requests.exceptions.HTTPError


class MockBeautifulSoup:
    def __init__(self, *args):
        pass

    def find(self, id):
        with open("tests/fixtures/maiia/maiia_test_rdv_form.html", "r") as f:
            return BeautifulSoup(f.read(), "html.parser").find(id=id)


class TestMaiia:
    """Quelques tests pour le scrape de  Maiia"""

    START_DATE = "2021-04-05"

    def test_fetch_slot_raise_HTTPError(self, monkeypatch):
        scraper.maiia.session = requests

        def mock_get(*args, **kwargs):
            return MockResponse()

        # On applique la fonction pour "mockée" pour la levée d'exception :
        monkeypatch.setattr(requests, "get", mock_get)
        scrap_request = ScraperRequest("http://dummy_website.com", TestMaiia.START_DATE)
        assert fetch_slots(scrap_request) is None

    def test_fetch_slot_with_incorrect_soup(self):
        dt = datetime.now()
        scrap_request = ScraperRequest("http://google.com", TestMaiia.START_DATE)
        assert fetch_slots(scrap_request) is None

    def test_fetch_slot(self):
        scraper.maiia.BeautifulSoup = MockBeautifulSoup
        scrap_request = ScraperRequest("http://google.com", TestMaiia.START_DATE)
        assert fetch_slots(scrap_request) is None

    def test_get_slots_from(self):
        # Testing the None return if rdv_form doesn't have a correct shape
        # RdvForm = make_dataclass("RdvForm",
        #                          [("contents", list, field(default_factory=list))])
        # rdv_form = RdvForm()
        # rdv_form.contents = ['{}']
        # assert get_slots_from(rdv_form, "", "") is None

        # Testing with correct data rdv_form
        with open("tests/fixtures/maiia/maiia_script_response.html", "r") as html_file:
            soup = BeautifulSoup(html_file, "html.parser")

        with open("tests/fixtures/maiia/availability.json", "r") as json_file:
            availibility = json.load(json_file)

        def mock_get_availibility(*args):
            return availibility

        scraper.maiia.get_any_availibility_from = mock_get_availibility
        scrap_request = ScraperRequest("", "")

        assert get_slots_from(soup.script, scrap_request) == "2021-05-04T14:00:00.000000Z"

        del availibility["firstPhysicalStartDateTime"]
        assert get_slots_from(soup.script, scrap_request) == "2021-05-04T14:00:00.000000Z"

        del availibility["closestPhysicalAvailability"]
        assert get_slots_from(soup.script, scrap_request) is None
