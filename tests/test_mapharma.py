import json
import httpx
from bs4 import BeautifulSoup
from pathlib import Path

from scraper.mapharma.mapharma import (
    get_name,
    get_address,
    get_reasons,
    get_profile,
    get_profiles)



def get_soup():
    with open(Path("tests", "fixtures", "mapharma", "49100-5.html"), encoding='utf8') as html_file:
        soup = BeautifulSoup(html_file.read(), 'html.parser')
        return soup


def test_get_name():
    soup = get_soup()
    assert get_name(soup) == 'Pharmacie De La Gare'


def test_get_address():
    soup = get_soup()
    with open(Path("tests", "fixtures", "mapharma", "49100-5.html"), encoding='utf8') as html_file:
        soup = BeautifulSoup(html_file.read(), 'html.parser')
    assert get_address(soup) == '5 ESPLANADE DE LA GARE 49100 ANGERS'


def test_get_reasons():
    soup = get_soup()
    with open(Path("tests", "fixtures", "mapharma", "49100-5.html"), encoding='utf8') as html_file:
        soup = BeautifulSoup(html_file.read(), 'html.parser')
    assert get_reasons(soup) == [{"campagneId": "201", "optionId": "1",
                                  "optionName": "Vaccination COVID - 1\u00e8re injection (15 min.)"}]


def test_get_profile():
    centre_id = '49100-5'
    profileJson = json.load(open(Path('tests', 'fixtures', 'mapharma', f'{centre_id}.json'), encoding='utf8'))

    def app(request: httpx.Request) -> httpx.Response:
        slug = request.url.path.rsplit('/', 1)[-1]
        try:
            with open(Path('tests', 'fixtures', 'mapharma', f'{slug}.html'), encoding='utf8') as html_file:
                return httpx.Response(200, content=html_file.read())
        except IOError:
            return httpx.Response(404, content='')

    client = httpx.Client(transport=httpx.MockTransport(app))

    profile = get_profile(f'https://mapharma.net/{centre_id}', client=client)
    print(profile)
    assert profile == profileJson


def test_get_profiles():
    profilesJson = json.load(open(Path('tests', 'fixtures', 'mapharma', '49100.json'), encoding='utf8'))

    def app(request: httpx.Request) -> httpx.Response:
        slug = request.url.path.rsplit('/', 1)[-1]
        try:
            with open(Path('tests', 'fixtures', 'mapharma', f'{slug}.html'), encoding='utf8') as html_file:
                return httpx.Response(200, content=html_file.read())
        except IOError:
            return httpx.Response(404, content='')

    client = httpx.Client(transport=httpx.MockTransport(app))

    profiles = get_profiles("49100", client=client)
    assert profiles == profilesJson
