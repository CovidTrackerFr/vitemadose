import json
import logging
from scraper.pattern.center_info import CenterInfo
from utils.vmd_utils import DummyQueue
import httpx
import datetime as dt
from pathlib import Path
from scraper.pattern.center_location import CenterLocation
import scraper
from scraper.maiia.maiia import (
    MaiiaSlots,
    get_reasons,
    fetch_slots,
    center_iterator,
    MAIIA_LIMIT,
)
from scraper.maiia.maiia_center_scrap import maiia_scrap
from scraper.pattern.scraper_request import ScraperRequest
from .utils import mock_datetime_now


logger = logging.getLogger("scraper")


def app(request: httpx.Request) -> httpx.Response:
    try:
        slug = request.url.path.split("/")[-1]
        endpoint = slug.split("?")[0]
        path = Path("tests", "fixtures", "maiia", f"{endpoint}.json")
        with open(path, encoding="utf8") as f:
            return httpx.Response(200, content=f.read())
    except IOError:
        return httpx.Response(404, content="")


client = httpx.Client(transport=httpx.MockTransport(app))

scraper.maiia.maiia.DEFAULT_CLIENT = client


def test_parse_slots():
    request = ScraperRequest(
        url="https://www.maiia.com/centre-de-vaccination/93230-romainville/centre-de-vaccination-de-romainville?centerId=6000447d018ecf0e3f5715f2",
        start_date="2021-03-26",
    )
    slots_test = MaiiaSlots(creneau_q=DummyQueue, client=None)
    availabilities = slots_test.get_slots(
        center_id="5ffc744c68dedf073a5b87a2",
        consultation_reason_name="Premi%C3%A8re%20injection%20vaccin%20anti%20covid-19%20(%20%2B50%20ans%20avec%20comorbidit%C3%A9)",
        start_date="2021-04-16T00:00:00+00:00",
        end_date="2021-06-30T00:00:00+00:00",
        limit=MAIIA_LIMIT,
        client=client,
    )
    result = slots_test.parse_slots(availabilities, request)
    assert result.isoformat() == "2021-05-13T13:40:00+00:00"


def test_get_next_slots():
    next_slot_date = MaiiaSlots(creneau_q=DummyQueue, client=None)

    next_date = next_slot_date.get_next_slot_date(
        center_id="5ffc744c68dedf073a5b87a2",
        consultation_reason_name="Premi%C3%A8re%20injection%20vaccin%20anti%20Covid-19%20%28Pfizer-BioNTech%29",
        start_date="2021-04-14T17:50:00.000Z",
        client=httpx.Client(transport=httpx.MockTransport(app)),
    )
    assert next_date == "2021-05-26T12:55:00.000Z"


def test_get_slots():
    slots_req = MaiiaSlots(creneau_q=DummyQueue, client=None)

    slots = slots_req.get_slots(
        center_id="5ffc744c68dedf073a5b87a2",
        consultation_reason_name="Premi%C3%A8re%20injection%20vaccin%20anti%20covid-19%20(%20%2B50%20ans%20avec%20comorbidit%C3%A9)",
        start_date="2021-04-16T00:00:00+00:00",
        end_date="2021-06-30T00:00:00+00:00",
        limit=MAIIA_LIMIT,
        client=client,
    )
    assert len(slots) == 798
    assert slots[42]["startDateTime"] == "2021-05-14T07:00:00.000Z"


def test_get_reasons():
    reasons = get_reasons("5ffc744c68dedf073a5b87a2", limit=MAIIA_LIMIT, client=client)
    assert len(reasons) == 10
    assert reasons[5]["injectionType"] == "FIRST"


