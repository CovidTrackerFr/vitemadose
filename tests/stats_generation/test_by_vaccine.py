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
        "version": 1,
        "last_updated": "2021-07-19T23:02:28+02:00",
        "centres_disponibles": [
            {
                "departement": "75",
                "nom": "Pharmacie Bassereau",
                "url": "https://www.maiia.com/pharmacie/75017-paris/pharmacie-bassereau?centerid=604b186665d8f5139d42dc21",
                "location": {"longitude": 2.317913, "latitude": 48.886224, "city": "Paris", "cp": "75017"},
                "metadata": {
                    "address": "70 Rue Legendre 75017 Paris",
                    "business_hours": {
                        "Lundi": "09:20-20:00",
                        "Mardi": "09:20-20:00",
                        "Mercredi": "09:20-20:00",
                        "Jeudi": "09:20-20:00",
                        "Vendredi": "09:20-20:00",
                        "Samedi": "09:20-20:00",
                        "Dimanche": "09:20-20:00",
                    },
                },
                "prochain_rdv": "2021-07-20T07:00:00+00:00",
                "plateforme": "Maiia",
                "type": "drugstore",
                "appointment_count": 7,
                "internal_id": "maiia604b1866",
                "vaccine_type": ["Janssen"],
                "appointment_by_phone_only": False,
                "erreur": None,
                "last_scan_with_availabilities": None,
                "request_counts": None,
            },
            {
                "departement": "94",
                "nom": "Centre de vaccination - CHI de Villeneuve-Saint-Georges",
                "url": "https://www.maiia.com/centre-de-vaccination/94190-villeneuve-saint-georges/centre-de-vaccination---chi-de-villeneuve-saint-georges?centerid=6001704008fa3a60d6d1b0aa",
                "location": {
                    "longitude": 2.450239,
                    "latitude": 48.723306,
                    "city": "Villeneuve-Saint-Georges",
                    "cp": "94190",
                },
                "metadata": {
                    "address": "40 Allée de la Source 94190 Villeneuve-Saint-Georges",
                    "business_hours": {
                        "Lundi": "09:00-16:30",
                        "Mardi": "09:00-16:30",
                        "Mercredi": "09:00-16:30",
                        "Jeudi": "09:00-16:30",
                        "Vendredi": "09:00-16:30",
                        "Samedi": "09:00-16:30",
                        "Dimanche": "09:00-16:30",
                    },
                    "phone_number": "+33143862150",
                },
                "prochain_rdv": "2021-07-20T07:10:00+00:00",
                "plateforme": "Maiia",
                "type": "vaccination-center",
                "appointment_count": 650,
                "internal_id": "maiia60017040",
                "vaccine_type": ["Pfizer-BioNTech"],
                "appointment_by_phone_only": False,
                "erreur": None,
                "last_scan_with_availabilities": None,
                "request_counts": None,
            },
        ],
    }
    flattened = list(by_vaccine.flatten_vaccine_types_schedules(data))
    assert flattened == [("Janssen", 1), ("Pfizer-BioNTech", 1)]
    assert reduce(by_vaccine.merge, flattened, {}) == {"Janssen": 1, "Pfizer-BioNTech": 1}
