import json
from pathlib import Path

from dev.model.department import Center, Schedule


path = Path("tests", "fixtures", "utils", "info_centres.json")

with open(path) as fixture:
    data = json.load(fixture)


def test_unavailable_center():
    center = Center(**data["01"]["centres_indisponibles"][0])
    assert center.department == "01"
    assert not center.appointment_schedules
    assert not center.is_available


def test_available_center():
    center = Center(**data["01"]["centres_disponibles"][0])
    assert center.department == "01"
    assert center.appointment_schedules
    assert len(center.appointment_schedules) == 6
    assert center.appointment_schedules[0] == Schedule(
        **{
            "name": "chronodose",
            "from": "2021-05-10T00:00:00+02:00",
            "to": "2021-05-11T23:59:59+02:00",
            "total": 0,
        }
    )
    assert center.is_available


def test_center_iteration():
    center = Center(**data["01"]["centres_disponibles"][0])
    i = 0
    for _ in center:
        i += 1
    assert i > 0
