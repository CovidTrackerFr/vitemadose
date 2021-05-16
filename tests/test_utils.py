import datetime as dt

from utils.vmd_utils import format_phone_number, get_last_scans
from .utils import mock_datetime_now
from scraper.pattern.center_info import CenterInfo


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

    phone_number = "0033146871340"
    assert format_phone_number(phone_number) == "+33146871340"


def test_get_last_scans():

    center_info1 = CenterInfo("01", "Centre 1", "https://example1.fr")
    center_info2 = CenterInfo("01", "Centre 2", "https://example2.fr")

    center_info2.prochain_rdv = "2021-06-06T00:00:00"

    centres_cherchés = [center_info1, center_info2]

    fake_now = dt.datetime(2021, 5, 5)
    with mock_datetime_now(fake_now):
        centres_cherchés = get_last_scans(centres_cherchés)

    assert centres_cherchés[0].last_scan_with_availabilities == None
    assert centres_cherchés[1].last_scan_with_availabilities == "2021-05-05T00:00:00"
