from scraper.pattern.center_location import CenterLocation
from scraper.pattern.scraper_request import ScraperRequest
from scraper.pattern.scraper_result import ScraperResult, DRUG_STORE
from scraper.pattern.center_info import (
    CenterInfo,
    convert_csv_address,
    convert_csv_business_hours,
    convert_ordoclic_to_center_info,
)
from scraper.pattern.vaccine import Vaccine, get_vaccine_name, get_vaccine_astrazeneca_minus_55_edgecase


def test_center_info_fill():
    center = CenterInfo("Paris", "Centre 1", "https://.../centre")
    newloc = CenterLocation(1.122, 2.391, "Ok", "Cp")
    request = ScraperRequest(center.url, "2021-05-04")
    result = ScraperResult(request, "Doctolib", "2021-05-06")
    center.fill_localization(newloc)
    request.update_appointment_count(42)
    request.add_vaccine_type(Vaccine.PFIZER)
    request.add_vaccine_type(Vaccine.ASTRAZENECA)
    request.add_vaccine_type(Vaccine.MODERNA)
    request.update_internal_id("doctolibcentre1")
    request.update_practitioner_type(DRUG_STORE)
    request.set_appointments_only_by_phone(False)
    center.fill_result(result)

    assert center.location == newloc
    assert center.prochain_rdv == "2021-05-06"
    assert center.plateforme == "Doctolib"
    assert center.type == "drugstore"
    assert center.appointment_count == 42
    assert center.internal_id == "doctolibcentre1"
    assert center.vaccine_type == ["Pfizer-BioNTech", "AstraZeneca", "Moderna"]
    assert not center.appointment_by_phone_only
    assert center.default() == {
        "departement": "Paris",
        "nom": "Centre 1",
        "url": "https://.../centre",
        "location": {"longitude": 1.122, "latitude": 2.391, "city": "Ok", "cp": "Cp"},
        "metadata": None,
        "prochain_rdv": "2021-05-06",
        "plateforme": "Doctolib",
        "type": "drugstore",
        "appointment_count": 42,
        "internal_id": "doctolibcentre1",
        "vaccine_type": ["Pfizer-BioNTech", "AstraZeneca", "Moderna"],
        "appointment_by_phone_only": False,
        "erreur": None,
        "last_scan_with_availabilities": None,
        "appointment_schedules": None,
        "request_counts": None,
    }


def test_convert_address():
    data = {"adr_num": "1", "adr_voie": "Rue de la Fraise", "com_cp": "75016", "com_nom": "Paris"}
    address = convert_csv_address(data)
    assert address == "1 Rue de la Fraise, 75016 Paris"
    data = {"address": "12 Rue de la Vie, 75012 Paris"}
    address = convert_csv_address(data)
    assert address == "12 Rue de la Vie, 75012 Paris"


def test_center_info_next_availability():
    center = CenterInfo("Paris", "Centre 1", "https://.../centre")
    center.prochain_rdv = "TEST"
    data = center.handle_next_availability()
    assert not data
    center.prochain_rdv = "2021-06-06"
    data = center.handle_next_availability()
    assert center.prochain_rdv == "2021-06-06"
    center.prochain_rdv = "2042-04-10T00:00:00"
    data = center.handle_next_availability()
    assert center.prochain_rdv is None


def test_center_info_business_hours():
    data = {
        "rdv_lundi": "09:50-10:10",
        "rdv_mardi": "09:10-10:10",
        "rdv_mercredi": "10:00-10:10",
        "rdv_jeudi": "10:20-10:40",
        "rdv_vendredi": "09:50-10:10",
        "rdv_samedi": "09:00-10:20",
        "rdv_dimanche": "Fermé",
        "rdv_dimanche2": "Fermé",
    }
    business_hours = convert_csv_business_hours(data)
    assert business_hours == {
        "lundi": "09:50-10:10",
        "mardi": "09:10-10:10",
        "mercredi": "10:00-10:10",
        "jeudi": "10:20-10:40",
        "vendredi": "09:50-10:10",
        "samedi": "09:00-10:20",
        "dimanche": "Fermé",
    }
    business2 = convert_csv_business_hours({"business_hours": business_hours})
    assert business2 == business_hours
    data = {"dimanche2": "Fermé"}
    business = convert_csv_business_hours(data)
    assert not business


