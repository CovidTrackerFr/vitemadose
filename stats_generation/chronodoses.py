"""Generates stats about «chronodoses».

Issue: https://github.com/CovidTrackerFr/vitemadose/issues/383

Usage:

```shell
python3 -m stats_generation.chronodoses \
    --input="some/file.json" # Optional (should follow the same structure as data/output/info_centres.json.)\
    --output="put/it/here.json" # Optional \
    --national # Optional: Whether or not to add a summary national statistic.
```

"""
import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List


_default_input = Path("data", "output", "info_centres.json")
_default_output = Path("data", "output", "stats_chronodoses.json")


def count_departments_chronodoses(data: dict) -> Dict[str, int]:
    return {
        department_id: _department_chronodoses(department_data)
        for department_id, department_data in data.items()
    }


def _national_doses(per_department: Dict[str, int]) -> dict:
    return sum(per_department.values())


def _department_chronodoses(department_data: dict) -> int:
    """Sums the available chronodoses for a given department.

    ```json
    {
        "01": {
            ...,
            "centres_disponibles": {
                ...,
                "appointment_schedules": [
                    {
                        "name": "chronodose",
                        "total": 0
                    },
                    {...}
                ]
            }
        }
    }
    ```
    """
    if "centres_disponibles" not in department_data:
        return 0
    centers = department_data["centres_disponibles"]

    return sum(
        schedule["total"]
        for center in centers
        for schedule in center["appointment_schedules"]
        if schedule["name"] == "chronodose"
    )


def parse_args(args: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        default=_default_input,
        type=Path,
        help="File with the statistics per department. Should follow the same structure as info_centres.json.",
    )
    parser.add_argument(
        "--output",
        default=_default_output,
        type=Path,
        help="Where to put the resulting statistics.",
    )
    parser.add_argument(
        "--national",
        action="store_true",
        default=False,
    )
    return parser.parse_args(args)


def main(argv):
    args = parse_args(argv[1:])
    with open(args.input) as f:
        doses = {"departments": count_departments_chronodoses(json.load(f))}
    if args.national:
        doses.update({"national": _national_doses(doses["departments"])})
    with open(args.output, "w") as f:
        json.dump(doses, f)


if __name__ == "__main__":
    main(sys.argv)
