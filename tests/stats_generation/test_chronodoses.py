from pathlib import Path

from stats_generation import chronodoses


def test_departments_chronodoses():
    data = {
        "key": "value",
    }
    assert chronodoses._department_chronodoses(data) == 0

    data = {
        "centres_disponibles": [],
    }
    assert chronodoses._department_chronodoses(data) == 0

    data = {
        "centres_disponibles": [
            {"appointment_schedules": []},
            {
                "appointment_schedules": [
                    {"name": "chronodose", "total": 0},
                    {"name": "1_days", "total": 10},
                ]
            },
        ],
    }
    assert chronodoses._department_chronodoses(data) == 0

    data = {
        "centres_disponibles": [
            {"appointment_schedules": []},
            {
                "appointment_schedules": [
                    {"name": "1_days", "total": 10},
                ]
            },
        ],
    }
    assert chronodoses._department_chronodoses(data) == 0

    data = {
        "centres_disponibles": [
            {"appointment_schedules": []},
            {
                "appointment_schedules": [
                    {"name": "chronodose", "total": 1},
                    {"name": "1_days", "total": 10},
                ]
            },
        ],
    }
    assert chronodoses._department_chronodoses(data) == 1


def test_parse_args():
    args = []
    flags = chronodoses.parse_args(args)
    assert not flags.national
    assert flags.input == chronodoses._default_input
    assert flags.output == chronodoses._default_output

    args = ["--input=some_path"]
    flags = chronodoses.parse_args(args)
    assert not flags.national
    assert flags.input == Path("some_path")
    assert flags.output == chronodoses._default_output

    args = ["--output=some_path"]
    flags = chronodoses.parse_args(args)
    assert not flags.national
    assert flags.input == chronodoses._default_input
    assert flags.output == Path("some_path")

    args = ["--national"]
    flags = chronodoses.parse_args(args)
    assert flags.national
    assert flags.input == chronodoses._default_input
    assert flags.output == chronodoses._default_output
