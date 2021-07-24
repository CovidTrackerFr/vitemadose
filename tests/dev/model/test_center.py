import json
from pathlib import Path

from dev.model.department import Center, Schedule


path = Path("tests", "fixtures", "utils", "info_centres.json")

with open(path) as fixture:
    data = json.load(fixture)


def test_unavailable_center():
    center = Center(**data["01"]["centres_indisponibles"][0])
    assert center.department == "01"
    assert center.appointment_count == 0


def test_available_center():
    center = Center(**data["01"]["centres_disponibles"][0])
    assert center.department == "01"
    assert center.appointment_count == 35


def test_center_iteration():
    center = Center(**data["01"]["centres_disponibles"][0])
    i = 0
    for _ in center:
        i += 1
    assert i > 0
