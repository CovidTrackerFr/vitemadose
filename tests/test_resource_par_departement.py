import dateutil
from dateutil.tz import gettz
from scraper.creneaux.creneau import Creneau, Plateforme, Lieu, PasDeCreneau
from scraper.export.resource_centres import ResourceParDepartement
from datetime import datetime
from scraper.pattern.vaccine import Vaccine
from scraper.pattern.center_location import CenterLocation

expected_now = dateutil.parser.parse("2021-05-26T21:34:00.000Z")


def now(tz=None):
    return expected_now


def test_resource_par_departement_from_empty():
    # Given
    departement = "07"
    creneaux = []
    # When
    actual = next(ResourceParDepartement.from_creneaux(creneaux, departement=departement, now=now))
    # Then
    assert actual.asdict() == {
        "version": 1,
        "last_updated": expected_now.isoformat(),
        "centres_disponibles": [],
        "centres_indisponibles": [],
    }


def test_resource_par_departement__from_other_departement():
    # Given
    departement = "07"
    creneau = Creneau(
        horaire=dateutil.parser.parse("2021-06-06T06:30:00.000Z"),
        lieu=centre_perigueux,
        reservation_url="https://some.url/reservation",
        timezone=gettz("Europe/Paris"),
        type_vaccin=Vaccine.ASTRAZENECA,
    )
    # When
    actual = next(ResourceParDepartement.from_creneaux([creneau], departement=departement, now=now))
    # Then
    assert actual.asdict() == {
        "version": 1,
        "last_updated": expected_now.isoformat(),
        "centres_disponibles": [],
        "centres_indisponibles": [],
    }


def test_resource_par_departement__1_creneau():
    # Given
    departement = "07"
    creneau = Creneau(
        horaire=dateutil.parser.parse("2021-06-06T06:30:00.000Z"),
        lieu=centre_lamastre,
        reservation_url="https://some.url/reservation",
        timezone=gettz("Europe/Paris"),
        type_vaccin=[Vaccine.MODERNA],
    )
    expected = {
        "version": 1,
        "last_updated": expected_now.isoformat(),
        "centres_disponibles": [
            {
                "departement": "07",
                "nom": "CENTRE DE VACCINATION COVID - LAMASTRE",
                "url": "https://www.maiia.com/centre-de-vaccination/07270-lamastre/centre-de-vaccination-covid---lamastre?centerid=5fff1f61b1a1aa1cc204f203",
                "location": {"longitude": 4.5, "latitude": 45.0, "city": "Lamastre", "cp": "07270"},
                "metadata": None,
                "prochain_rdv": "2021-06-06T06:30:00+00:00",
                "last_scan_with_availabilities": None,
                "request_counts": None,
                "plateforme": "Maiia",
                "type": "vaccination-center",
                "appointment_count": 1,
                "appointment_schedules": [],
                "internal_id": "maiia5fff1f61b1a1aa1cc204f203",
                "vaccine_type": ["Moderna"],
                "appointment_by_phone_only": False,
                "erreur": None,
            }
        ],
        "centres_indisponibles": [],
    }
    # When
    actual = next(ResourceParDepartement.from_creneaux([creneau], departement=departement, now=now))
    # Then
    assert actual.asdict()["centres_disponibles"] == expected["centres_disponibles"]


def test_resource_par_departement__0_creneau():
    # Given
    departement = "07"
    creneau = PasDeCreneau(lieu=centre_lamastre)
    expected = {
        "version": 1,
        "last_updated": expected_now.isoformat(),
        "centres_indisponibles": [
            {
                "departement": "07",
                "nom": "CENTRE DE VACCINATION COVID - LAMASTRE",
                "url": "https://www.maiia.com/centre-de-vaccination/07270-lamastre/centre-de-vaccination-covid---lamastre?centerid=5fff1f61b1a1aa1cc204f203",
                "location": {"longitude": 4.5, "latitude": 45.0, "city": "Lamastre", "cp": "07270"},
                "metadata": None,
                "prochain_rdv": None,
                "last_scan_with_availabilities": None,
                "request_counts": None,
                "plateforme": "Maiia",
                "type": "vaccination-center",
                "appointment_count": 0,
                "appointment_schedules": [],
                "internal_id": "maiia5fff1f61b1a1aa1cc204f203",
                "vaccine_type": [],
                "appointment_by_phone_only": False,
                "erreur": None,
            }
        ],
        "centres_disponibles": [],
    }
    # When
    actual = next(ResourceParDepartement.from_creneaux([creneau], departement=departement, now=now))
    # Then
    assert actual.asdict()["centres_indisponibles"] == expected["centres_indisponibles"]
    assert actual.asdict()["centres_disponibles"] == expected["centres_disponibles"]


