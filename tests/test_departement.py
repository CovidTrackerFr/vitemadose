import pytest
from scraper.departements import to_departement_number

def test_insee_to_departement_code():
    right_insee_code = "01001"
    short_insee_code = "1001"
    DOM_TOM_insee_code = "97234"
    passed_linked_to_Guadeloupe_insee_code = "97801"
    corse_insee_code = "2A004"
    wrong_insee_code = "123"
    not_in_insee_code_table_insee_code = "12345"

    assert to_departement_number(right_insee_code) == right_insee_code[:2]
    print(len(short_insee_code))
    assert to_departement_number(short_insee_code) == short_insee_code.zfill(5)[:2]
    assert to_departement_number(DOM_TOM_insee_code) == DOM_TOM_insee_code[:3]
    assert to_departement_number(passed_linked_to_Guadeloupe_insee_code) == "971"
    assert to_departement_number(corse_insee_code) == "20"
    with pytest.raises(ValueError):
        to_departement_number(wrong_insee_code)
    with pytest.raises(ValueError):
        to_departement_number(not_in_insee_code_table_insee_code)