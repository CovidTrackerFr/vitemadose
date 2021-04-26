import json
import httpx

from bs4 import BeautifulSoup
from pathlib import Path
from datetime import datetime

from scraper.mapharma.mapharma import parse_slots, fetch_slots
from scraper.pattern.scraper_request import ScraperRequest

TEST_OPEN_DATA_FILE = Path('tests', 'fixtures', 'mapharma', 'mapharma_open_data.json')
TEST_SLOT_FILE = Path('tests', 'fixtures', 'mapharma', 'slots.json')

def test_parse_slots():
    slots = dict()
    with open(TEST_SLOT_FILE, 'r', encoding='utf8') as f:
        slots = json.load(f)
    first_availability, slots_count = parse_slots(slots)
    assert first_availability == datetime(2021, 4, 19, 17, 15)
    assert slots_count == 72


def test_fetch_slots():
    def app(request: httpx.Request) -> httpx.Response:
        print(request.url)
        try:
            with open(Path('tests', 'fixtures', 'mapharma', 'slots.json'), encoding='utf8') as f:
                return httpx.Response(200, content=f.read())
        except IOError:
            return httpx.Response(404, content='')

    client = httpx.Client(transport=httpx.MockTransport(app))

    request = ScraperRequest(
        'https://mapharma.net/97200?c=60&l=1', '2021-04-14')
    first_availability = fetch_slots(request, client, opendata_file = TEST_OPEN_DATA_FILE)
    assert first_availability == "2021-04-19T17:15:00"
