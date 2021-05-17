import json
import logging
import httpx
import datetime as dt
from pathlib import Path

import scraper
from scraper.maiia.maiia import (
    parse_slots,
    get_next_slot_date,
    get_slots,
    get_reasons,
    get_first_availability,
    fetch_slots,
    centre_iterator,
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
    slots = get_slots(
        "5ffc744c68dedf073a5b87a2",
        "Premi%C3%A8re%20injection%20vaccin%20anti%20covid-19%20(%20%2B50%20ans%20avec%20comorbidit%C3%A9)",
        "2021-04-16T00:00:00+00:00",
        "2021-06-30T00:00:00+00:00",
        limit=MAIIA_LIMIT,
        client=client,
    )
    result = parse_slots(slots)
    assert result.isoformat() == "2021-05-13T13:40:00+00:00"


def test_get_next_slots():
    next_slot_date = get_next_slot_date(
        "5ffc744c68dedf073a5b87a2",
        "Premi%C3%A8re%20injection%20vaccin%20anti%20Covid-19%20%28Pfizer-BioNTech%29",
        "2021-04-14T17:50:00.000Z",
        client=httpx.Client(transport=httpx.MockTransport(app)),
    )
    assert next_slot_date == "2021-05-26T12:55:00.000Z"


def test_get_slots():
    slots = get_slots(
        "5ffc744c68dedf073a5b87a2",
        "Premi%C3%A8re%20injection%20vaccin%20anti%20covid-19%20(%20%2B50%20ans%20avec%20comorbidit%C3%A9)",
        "2021-04-16T00:00:00+00:00",
        "2021-06-30T00:00:00+00:00",
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
    reasons = get_reasons("5ffc744c68dedf073a5b87a2", limit=MAIIA_LIMIT, client=client)

    fake_now = dt.datetime(2021, 4, 29, 18, 20)
    with mock_datetime_now(fake_now):
        first_availability, slots_count, appointment_schedules = get_first_availability(
            "5ffc744c68dedf073a5b87a2", "2021-04-29", reasons, client=client
        )
    assert appointment_schedules == [
        {"from": "2021-04-29T18:20:00+02:00", "name": "chronodose", "to": "2021-04-30T18:19:59+02:00", "total": 0},
        {"from": "2021-04-29T00:00:00+02:00", "name": "1_days", "to": "2021-04-29T23:59:59+02:00", "total": 0},
        {"from": "2021-04-29T00:00:00+02:00", "name": "2_days", "to": "2021-04-30T23:59:59+02:00", "total": 0},
        {"from": "2021-04-29T00:00:00+02:00", "name": "7_days", "to": "2021-05-05T23:59:59+02:00", "total": 0},
        {"from": "2021-04-29T00:00:00+02:00", "name": "28_days", "to": "2021-05-26T23:59:59+02:00", "total": 6570},
        {"from": "2021-04-29T00:00:00+02:00", "name": "49_days", "to": "2021-06-16T23:59:59+02:00", "total": 7980},
    ]
    assert slots_count == 7980
    assert first_availability.isoformat() == "2021-05-13T13:40:00+00:00"


def test_fetch_slots():

    # Oops I forgot centerid
    request = ScraperRequest(
        "https://www.maiia.com/centre-de-vaccination/42400-saint-chamond/centre-de-vaccination-covid---hopital-du-gier-",
        "2021-04-16",
    )
    first_availability = fetch_slots(request, client=client)
    assert first_availability == None

    request = ScraperRequest(
        "https://www.maiia.com/centre-de-vaccination/42400-saint-chamond/centre-de-vaccination-covid---hopital-du-gier-?centerid=5ffc744c68dedf073a5b87a2",
        "2021-04-16",
    )
    first_availability = fetch_slots(request, client=client)
    assert first_availability == "2021-05-13T13:40:00+00:00"


def test_centre_iterator():
    centres = []
    for centre in centre_iterator(overwrite_centers_file=False):
        centres.append(centre)
    assert len(centres) > 0


def test_maiia_center_scrap():
    url = "/api/pat-public/hcd"

    def app_mock(request: httpx.Request) -> httpx.Response:

        if request.url.path == url and "pharmacie" in request.url.query.decode("utf-8"):
            return httpx.Response(200, json=json.loads(Path("tests/fixtures/maiia/scrap-center.json").read_text()))
        if request.url.path == url and "centre-de-vaccination" in request.url.query.decode("utf-8"):
            return httpx.Response(200, json={"total": 0, "items": []})
        return httpx.Response(403)

    client = httpx.Client(transport=httpx.MockTransport(app_mock))
    centers = maiia_scrap(client, save=False)

    assert centers == json.loads(Path("tests/fixtures/maiia/scrap-center-result.json").read_text())
