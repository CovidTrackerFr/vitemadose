from functools import reduce

from scraper import sheets

expected_response = {
    "feed": {
        "entry": [
            {"gs$cell": {"row": "1", "col": "1", "inputValue": "Name"}},
            {"gs$cell": {"row": "1", "col": "2", "inputValue": "URL"}},
            {"gs$cell": {"row": "1", "col": "3", "inputValue": "Irrelevant"}},
            {"gs$cell": {"row": "2", "col": "1", "inputValue": "Paris"}},
            {"gs$cell": {"row": "2", "col": "2", "inputValue": "https://google.com"}},
            {"gs$cell": {"row": "2", "col": "3", "inputValue": "much wow"}},
            {"gs$cell": {"row": "3", "col": "1", "inputValue": "Cayenne"}},
            {"gs$cell": {"row": "3", "col": "2", "inputValue": "https://google.com"}},
            {"gs$cell": {"row": "3", "col": "3", "inputValue": "to the moon"}},
        ],
    }
}


def test_group_rows():
    cells = (_["gs$cell"] for _ in expected_response["feed"]["entry"])
    grouped = dict(reduce(sheets._group_rows, cells, {}))
    print(grouped)
    assert grouped == {
        "1": [
            {"row": "1", "col": "1", "inputValue": "Name"},
            {"row": "1", "col": "2", "inputValue": "URL"},
            {"row": "1", "col": "3", "inputValue": "Irrelevant"},
        ],
        "2": [
            {"row": "2", "col": "1", "inputValue": "Paris"},
            {"row": "2", "col": "2", "inputValue": "https://google.com"},
            {"row": "2", "col": "3", "inputValue": "much wow"},
        ],
        "3": [
            {"row": "3", "col": "1", "inputValue": "Cayenne"},
            {"row": "3", "col": "2", "inputValue": "https://google.com"},
            {"row": "3", "col": "3", "inputValue": "to the moon"},
        ],
    }


def test_parse_row():
    to_parse = [
        {"row": "3", "col": "1", "inputValue": "Cayenne"},
        {"row": "3", "col": "2", "inputValue": "https://google.com"},
        {"row": "3", "col": "3", "inputValue": "to the moon"},
    ]
    column_names = {1: "Name", 2: "URL"}
    expected = {"Name": "Cayenne", "URL": "https://google.com"}
    assert sheets._parse_row(to_parse, column_names) == expected


def test_parse():
    parsed = sheets._parse(expected_response["feed"]["entry"], column_names={1: "Name", 2: "URL"}, has_header=True)
    expected = [
        {"Name": "Paris", "URL": "https://google.com"},
        {"Name": "Cayenne", "URL": "https://google.com"},
    ]
    assert parsed == expected
