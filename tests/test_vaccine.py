from scraper.pattern.vaccine import Vaccine, get_vaccine_name, get_vaccine_astrazeneca_minus_55_edgecase


def test_vaccine_name():
    name = get_vaccine_name("", Vaccine.PFIZER)
    assert name == 'Pfizer-BioNTech'

    name = get_vaccine_name("Injection unique Jansen", Vaccine.PFIZER)
    assert name == 'Janssen'


def test_minus_edgecase():
    name = "2ème injection pour moins de 55 ans suite à première injection AstraAzeneca"
    vaccine = get_vaccine_astrazeneca_minus_55_edgecase(name)
    assert vaccine == Vaccine.ARNM

    name = "Vaccination Covid pour les – de 55 ans suite à une 1ère injection d’AstraZeneca"
    vaccine = get_vaccine_astrazeneca_minus_55_edgecase(name)
    assert vaccine == Vaccine.ARNM

    name = "2ème injection AstraZeneca ---"
    vaccine = get_vaccine_astrazeneca_minus_55_edgecase(name)
    assert vaccine == Vaccine.ASTRAZENECA