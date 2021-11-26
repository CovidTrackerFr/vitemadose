from scraper.creneaux.creneau import Creneau
from scraper.pattern.vaccine import Vaccine


def tag_all(creneau: Creneau):
    return True


def first_dose(creneau: Creneau):
    if creneau.dose == 1:
        return True


def second_dose(creneau: Creneau):
    if creneau.dose == 2:
        return True


def third_dose(creneau: Creneau):
    if creneau.dose == 3:
        return True


CURRENT_TAGS = {
    "all": tag_all,
    "first_dose": first_dose,
    "second_dose": second_dose,
    "third_dose": third_dose,
}
