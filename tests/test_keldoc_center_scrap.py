import httpx
from scraper.keldoc.keldoc_center_scrap import parse_keldoc_resource_url, KeldocCenterScraper
from tests.test_keldoc import get_test_data

TEST_CENTERS = [
    {
        "item": {
            "url": "https://keldoc.com/centre-de-vaccination/62800-lievin/centre-de-vaccination-lievin-pays-dartois"
        },
        "result": "https://booking.keldoc.com/api/patients/v2/searches/resource?type=centre-de-vaccination&location=62800-lievin&slug=centre-de-vaccination-lievin-pays-dartois",
    },
    {
        "item": {
            "url": "https://www.keldoc.com/centre-hospitalier/melun-cedex-77011/groupe-hospitalier-sud-ile-de-france/centre-de-vaccination-ghsif-site-de-brie-comte-robert"
        },
        "result": "https://booking.keldoc.com/api/patients/v2/searches/resource?type=centre-hospitalier&location=melun-cedex-77011&slug=groupe-hospitalier-sud-ile-de-france&cabinet=centre-de-vaccination-ghsif-site-de-brie-comte-robert",
    },
]

API_MOCKS = {
    "/api/patients/v2/searches/resource": "resource-ain",
    "/api/patients/v2/searches/geo_location": "department-ain",
    "/api/patients/v2/clinics/2737/specialties/144/cabinets/17136/motive_categories": "motives-ain",
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
        assert parse_keldoc_resource_url(test_center["item"]["url"]) == test_center["result"]


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
