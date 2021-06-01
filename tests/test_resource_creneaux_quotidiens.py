import dateutil
from dateutil.tz import gettz
from scraper.creneaux.creneau import Creneau, Plateforme, Lieu, PasDeCreneau
from scraper.export.resource_centres import ResourceParDepartement
from datetime import datetime
from scraper.pattern.vaccine import Vaccine
from scraper.pattern.center_location import CenterLocation
from scraper.export.resource_creneaux_quotidiens import ResourceCreneauxQuotidiens

stubbed_now = dateutil.parser.parse("2021-05-26T21:34:00+02:00")


def now(*args, **kwargs):
    return stubbed_now


def test_resource_creneaux_quotidiens__empty():
    # Given
    departement = "07"
    creneaux = []
    expected = {
        "departement": "07",
        "creneaux_quotidiens": [
            {"date": "2021-05-26", "total": 0, "creneaux_par_lieu": []},
            {"date": "2021-05-27", "total": 0, "creneaux_par_lieu": []},
            {"date": "2021-05-28", "total": 0, "creneaux_par_lieu": []},
            {"date": "2021-05-29", "total": 0, "creneaux_par_lieu": []},
            {"date": "2021-05-30", "total": 0, "creneaux_par_lieu": []},
            {"date": "2021-05-31", "total": 0, "creneaux_par_lieu": []},
            {"date": "2021-06-01", "total": 0, "creneaux_par_lieu": []},
            {"date": "2021-06-02", "total": 0, "creneaux_par_lieu": []},
        ],
    }
    # When
    actual = next(ResourceCreneauxQuotidiens.from_creneaux(creneaux, next_days=7, departement=departement, now=now))
    # Then
    assert actual.asdict() == expected


def test_resource_creneaux_quotidiens__other_departement():
    # Given
    departement = "07"
    creneaux = [
        Creneau(
            horaire=dateutil.parser.parse("2021-06-01T06:30:00.000Z"),
            lieu=centre_perigueux,
            reservation_url="https://some.url/reservation",
            timezone=gettz("Europe/Paris"),
            type_vaccin=Vaccine.ASTRAZENECA,
        )
    ]
    expected = {
        "departement": "07",
        "creneaux_quotidiens": [
            {"date": "2021-05-26", "total": 0, "creneaux_par_lieu": []},
            {"date": "2021-05-27", "total": 0, "creneaux_par_lieu": []},
            {"date": "2021-05-28", "total": 0, "creneaux_par_lieu": []},
            {"date": "2021-05-29", "total": 0, "creneaux_par_lieu": []},
            {"date": "2021-05-30", "total": 0, "creneaux_par_lieu": []},
            {"date": "2021-05-31", "total": 0, "creneaux_par_lieu": []},
            {"date": "2021-06-01", "total": 0, "creneaux_par_lieu": []},
            {"date": "2021-06-02", "total": 0, "creneaux_par_lieu": []},
        ],
    }
    # When
    actual = next(ResourceCreneauxQuotidiens.from_creneaux(creneaux, next_days=7, departement=departement, now=now))
    # Then
    assert actual.asdict() == expected


def test_resource_creneaux_quotidiens__1_creneau():
    # Given
    departement = "07"
    creneaux = [
        Creneau(
            horaire=dateutil.parser.parse("2021-06-01T06:30:00.000Z"),
            lieu=centre_lamastre,
            reservation_url="https://some.url/reservation",
            timezone=gettz("Europe/Paris"),
            type_vaccin=Vaccine.ASTRAZENECA,
        )
    ]
    expected = {
        "departement": "07",
        "creneaux_quotidiens": [
            {"date": "2021-05-26", "total": 0, "creneaux_par_lieu": []},
            {"date": "2021-05-27", "total": 0, "creneaux_par_lieu": []},
            {"date": "2021-05-28", "total": 0, "creneaux_par_lieu": []},
            {"date": "2021-05-29", "total": 0, "creneaux_par_lieu": []},
            {"date": "2021-05-30", "total": 0, "creneaux_par_lieu": []},
            {"date": "2021-05-31", "total": 0, "creneaux_par_lieu": []},
            {
                "date": "2021-06-01",
                "total": 1,
                "creneaux_par_lieu": [
                    {"lieu": centre_lamastre.internal_id, "creneaux_par_tag": [{"tag": "all", "creneaux": 1}]}
                ],
            },
            {"date": "2021-06-02", "total": 0, "creneaux_par_lieu": []},
        ],
    }
    # When
    actual = next(ResourceCreneauxQuotidiens.from_creneaux(creneaux, next_days=7, departement=departement, now=now))
    # Then
    assert actual.asdict() == expected


