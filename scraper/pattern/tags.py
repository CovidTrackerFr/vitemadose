from scraper.creneaux.creneau import Creneau
from scraper.pattern.vaccine import Vaccine


def tag_all(creneau: Creneau):
    return True


def first_dose(creneau: Creneau):
    if creneau.dose:
        if 1 in creneau.dose:
            return True


def second_dose(creneau: Creneau):
    if creneau.dose:
        if 2 in creneau.dose:
            return True


def third_dose(creneau: Creneau):
    if creneau.dose:
        if 3 in creneau.dose:
            return True


def unknown_dose(creneau: Creneau):
    if not creneau.dose:
        return True
    if len(creneau.dose) == 0:
        return True


CURRENT_TAGS = {
    "all": [tag_all],
    "first_or_second_dose": [first_dose, second_dose],
    "third_dose": [third_dose],
    "unknown_dose": [unknown_dose],
}
