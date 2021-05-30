from scraper.creneaux.creneau import Creneau
from scraper.pattern.vaccine import Vaccine

def tag_all(creneau: Creneau):
    return True

def tag_preco18_55(creneau: Creneau):
    return creneau.type_vaccin == Vaccine.PFIZER or creneau.type_vaccin == Vaccine.MODERNA

CURRENT_TAGS = {
    'all': tag_all,
    'preco18_55': tag_preco18_55
}
