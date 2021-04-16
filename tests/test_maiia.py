import json

import httpx

from pathlib import Path

import scraper
from scraper.maiia.maiia import (
    fetch_slots,
    get_slots,
    parse_slots,
    centre_iterator,
    MAIIA_LIMIT
)
from scraper.pattern.scraper_request import ScraperRequest

def app(request: httpx.Request) -> httpx.Response:
    try:
        slug = request.url.path.split('/')[-1]
        endpoint = slug.split('?')[0]
        path = Path('tests', 'fixtures', 'maiia', f'{endpoint}.json')
        with open(path, encoding='utf8') as f:
            return httpx.Response(200, content=f.read())
    except IOError:
        return httpx.Response(404, content='')


client = httpx.Client(transport=httpx.MockTransport(app))


def test_parse_slots():
    slots = get_slots('5ffc744c68dedf073a5b87a2', 'Première injection vaccin anti covid-19 ( +50 ans avec comorbidité)', '2021-04-16T00:00:00+00:00', '2021-06-30T00:00:00+00:00', limit=MAIIA_LIMIT, client=client)
    result = parse_slots(slots)
    assert result.isoformat() == '2021-05-13T13:40:00+00:00'


def test_fetch_slots():

    # Oops I forgot centerid
    request = ScraperRequest(
        'https://www.maiia.com/centre-de-vaccination/42400-saint-chamond/centre-de-vaccination-covid---hopital-du-gier-', '2021-04-16')
    first_availability = fetch_slots(request, client=client)
    assert first_availability == None

    request = ScraperRequest(
        'https://www.maiia.com/centre-de-vaccination/42400-saint-chamond/centre-de-vaccination-covid---hopital-du-gier-?centerid=5ffc744c68dedf073a5b87a2', '2021-04-16')
    first_availability = fetch_slots(request, client=client)
    assert first_availability == "2021-05-13T13:40:00+00:00"


def test_centre_iterator():
    centres = []
    for centre in centre_iterator():
        centres.append(centre)
    assert len(centres) > 0