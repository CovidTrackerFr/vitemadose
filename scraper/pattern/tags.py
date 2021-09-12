from scraper.creneaux.creneau import Creneau
from scraper.pattern.vaccine import Vaccine


def tag_all(creneau: Creneau):
    return True


CURRENT_TAGS = {"all": tag_all}
