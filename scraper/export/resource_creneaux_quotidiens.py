import dateutil
from dateutil.tz import gettz
from datetime import datetime, timedelta
from typing import Iterator, Union
from .resource import Resource
from scraper.creneaux.creneau import Creneau, Lieu, Plateforme, PasDeCreneau

DEFAULT_NEXT_DAYS = 7
DEFAULT_TAGS = {"all": lambda creneau: True}


class ResourceCreneauxQuotidiens(Resource):
    def __init__(self, departement, next_days=DEFAULT_NEXT_DAYS, now=datetime.now, tags=DEFAULT_TAGS):
        super().__init__()
        self.departement = departement
        self.now = now
        self.next_days = next_days
        today = now(tz=gettz("Europe/Paris"))
        self.dates = {}
        for days_from_now in range(0, next_days + 1):
            day = today + timedelta(days=days_from_now)
            date = as_date(day)
            self.dates[date] = ResourceCreneauxParDate(date=date, tags=tags)

    def on_creneau(self, creneau: Union[Creneau, PasDeCreneau]):
        if creneau.lieu.departement == self.departement and creneau.disponible:
            date = as_date(creneau.horaire)
            if date in self.dates:
                self.dates[date].on_creneau(creneau)

    def asdict(self):
        return {"departement": self.departement, "creneaux_quotidiens": [date.asdict() for date in self.dates.values()]}


class ResourceCreneauxParDate(Resource):
    def __init__(self, date: str, tags=DEFAULT_TAGS):
        super().__init__()
        self.date = date
        self.total = 0
        self.tags = tags
        self.lieux = {}

    def on_creneau(self, creneau: Union[Creneau, PasDeCreneau]):
        if creneau.disponible and as_date(creneau.horaire) == self.date:
            self.total += 1
            if not creneau.lieu.internal_id in self.lieux:
                self.lieux[creneau.lieu.internal_id] = ResourceCreneauxParLieu(
                    internal_id=creneau.lieu.internal_id, tags=self.tags
                )

            self.lieux[creneau.lieu.internal_id].on_creneau(creneau)

    def asdict(self):
        return {
            "date": self.date,
            "total": self.total,
            "creneaux_par_lieu": [lieu.asdict() for lieu in self.lieux.values()],
        }


class ResourceCreneauxParLieu(Resource):
    def __init__(self, internal_id: str, tags=DEFAULT_TAGS):
        super().__init__()
        self.internal_id = internal_id
        self.total = 0
        self.tags = tags
        self.par_tag = {tag: {"tag": tag, "creneaux": 0} for tag in tags.keys()}

    def on_creneau(self, creneau: Union[Creneau, PasDeCreneau]):
        if creneau.disponible and creneau.lieu.internal_id == self.internal_id:
            self.total += 1
            for tag, qualifies in self.tags.items():
                if qualifies(creneau):
                    self.par_tag[tag]["creneaux"] += 1

    def asdict(self):
        return {"lieu": self.internal_id, "creneaux_par_tag": list(self.par_tag.values())}


def as_date(datetime):
    return datetime.strftime("%Y-%m-%d")