def test_convert_ordoclic():
    center = CenterInfo("Paris", "Centre 1", "https://.../centre")
    data = {
        "location": {
            "coordinates": {
                "lon": 1.1281,
                "lat": 93.182,
            },
            "city": "Foobar",
            "address": "12 Avenue de la ville",
            "zip": "22000",
        },
        "phone_number": "06 06 06 06 06",
    }
    center = convert_ordoclic_to_center_info(data, center)
    assert center.metadata["address"] == "12 Avenue de la ville, 22000 Foobar"
    assert center.metadata["phone_number"] == "+33606060606"
    assert center.metadata["business_hours"] is None


def test_convert_ordoclic_second():
    data = {
        "nom": "Centre 2",
        "com_insee": "35238",
        "rdv_site_web": "https://site.fr/",
        "iterator": "ordoclic",
        "location": {
            "coordinates": {
                "lon": 1.1281,
                "lat": 93.182,
            },
            "city": "Foobar",
            "address": "12 Avenue de la ville",
            "zip": "22000",
        },
        "phone_number": "06 06 06 06 06",
    }
    center = CenterInfo.from_csv_data(data)
    assert center.nom == "Centre 2"
    assert center.metadata["address"] == "12 Avenue de la ville, 22000 Foobar"
    assert center.metadata["phone_number"] == "+33606060606"
    assert center.metadata["business_hours"] is None


def test_convert_centerinfo():
    data = {
        "nom": "Centre 1",
        "rdv_site_web": "https://site.fr",
        "com_insee": "35238",
        "rdv_tel": "06 06 06 06 06",
        "phone_number": "06 06 06 06 07",
        "adr_num": "1",
        "adr_voie": "Rue de la Fraise",
        "com_cp": "75016",
        "com_nom": "Paris",
        "business_hours": {
            "lundi": "09:50-10:10",
            "mardi": "09:10-10:10",
            "mercredi": "10:00-10:10",
            "jeudi": "10:20-10:40",
            "vendredi": "09:50-10:10",
            "samedi": "09:00-10:20",
            "dimanche": "Fermé",
        },
    }

    center = CenterInfo.from_csv_data(data)
    assert center.departement == "35"
    assert center.url == "https://site.fr"
    assert center.metadata["address"] == "1 Rue de la Fraise, 75016 Paris"
    assert center.metadata["phone_number"] == "+33606060607"
    assert center.metadata["business_hours"] == {
        "lundi": "09:50-10:10",
        "mardi": "09:10-10:10",
        "mercredi": "10:00-10:10",
        "jeudi": "10:20-10:40",
        "vendredi": "09:50-10:10",
        "samedi": "09:00-10:20",
        "dimanche": "Fermé",
    }


def test_convert_centerinfo_invalid():
    data = {
        "nom": "Centre 1",
        "gid": "d001",
        "rdv_site_web": "https://site.fr",
        "com_insee": "0095238",
        "rdv_tel": "06 06 06 06 06",
        "phone_number": "06 06 06 06 07",
        "adr_num": "1",
        "adr_voie": "Rue de la Fraise",
        "com_cp": "75016",
        "com_nom": "Paris",
        "business_hours": {
            "lundi": "09:50-10:10",
            "mardi": "09:10-10:10",
            "mercredi": "10:00-10:10",
            "jeudi": "10:20-10:40",
            "vendredi": "09:50-10:10",
            "samedi": "09:00-10:20",
            "dimanche": "Fermé",
        },
    }

    center = CenterInfo.from_csv_data(data)
    assert center.departement == ""
    assert center.url == "https://site.fr"
    assert center.metadata["address"] == "1 Rue de la Fraise, 75016 Paris"
    assert center.metadata["phone_number"] == "+33606060607"
    assert center.metadata["business_hours"] == {
        "lundi": "09:50-10:10",
        "mardi": "09:10-10:10",
        "mercredi": "10:00-10:10",
        "jeudi": "10:20-10:40",
        "vendredi": "09:50-10:10",
        "samedi": "09:00-10:20",
        "dimanche": "Fermé",
    }


def test_vaccine_name():
    name = get_vaccine_name("", Vaccine.PFIZER)
    assert name == "Pfizer-BioNTech"


def test_minus_edgecase():
    name = "2ème injection pour moins de 55 ans suite à première injection AstraAzeneca"
    vaccine = get_vaccine_astrazeneca_minus_55_edgecase(name)

    assert vaccine == Vaccine.ARNM
    name = "2ème injection AstraZeneca ---"
    vaccine = get_vaccine_astrazeneca_minus_55_edgecase(name)
    assert vaccine == Vaccine.ASTRAZENECA
