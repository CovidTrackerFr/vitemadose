import json
from scraper.pattern.center_info import CenterInfo, CenterLocation
import httpx

from pathlib import Path
from datetime import datetime, date
from pytz import timezone
from utils.vmd_utils import departementUtils, DummyQueue
from scraper.mapharma.mapharma import Mapharma, fetch_slots, campagne_to_centre
from scraper.pattern.scraper_request import ScraperRequest
from scraper.pattern.scraper_result import DRUG_STORE
from scraper.creneaux.creneau import Lieu

TEST_OPEN_DATA_FILE = Path("tests", "fixtures", "mapharma", "mapharma_open_data.json")
TEST_SLOT_FILE = Path("tests", "fixtures", "mapharma", "slots.json")


def test_count_appointements():

    mapharma = Mapharma()
    slots = dict()
    with open(TEST_SLOT_FILE, "r", encoding="utf8") as f:
        slots = json.load(f)
    start_date = timezone("Europe/Paris").localize(datetime(2021, 4, 1, 0, 0, 0))
    end_date = timezone("Europe/Paris").localize(datetime(2021, 4, 19, 23, 59, 59))
    assert mapharma.count_appointements(slots, start_date, end_date) == 1
    end_date = timezone("Europe/Paris").localize(datetime(2021, 5, 14, 23, 59, 59))
    assert mapharma.count_appointements(slots, start_date, end_date) == 72


def test_parse_slots():
    mapharma = Mapharma()
    request = ScraperRequest(url="https://mapharma.net/49100-3?c=259&l=0", start_date="2021-07-18")
    slots = dict()
    with open(TEST_SLOT_FILE, "r", encoding="utf8") as f:
        slots = json.load(f)
    slots["first_something"] = []
    first_availability, slots_count = mapharma.parse_slots(
        slots, start_date=date(2021, 4, 19), request=request, vaccine="Vaccine.JANSSEN"
    )
    assert first_availability == datetime(2021, 4, 19, 17, 15)
    assert slots_count == 72


def test_fetch_slots():
    def app(request: httpx.Request) -> httpx.Response:
        try:
            with open(Path("tests", "fixtures", "mapharma", "slots.json"), encoding="utf8") as f:
                return httpx.Response(200, content=f.read())
        except IOError:
            return httpx.Response(404, content="")

    client = httpx.Client(transport=httpx.MockTransport(app))

    center_info = CenterInfo(
        departement="49",
        nom="Pharmacie Grand Maine",
        url="https://mapharma.net/49100-3?c=257&l=0",
        location=CenterLocation(longitude=-0.595416, latitude=47.468377, city="ANGERS", cp="49100"),
        metadata={
            "address": "CENTRE CIAL GRAND MAINE RUE DU GRAND LAUNAY, 49100 ANGERS",
            "business_hours": {
                "lundi": "09:30 – 20:00",
                "mardi": "09:30 – 20:00",
                "mercredi": "09:30 – 20:00",
                "jeudi": "09:30 – 20:00",
                "vendredi": "09:30 – 20:00",
                "samedi": "09:30 – 20:00",
                "dimanche": "Fermé",
            },
        },
    )

    request = ScraperRequest(
        url="https://mapharma.net/97200?c=60&l=1", start_date="2021-04-14", center_info=center_info
    )
    first_availability = fetch_slots(request, creneau_q=DummyQueue(), client=client, opendata_file=TEST_OPEN_DATA_FILE)

    assert first_availability == "2021-04-19T17:15:00"

    # test campagne["total_libres"]: 0
    request = ScraperRequest("https://mapharma.net/88400?c=92&l=1", "2021-04-14", center_info=center_info)
    first_availability = fetch_slots(request, client=client, opendata_file=TEST_OPEN_DATA_FILE)
    assert first_availability == None


def test_campaign_to_center():
    pharma = {
        "code_postal": "35000",
        "nom": "Pharmacie du centre",
        "longitude": 1.13,
        "latitude": 42.84,
        "ville": "Rennes",
        "adresse": "1 Rue de la Gare",
        "horaires": "lundi: 09:00-12:00\nmardi: 09:00-11:00",
        "telephone": "06 06 06 06 06",
    }
    campaign = {"url": "https://mapharma.fr/pharmacie-du-centre"}
    center = campagne_to_centre(pharma, campaign)
    assert center == {
        "nom": "Pharmacie du centre",
        "type": DRUG_STORE,
        "long_coor1": 1.13,
        "lat_coor1": 42.84,
        "com_nom": "Rennes",
        "com_cp": "35000",
        "address": "1 Rue de la Gare, 35000 Rennes",
        "business_hours": {"lundi": "09:00-12:00", "mardi": "09:00-11:00"},
        "phone_number": "06 06 06 06 06",
        "rdv_site_web": "https://mapharma.fr/pharmacie-du-centre",
        "com_insee": "35238",
        "gid": "6369652d64752d63656e747",
    }


def test_mapharma_fetch_slots():
    def app(request: httpx.Request) -> httpx.Response:
        try:
            with open(Path("tests", "fixtures", "mapharma", "slots.json"), encoding="utf8") as f:
                return httpx.Response(200, content=f.read())
        except IOError:
            return httpx.Response(404, content="")

    client = httpx.Client(transport=httpx.MockTransport(app))
    request = ScraperRequest("https://mapharma.net/97200?c=60&l=1", "2021-04-14")