def test_resource_par_departement__3_creneau():
    # Given
    departement = "07"
    creneau_1 = Creneau(
        horaire=dateutil.parser.parse("2021-06-06T06:30:00.000Z"),
        lieu=centre_lamastre,
        reservation_url="https://some.url/reservation",
        timezone=gettz("Europe/Paris"),
        type_vaccin=[Vaccine.MODERNA],
    )
    creneau_2 = Creneau(
        horaire=dateutil.parser.parse("2021-06-06T06:35:00.000Z"),
        lieu=centre_lamastre,
        reservation_url="https://some.url/reservation",
        timezone=gettz("Europe/Paris"),
        type_vaccin=[Vaccine.MODERNA],
    )
    creneau_3 = Creneau(
        horaire=dateutil.parser.parse("2021-06-06T06:00:00.000Z"),
        lieu=centre_lamastre,
        reservation_url="https://some.url/reservation",
        timezone=gettz("Europe/Paris"),
        type_vaccin=[Vaccine.PFIZER],
    )
    expected = {
        "version": 1,
        "last_updated": expected_now.isoformat(),
        "centres_disponibles": [
            {
                "departement": "07",
                "nom": "CENTRE DE VACCINATION COVID - LAMASTRE",
                "url": "https://www.maiia.com/centre-de-vaccination/07270-lamastre/centre-de-vaccination-covid---lamastre?centerid=5fff1f61b1a1aa1cc204f203",
                "location": {"longitude": 4.5, "latitude": 45.0, "city": "Lamastre", "cp": "07270"},
                "metadata": None,
                "prochain_rdv": "2021-06-06T06:00:00+00:00",
                "plateforme": "Maiia",
                "last_scan_with_availabilities": None,
                "request_counts": None,
                "type": "vaccination-center",
                "appointment_count": 3,
                "appointment_schedules": [],
                "internal_id": "maiia5fff1f61b1a1aa1cc204f203",
                "vaccine_type": ["Moderna", "Pfizer-BioNTech"],
                "appointment_by_phone_only": False,
                "erreur": None,
            }
        ],
        "centres_indisponibles": [],
    }
    # When
    actual = next(
        ResourceParDepartement.from_creneaux([creneau_1, creneau_2, creneau_3], departement=departement, now=now)
    )
    # Then
    assert actual.asdict()["centres_disponibles"] == expected["centres_disponibles"]


centre_lamastre = Lieu(
    departement="07",
    nom="CENTRE DE VACCINATION COVID - LAMASTRE",
    url="https://www.maiia.com/centre-de-vaccination/07270-lamastre/centre-de-vaccination-covid---lamastre?centerid=5fff1f61b1a1aa1cc204f203",
    lieu_type="vaccination-center",
    internal_id="maiia5fff1f61b1a1aa1cc204f203",
    location=CenterLocation(
        longitude=4.5,
        latitude=45.0,
        city="Lamastre",
        cp="07270",
    ),
    metadata=None,
    plateforme=Plateforme.MAIIA,
)

centre_perigueux = Lieu(
    departement="24",
    nom="CENTRE DE VACCINATION COVID - PERIGUEUX",
    url="https://www.doctolib.com/centre-de-vaccination/24000-perigueux/centre-de-vaccination-covid---lamastre?centerid=5fff1f61b1a1aa1cc204f205",
    lieu_type="vaccination-center",
    internal_id="doctolibfaaaaa1b1a1aa1cc204f203",
    location=CenterLocation(
        longitude=4.5,
        latitude=45.0,
        city="Perigueux",
        cp="24000",
    ),
    metadata=None,
    plateforme=Plateforme.DOCTOLIB,
)