def test_get_first_availability():

    request = ScraperRequest(
        url="https://www.maiia.com/centre-de-vaccination/42400-saint-chamond/centre-de-vaccination-covid---hopital-du-gier-?centerid=5ffc744c68dedf073a5b87a2",
        start_date="2021-07-17",
        center_info=CenterInfo(
            departement="42",
            nom="Centre de vaccination COVID - Hôpital du Gier ",
            url="https://www.maiia.com/centre-de-vaccination/42400-saint-chamond/centre-de-vaccination-covid---hopital-du-gier-?centerid=5ffc744c68dedf073a5b87a2",
            location=CenterLocation(longitude=4.50184989506, latitude=45.4698319517, city="Saint-Chamond", cp="42400"),
            metadata={
                "address": "19 rue victor hugo 42400 Saint-Chamond",
                "business_hours": {
                    "Lundi": "08:15-17:15",
                    "Mardi": "08:15-17:15",
                    "Mercredi": "08:15-17:15",
                    "Jeudi": "08:15-17:15",
                    "Vendredi": "08:15-17:15",
                    "Samedi": "08:15-17:15",
                    "Dimanche": "08:15-17:15",
                },
            },
            type="vaccination-center",
            internal_id="5ffc744c",
        ),
    )
    reasons = get_reasons("5ffc744c68dedf073a5b87a2", limit=MAIIA_LIMIT, client=client)
    instance = MaiiaSlots(creneau_q=DummyQueue, client=None)
    fake_now = dt.datetime(2021, 4, 29, 18, 20)
    with mock_datetime_now(fake_now):
        first_availability, slots_count = instance.get_first_availability(
            "5ffc744c68dedf073a5b87a2", "2021-04-29", reasons, client=client, request=request
        )

    assert slots_count == 7980
    assert first_availability.isoformat() == "2021-05-13T13:40:00+00:00"


def test_fetch_slots():

    # Oops I forgot centerid
    request = ScraperRequest(
        url="https://www.maiia.com/centre-de-vaccination/42400-saint-chamond/centre-de-vaccination-covid---hopital-du-gier-",
        start_date="2021-04-16",
        center_info=CenterInfo(
            departement="42",
            nom="Centre de vaccination COVID - Hôpital du Gier ",
            url="https://www.maiia.com/centre-de-vaccination/42400-saint-chamond/centre-de-vaccination-covid---hopital-du-gier-?centerid=5ffc744c68dedf073a5b87a2",
            location=CenterLocation(longitude=4.50184989506, latitude=45.4698319517, city="Saint-Chamond", cp="42400"),
            metadata={
                "address": "19 rue victor hugo 42400 Saint-Chamond",
                "business_hours": {
                    "Lundi": "08:15-17:15",
                    "Mardi": "08:15-17:15",
                    "Mercredi": "08:15-17:15",
                    "Jeudi": "08:15-17:15",
                    "Vendredi": "08:15-17:15",
                    "Samedi": "08:15-17:15",
                    "Dimanche": "08:15-17:15",
                },
            },
            type="vaccination-center",
            internal_id="5ffc744c",
        ),
    )
    first_availability = fetch_slots(request, client=client)
    assert first_availability == None

    request = ScraperRequest(
        url="https://www.maiia.com/centre-de-vaccination/42400-saint-chamond/centre-de-vaccination-covid---hopital-du-gier-?centerid=5ffc744c68dedf073a5b87a2",
        start_date="2021-04-16",
        center_info=CenterInfo(
            departement="42",
            nom="Centre de vaccination COVID - Hôpital du Gier ",
            url="https://www.maiia.com/centre-de-vaccination/42400-saint-chamond/centre-de-vaccination-covid---hopital-du-gier-?centerid=5ffc744c68dedf073a5b87a2",
            location=CenterLocation(longitude=4.50184989506, latitude=45.4698319517, city="Saint-Chamond", cp="42400"),
            metadata={
                "address": "19 rue victor hugo 42400 Saint-Chamond",
                "business_hours": {
                    "Lundi": "08:15-17:15",
                    "Mardi": "08:15-17:15",
                    "Mercredi": "08:15-17:15",
                    "Jeudi": "08:15-17:15",
                    "Vendredi": "08:15-17:15",
                    "Samedi": "08:15-17:15",
                    "Dimanche": "08:15-17:15",
                },
            },
            type="vaccination-center",
            internal_id="5ffc744c",
        ),
    )
    print(request.center_info)

    first_availability = fetch_slots(request, client=client)
    assert first_availability == "2021-05-13T13:40:00+00:00"


def test_center_iterator():
    centres = []
    for centre in center_iterator():
        centres.append(centre)
    assert len(centres) > 0

