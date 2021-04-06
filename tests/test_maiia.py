from datetime import datetime
from pathlib import Path

from bs4 import BeautifulSoup
import requests

import scraper
from scraper.maiia import (
    fetch_slots,
    get_slots_from,
    get_any_availibility_from,
)


class MockResponse:
    text = ""

    @staticmethod
    def raise_for_status():
        raise requests.exceptions.HTTPError


class MockBeautifulSoup:
    def __init__(self, *args):
        pass

    def find(self, id):
        path = Path("tests/maiia_test_rdv_form.html")
        return BeautifulSoup(path.read_text(), "html.parser").find(id=id)


class TestMaiia:
    """Quelques tests pour le scrape de  Maiia"""

    START_DATE = "2021-04-05"

    def test_fetch_slot_raise_HTTPError(self, monkeypatch):
        scraper.maiia.session = requests

        def mock_get(*args, **kwargs):
            return MockResponse()

        # On applique la fonction pour "mockée" pour la levée d'exception :
        monkeypatch.setattr(requests, "get", mock_get)
        assert fetch_slots("http://dummy_website.com", TestMaiia.START_DATE) is None

    def test_fetch_slot_with_incorrect_soup(self):
        dt = datetime.now()
        assert fetch_slots("http://google.com", TestMaiia.START_DATE) is None


    def test_fetch_slot(self):
        scraper.maiia.BeautifulSoup = MockBeautifulSoup
        assert fetch_slots("https://google.com", TestMaiia.START_DATE) is None