import datetime as dt

from utils.vmd_utils import format_phone_number


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