def test_resource_creneaux_quotidiens__2_creneau():
    # Given
    departement = "07"
    creneaux = [
        Creneau(
            horaire=dateutil.parser.parse("2021-06-01T06:30:00.000Z"),
            lieu=centre_lamastre,
            reservation_url="https://some.url/reservation",
            timezone=gettz("Europe/Paris"),
            type_vaccin=Vaccine.ASTRAZENECA,
        ),
        Creneau(
            horaire=dateutil.parser.parse("2021-05-27T18:12:00.000Z"),
            lieu=centre_saint_andeol,
            reservation_url="https://some.url/reservation",
            timezone=gettz("Europe/Paris"),
            type_vaccin=Vaccine.MODERNA,
        ),
        PasDeCreneau(lieu=centre_saint_andeol),
    ]
    expected = {
        "departement": "07",
        "creneaux_quotidiens": [
            {"date": "2021-05-26", "total": 0, "creneaux_par_lieu": []},
            {
                "date": "2021-05-27",
                "total": 1,
                "creneaux_par_lieu": [
                    {"lieu": centre_saint_andeol.internal_id, "creneaux_par_tag": [{"tag": "all", "creneaux": 1}]}
                ],
            },
            {"date": "2021-05-28", "total": 0, "creneaux_par_lieu": []},
            {"date": "2021-05-29", "total": 0, "creneaux_par_lieu": []},
            {"date": "2021-05-30", "total": 0, "creneaux_par_lieu": []},
            {"date": "2021-05-31", "total": 0, "creneaux_par_lieu": []},
            {
                "date": "2021-06-01",
                "total": 1,
                "creneaux_par_lieu": [
                    {"lieu": centre_lamastre.internal_id, "creneaux_par_tag": [{"tag": "all", "creneaux": 1}]}
                ],
            },
            {"date": "2021-06-02", "total": 0, "creneaux_par_lieu": []},
        ],
    }
    # When
    actual = next(ResourceCreneauxQuotidiens.from_creneaux(creneaux, next_days=7, departement=departement, now=now))
    # Then
    assert actual.asdict() == expected


def test_resource_creneaux_quotidiens__2_creneau_with_custom_tags():
    # Given
    departement = "07"
    tags = {
        "all": lambda c: True,
        "arnm": lambda c: c.type_vaccin == Vaccine.MODERNA or c.type_vaccin == Vaccine.PFIZER,
        "adeno": lambda c: c.type_vaccin == Vaccine.ASTRAZENECA or c.type_vaccin == Vaccine.JANSSEN,
    }
    creneaux = [
        Creneau(
            horaire=dateutil.parser.parse("2021-06-01T06:30:00.000Z"),
            lieu=centre_lamastre,
            reservation_url="https://some.url/reservation",
            timezone=gettz("Europe/Paris"),
            type_vaccin=Vaccine.ASTRAZENECA,
        ),
        Creneau(
            horaire=dateutil.parser.parse("2021-05-27T18:12:00.000Z"),
            lieu=centre_saint_andeol,
            reservation_url="https://some.url/reservation",
            timezone=gettz("Europe/Paris"),
            type_vaccin=Vaccine.MODERNA,
        ),
        PasDeCreneau(lieu=centre_saint_andeol),
    ]
    expected = {
        "departement": "07",
        "creneaux_quotidiens": [
            {"date": "2021-05-26", "total": 0, "creneaux_par_lieu": []},
            {
                "date": "2021-05-27",
                "total": 1,
                "creneaux_par_lieu": [
                    {
                        "lieu": centre_saint_andeol.internal_id,
                        "creneaux_par_tag": [
                            {"tag": "all", "creneaux": 1},
                            {"tag": "arnm", "creneaux": 1},
                            {"tag": "adeno", "creneaux": 0},
                        ],
                    }
                ],
            },
            {"date": "2021-05-28", "total": 0, "creneaux_par_lieu": []},
            {"date": "2021-05-29", "total": 0, "creneaux_par_lieu": []},
            {"date": "2021-05-30", "total": 0, "creneaux_par_lieu": []},
            {"date": "2021-05-31", "total": 0, "creneaux_par_lieu": []},
            {
                "date": "2021-06-01",
                "total": 1,
                "creneaux_par_lieu": [
                    {
                        "lieu": centre_lamastre.internal_id,
                        "creneaux_par_tag": [
                            {"tag": "all", "creneaux": 1},
                            {"tag": "arnm", "creneaux": 0},
                            {"tag": "adeno", "creneaux": 1},
                        ],
                    }
                ],
            },
            {"date": "2021-06-02", "total": 0, "creneaux_par_lieu": []},
        ],
    }
    # When
    actual = next(
        ResourceCreneauxQuotidiens.from_creneaux(creneaux, next_days=7, departement=departement, now=now, tags=tags)
    )
    # Then
    assert actual.asdict() == expected


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

centre_saint_andeol = Lieu(
    departement="07",
    nom="CENTRE DE VACCINATION COVID 19 TERRITORIAL ET HOSPITALIER DE BOURG DU SAINT-ANDÉOL VIVIERS",
    url="https://www.doctolib.fr/vaccination-covid-19/bourg-saint-andeol/centre-de-vaccination-territorial-bourg-saint-andeol?pid=practice-166627",
    lieu_type="vaccination-center",
    internal_id="doctolib245141pid166627",
    location=CenterLocation(
        longitude=4.6,
        latitude=44.3,
        city="Bourg-Saint-Andéol",
        cp="07700",
    ),
    metadata=None,
    plateforme=Plateforme.DOCTOLIB,
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
