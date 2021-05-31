from scraper.keldoc.keldoc_center_scrap import parse_keldoc_resource_url, get_cabinets

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


def test_parse_keldoc_resource_url():
    for test_center in TEST_CENTERS:
        assert parse_keldoc_resource_url(test_center["item"]) == test_center["result"]


def test_get_cabinets():
    assert get_cabinets({"cabinet": {"id": 1}}) == [{"id": 1}]
    assert get_cabinets({"cabinets": [{"id": 1}]}) == [{"id": 1}]
    assert get_cabinets({}) == []
