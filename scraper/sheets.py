"""Reads data from a Google Sheet.

The API is a bit funky, as the results look like this:

```json
{
    ...,
    "feed": {
        ...,
        "gs$rowCount": {"$t": '1000'},
        "gs$colCount": {"$t": '26'},
        "entry": [
            {
                ...,
                "gs$cell": {"row": "1", "col": "1", "inputValue": "ID", "$t$: "ID"} // Our cell!
            }
        ]
    }
}
```

So, we are provided with a flattened view of our data, and we need to morph it into
what we want, i.e. a list of dictionnaries.
"""

from typing import Dict, List
import requests

json_endpoint = "https://spreadsheets.google.com/feeds/cells/{SHEET_ID}/{PAGE_NUMBER}/public/full?alt=json"


def _fetch(sheet_id: str, page_number: int) -> dict:
    response = requests.get(json_endpoint.format(SHEET_ID=sheet_id, PAGE_NUMBER=page_number))
    response.raise_for_status()
    return response.json()


def _flatten_cells(data: dict, column_names: Dict[int, str], has_header: bool) -> List[dict]:
    return [
        cell
        for entry in data
        if int((cell := entry["gs$cell"])["col"]) in column_names and (int(cell["row"]) > 1 if has_header else True)
    ]


def _assemble(cells: List[str], column_names: Dict[int, str]):
    return {
        column_name: [cell["inputValue"] for cell in cells if int(cell["col"]) == column_id]
        for column_id, column_name in column_names.items()
    }


def _parse(data: dict, column_names: Dict[int, str], has_header: bool) -> List[dict]:
    cells = _flatten_cells(data, column_names, has_header)
    return _assemble(cells, column_names)


def load(sheet_id: str, page_number: int, column_names: Dict[int, str], has_header=True) -> List[dict]:
    data = _fetch(sheet_id, page_number)["feed"]["entry"]
    return _parse(data, column_names, has_header)
