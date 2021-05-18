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


def test_flatten_cells():
    """
    | Name    | URL                | Irrelevant  |
    | ------- | ------------------ | ----------- |
    | Paris   | https://google.com | much wow    |
    | Cayenne | https://google.com | to the moon |
    """
    entries = expected_response["feed"]["entry"]
    column_names = {1: "Name", 2: "URL"}

    flattened = sheets._flatten_cells(entries, column_names=column_names, has_header=True)
    assert flattened == [
        {"row": "2", "col": "1", "inputValue": "Paris"},
        {"row": "2", "col": "2", "inputValue": "https://google.com"},
        {"row": "3", "col": "1", "inputValue": "Cayenne"},
        {"row": "3", "col": "2", "inputValue": "https://google.com"},
    ]

    flattened = sheets._flatten_cells(entries, column_names=column_names, has_header=False)
    assert flattened == [
        {"row": "1", "col": "1", "inputValue": "Name"},
        {"row": "1", "col": "2", "inputValue": "URL"},
        {"row": "2", "col": "1", "inputValue": "Paris"},
        {"row": "2", "col": "2", "inputValue": "https://google.com"},
        {"row": "3", "col": "1", "inputValue": "Cayenne"},
        {"row": "3", "col": "2", "inputValue": "https://google.com"},
    ]


def test_assemble():
    flattened = [
        {"row": "2", "col": "1", "inputValue": "Paris"},
        {"row": "2", "col": "2", "inputValue": "https://google.com"},
        {"row": "3", "col": "1", "inputValue": "Cayenne"},
        {"row": "3", "col": "2", "inputValue": "https://google.com"},
    ]
    column_names = {1: "Name", 2: "URL"}
    assembled = sheets._assemble(flattened, column_names)
    assert assembled == {
        "Name": ["Paris", "Cayenne"],
        "URL": ["https://google.com", "https://google.com"],
    }


def test_parse():
    parsed = sheets._parse(expected_response["feed"]["entry"], column_names={1: "Name", 2: "URL"}, has_header=True)
    expected = {
        "Name": ["Paris", "Cayenne"],
        "URL": ["https://google.com", "https://google.com"],
    }
    assert parsed == expected
