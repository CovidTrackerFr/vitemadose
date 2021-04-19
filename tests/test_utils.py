import datetime as dt

from utils.vmd_utils import format_phone_number, get_last_scans
from scraper.pattern.center_info import CenterInfo
from .utils import mock_datetime_now

def test_format_phone_number():

	phone_number = "+331204312"
	assert format_phone_number(phone_number) == "+331204312"

	phone_number = "+569492392"
	assert format_phone_number(phone_number) == "+569492392"
	
	phone_number = "0123456789"
	assert format_phone_number(phone_number) == "+33123456789"

	phone_number = "01.20.43.12"
	assert format_phone_number(phone_number) == "+331204312"

	phone_number = "3975"
	assert format_phone_number(phone_number) == "+333975"


def test_get_last_scans():

    outpath_format = "tests/fixtures/utils/{}.json"

    center_info1 = CenterInfo("01", "Centre 1", "https://example1.fr")
    center_info2 = CenterInfo("01", "Centre 2", "https://example2.fr")
    center_info3 = CenterInfo("01", "Centre 3", "https://example3.fr")
    center_info4 = CenterInfo("01", "Centre 4", "https://example4.fr")

    center_info4.prochain_rdv = "2021-06-06T00:00:00"

    centres_cherchés = [
        center_info1,
        center_info2,
        center_info3,
        center_info4
    ]

    fake_now = dt.datetime(2021, 5, 5)
    with mock_datetime_now(fake_now):
        centres_cherchés = get_last_scans(centres_cherchés, outpath_format)

    assert centres_cherchés[0].last_scan_with_availabilities == "2021-04-04T00:00:00"
    assert centres_cherchés[1].last_scan_with_availabilities == None
    assert centres_cherchés[2].last_scan_with_availabilities == "2021-03-03T00:00:00"
    assert centres_cherchés[3].last_scan_with_availabilities == "2021-05-05T00:00:00"