from scraper.creneaux.creneau import Creneau
from scraper.pattern.vaccine import Vaccine


def tag_all(creneau: Creneau):
    return True


def tag_preco18_55(creneau: Creneau):

    if (
        Vaccine.PFIZER in creneau.type_vaccin
        or Vaccine.MODERNA in creneau.type_vaccin
        or Vaccine.ARNM in creneau.type_vaccin
    ):
        return True


CURRENT_TAGS = {"all": tag_all, "preco18_55": tag_preco18_55}
