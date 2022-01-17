import pytest

from scraper.export.export_v2 import Departement
from utils.vmd_utils import departementUtils


def test_import_departements():
    departements = departementUtils.import_departements()

    assert len(departements) == 102
    assert departements[:3] == ["01", "02", "03"]
    assert departements[83] == "83"
    assert departements[-2] == "976"
    assert departements[-1] == "om"
    assert departements.index("2A") == 28
    assert sorted(departements) == departements


def test_insee_to_departement_code():
    right_insee_code = "01001"
    short_insee_code = "1001"
    DOM_TOM_insee_code = "97234"
    passed_linked_to_Guadeloupe_insee_code = "97120"
    corse_insee_code = "2A004"
    monaco_insee_code = "99138"
    wrong_insee_code = "123"
    not_in_insee_code_table_insee_code = "12345"
    saint_barthelemy_insee_code = "97701"
    miquelon_laglande_insee_code = "97501"
    saint_pierre_insee_code = "97502"
    saint_martin_insee_code = "97801"

    assert departementUtils.to_departement_number(right_insee_code) == right_insee_code[:2]
    assert departementUtils.to_departement_number(short_insee_code) == short_insee_code.zfill(5)[:2]
    assert departementUtils.to_departement_number(DOM_TOM_insee_code) == DOM_TOM_insee_code[:3]
    assert departementUtils.to_departement_number(passed_linked_to_Guadeloupe_insee_code) == "971"
    assert departementUtils.to_departement_number(corse_insee_code) == "2A"
    assert departementUtils.to_departement_number(monaco_insee_code) == "98"
    with pytest.raises(ValueError):
        departementUtils.to_departement_number(wrong_insee_code)
    with pytest.raises(ValueError):
        departementUtils.to_departement_number(not_in_insee_code_table_insee_code)
    assert departementUtils.to_departement_number(saint_barthelemy_insee_code) == "om"
    assert departementUtils.to_departement_number(miquelon_laglande_insee_code) == "om"
    assert departementUtils.to_departement_number(saint_pierre_insee_code) == "om"
    assert departementUtils.to_departement_number(saint_martin_insee_code) == "om"


def test_get_city():
    address_1 = "2 avenue de la République, 75005 PARIS"
    address_2 = " 24 Rue de la Brèche, 91740 Pussay "
    address_3 = "Centre Cial du Bois des Roches 91240 SAINT MICHEL SUR ORGE"
    address_4 = " , 83700 Saint-Raphaël "
    address_5 = "1171 Avenue Gaston Feuillard\n97100 Basse-Terre"
    address_6 = "Rue de la République"

    assert departementUtils.get_city(address_1) == "PARIS"
    assert departementUtils.get_city(address_2) == "Pussay"
    assert departementUtils.get_city(address_3) == "SAINT MICHEL SUR ORGE"
    assert departementUtils.get_city(address_4) == "Saint-Raphaël"
    assert departementUtils.get_city(address_5) == "Basse-Terre"
    assert departementUtils.get_city(address_6) == None


def test_get_cp():
    address_1 = "2 avenue de la République, 75005 PARIS"
    address_2 = " 24 Rue de la Brèche, 91740 Pussay "
    address_3 = "Centre Cial du Bois des Roches 91240 SAINT MICHEL SUR ORGE"
    address_4 = " , 83700 Saint-Raphaël "
    address_5 = "1171 Avenue Gaston Feuillard\n97100 Basse-Terre"
    address_6 = "Rue de la République"

    assert departementUtils.get_cp(address_1) == "75005"
    assert departementUtils.get_cp(address_2) == "91740"
    assert departementUtils.get_cp(address_3) == "91240"
    assert departementUtils.get_cp(address_4) == "83700"
    assert departementUtils.get_cp(address_5) == "97100"
    assert departementUtils.get_cp(address_6) == None


def test_cp_to_insee():
    # Paris 15
    cp_paris_15 = "75015"
    insee_paris_15 = "75115"
    assert departementUtils.cp_to_insee(cp_paris_15) == insee_paris_15

    # Ajaccio
    cp_ajaccio_1 = "20090"
    cp_ajaccio_2 = "20090"
    insee_ajaccio = "2A004"
    assert departementUtils.cp_to_insee(cp_ajaccio_1) == insee_ajaccio
    assert departementUtils.cp_to_insee(cp_ajaccio_2) == insee_ajaccio

    # Paray-Vieille-Poste
    cp_paray_vieille_poste = "94390"
    insee_paray_vieille_poste = "91479"
    assert departementUtils.cp_to_insee(cp_paray_vieille_poste) == insee_paray_vieille_poste

    # Fort de France
    cp_fort_de_france = "97234"
    insee_fort_de_france = "97209"
    assert departementUtils.cp_to_insee(cp_fort_de_france) == insee_fort_de_france

    # Monaco
    cp_monaco = "98000"
    insee_monaco = "99138"
    assert departementUtils.cp_to_insee(cp_monaco) == insee_monaco

    # CP invalide
    invalid_cp = "1234"
    assert departementUtils.cp_to_insee(invalid_cp) == f"0{invalid_cp}"

    # Cholet entier
    cp_cholet_int = 49300  # => invalide
    insee_cholet = "49099"
    assert departementUtils.cp_to_insee(cp_cholet_int) == insee_cholet

    # Cholet entier
    cp_st_maurice_remens_int = 1500  # => invalide
    insee_st_maurice_remens = "01379"
    assert departementUtils.cp_to_insee(cp_st_maurice_remens_int) == insee_st_maurice_remens


def test_cp_to_insee_with_cedex():
    cedex_st_michel = "16959"
    assert departementUtils.cp_to_insee(cedex_st_michel) == "16341"
    assert departementUtils.cp_to_insee(f"{cedex_st_michel} CEDEX") == "16341"


def test_departement_all_should_return_overseas():
    # Given
    expected_output_element = Departement("om", "Collectivités d'Outremer", -1, "Outremer")

    # When
    output = Departement.all()

    # Then
    assert expected_output_element in output
