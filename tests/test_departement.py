import pytest
from utils.vmd_utils import departementUtils



def test_insee_to_departement_code():
    right_insee_code = "01001"
    short_insee_code = "1001"
    DOM_TOM_insee_code = "97234"
    passed_linked_to_Guadeloupe_insee_code = "97801"
    corse_insee_code = "2A004"
    monaco_insee_code = "99138"
    wrong_insee_code = "123"
    not_in_insee_code_table_insee_code = "12345"

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
