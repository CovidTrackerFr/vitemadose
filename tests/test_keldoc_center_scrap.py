import httpx

from scraper.centerscraper.keldoc_center_scrap import parse_keldoc_resource_url, get_cabinets, KeldocCenterScraper
from tests.test_keldoc import get_test_data

TEST_CENTERS = [
    {
        "item": {
            "url": "/centre-de-vaccination/62800-lievin/centre-de-vaccination-lievin-pays-dartois?centerid=5f92930176af0c5443ff0b63"
        },
        "result": "https://booking.keldoc.com/api/patients/v2/searches/resource?type=centre-de-vaccination&location=62800-lievin&slug=centre-de-vaccination-lievin-pays-dartois?centerid=5f92930176af0c5443ff0b63",
    },
    {
        "item": {
            "url": "/centre-de-vaccination/72300-sable-sur-sarthe/centre-de-vaccination---msp-du-pays-sabolien?centerid=5fc8a456310f92465037b285"
        },
        "result": "https://booking.keldoc.com/api/patients/v2/searches/resource?type=centre-de-vaccination&location=72300-sable-sur-sarthe&slug=centre-de-vaccination---msp-du-pays-sabolien?centerid=5fc8a456310f92465037b285",
    },
    {
        "item": {
            "url": "/centre-de-vaccination/02120-guise/centre-de-vaccination---msp-de-guise?centerid=5ffc21a0fabad2432c9bd0df"
        },
        "result": "https://booking.keldoc.com/api/patients/v2/searches/resource?type=centre-de-vaccination&location=02120-guise&slug=centre-de-vaccination---msp-de-guise?centerid=5ffc21a0fabad2432c9bd0df",
    },
]

API_MOCKS = {
    "/api/patients/v2/searches/resource": "resource-ain",
    "/api/patients/v2/searches/geo_location": "department-ain",
    "/api/patients/v2/clinics/17136/specialties/144/cabinets/17136/motive_categories": "motives-ain",
}


def test_keldoc_center_scraper():
    def app(request: httpx.Request) -> httpx.Response:
        if request.url.path in API_MOCKS:
            return httpx.Response(200, json=get_test_data(API_MOCKS[request.url.path]))
        return httpx.Response(200, json={})

    client = httpx.Client(transport=httpx.MockTransport(app))
    scraper = KeldocCenterScraper(session=client)
    result = scraper.run_departement_scrap("ain")
    assert result == get_test_data("result-ain")


def test_parse_keldoc_resource_url():
    for test_center in TEST_CENTERS:
        assert parse_keldoc_resource_url(test_center["item"]) == test_center["result"]


def test_get_cabinets():
    assert get_cabinets({"cabinet": {"id": 1}}) == [{"id": 1}]
    assert get_cabinets({"cabinets": [{"id": 1}]}) == [{"id": 1}]
    assert get_cabinets({}) == []


def test_keldoc_requests():
    # Timeout test
    def app_timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException(message="Timeout", request=request)

    client = httpx.Client(transport=httpx.MockTransport(app_timeout))
    scraper = KeldocCenterScraper(session=client)
    assert not scraper.send_keldoc_request("https://keldoc.com")

    # Status test
    def app_status(request: httpx.Request) -> httpx.Response:
        res = httpx.Response(403, json={})
        raise httpx.HTTPStatusError(message="status error", request=request, response=res)

    client = httpx.Client(transport=httpx.MockTransport(app_status))
    scraper = KeldocCenterScraper(session=client)
    assert not scraper.send_keldoc_request("https://keldoc.com")

    # Remote error test
    def app_remote_error(request: httpx.Request) -> httpx.Response:
        res = httpx.Response(403, json={})
        raise httpx.RemoteProtocolError(message="status error", request=request)

    client = httpx.Client(transport=httpx.MockTransport(app_remote_error))
    scraper = KeldocCenterScraper(session=client)
    assert not scraper.send_keldoc_request("https://keldoc.com")
