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

from functools import reduce
from typing import Dict, List
import requests

json_endpoint = "https://spreadsheets.google.com/feeds/cells/{SHEET_ID}/{PAGE_NUMBER}/public/full?alt=json"


def _fetch(sheet_id: str, page_number: int) -> dict:
    response = requests.get(json_endpoint.format(SHEET_ID=sheet_id, PAGE_NUMBER=page_number))
    response.raise_for_status()
    return response.json()


def _group_rows(accumulator: dict, new: dict) -> dict:
    if (row := new["row"]) in accumulator:
        accumulator[row].append(new)
    else:
        accumulator[row] = [new]
    return accumulator


def _parse_row(row: Dict[str, List[dict]], column_names: Dict[int, str]) -> dict:
    return {
        column_name: cell["inputValue"]
        for cell in row
        for column_id, column_name in column_names.items()
        if int(cell["col"]) == column_id
    }


def _parse(entries: list, column_names: Dict[int, str], has_header: bool) -> list:
    cells = (_["gs$cell"] for _ in entries)
    by_row = dict(reduce(_group_rows, cells, {}))
    rows = list(by_row.values())
    return [_parse_row(row, column_names) for row in (rows if not has_header else rows[1:])]


def load(sheet_id: str, page_number: int, column_names: Dict[int, str], has_header=True) -> List[dict]:
    entries = _fetch(sheet_id, page_number)["feed"]["entry"]
    return _parse(entries, column_names, has_header)
