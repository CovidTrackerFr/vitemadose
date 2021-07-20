from functools import reduce
from stats_generation import by_vaccine


def test_merge():
    data = {}
    by_vaccine.merge(data, ("Astra", 10))
    assert data == {"Astra": 10}

    by_vaccine.merge(data, ("Astra", 10))
    assert data == {"Astra": 20}

    by_vaccine.merge(data, ("Pfizer", 100))
    assert data == {"Astra": 20, "Pfizer": 100}


def test_flatten_vaccine_types():
    data = {
        "01": {
            "centres_disponibles": [
                # Dropped because it lists multiple vaccine types.
                {"appointment_schedules": [{"total": 10}], "vaccine_type": ["Pfizer", "Astra"]},
                {"appointment_schedules": [{"total": 10}], "vaccine_type": ["Pfizer"]},
            ],
            "centres_indisponibles": [
                {"vaccine_type": ["Pfizer"]},
                {"vaccine_type": ["Astra"]},
            ],
        },
        "02": {
            "centres_disponibles": [
                {"appointment_schedules": [{"total": 10}], "vaccine_type": ["Pfizer"]},
                {"appointment_schedules": [{"total": 100}], "vaccine_type": ["Astra"]},
            ],
            "centres_indisponibles": [],
        },
        "03": {
            "centres_disponibles": [],
            "centres_indisponibles": [],
        },
    }
    flattened = list(by_vaccine.flatten_vaccine_types_schedules(data))
    assert flattened == [("Pfizer", 10), ("Pfizer", 10), ("Astra", 100)]
    assert reduce(by_vaccine.merge, flattened, {}) == {"Astra": 100, "Pfizer": 20}
