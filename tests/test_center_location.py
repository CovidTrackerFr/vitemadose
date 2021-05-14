from scraper.pattern.center_location import convert_csv_data_to_location


def test_location_working():
    dict = {"long_coor1": 1.231, "lat_coor1": -42.839, "com_nom": "Rennes"}
    center_location = convert_csv_data_to_location(dict)
    assert center_location
    assert center_location.longitude == 1.231
    assert center_location.latitude == -42.839
    assert center_location.city == "Rennes"


def test_location_issue():
    dict = {"long_coor31": 1.231, "lat_coor13": -42.839, "com_nom": "Rennes"}
    center_location = convert_csv_data_to_location(dict)
    assert center_location is None


def test_location_parse_address():
    dict = {"long_coor1": 1.231, "lat_coor1": -42.839, "address": "39 Rue de la Fraise, 35000 Foobar"}
    center_location = convert_csv_data_to_location(dict)
    assert center_location.city == "Foobar"


def test_location_bad_values():
    dict = {"long_coor1": "1,231Foo", "lat_coor1": -1.23, "address": "39 Rue de la Fraise, 35000 Foobar"}
    center_location = convert_csv_data_to_location(dict)
    assert center_location is None


def test_location_callback():
    dict = {"long_coor1": "1.231", "lat_coor1": -1.23, "address": "39 Rue de la Fraise, 35000 Foo2bar"}
    center_location = convert_csv_data_to_location(dict)
    assert center_location.default() == {"longitude": 1.231, "latitude": -1.23, "city": "Foo2bar", "cp": "35000"}
