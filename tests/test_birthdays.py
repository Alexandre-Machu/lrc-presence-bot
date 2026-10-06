from datetime import date

import pytest

from utils.birthdays import birthday_on, days_until, parse_birthday


def test_parse_ok_and_leap_day():
    assert parse_birthday("25/12") == (25, 12)
    assert parse_birthday("5/3") == (5, 3)
    assert parse_birthday("29/02") == (29, 2)


@pytest.mark.parametrize("bad", ["31/02", "12-25", "abc", "", "32/01", "10/13"])
def test_parse_invalid(bad):
    with pytest.raises(ValueError):
        parse_birthday(bad)


def test_days_until_wraps_year():
    assert days_until("05/01", date(2026, 12, 20)) == 16
    assert days_until("20/12", date(2026, 12, 20)) == 0
    assert days_until("19/12", date(2026, 12, 20)) == 364


def test_feb_29_non_leap_year():
    assert birthday_on(2026, 29, 2) == date(2026, 2, 28)
    assert birthday_on(2028, 29, 2) == date(2028, 2, 29)
    assert days_until("29/02", date(2026, 2, 27)) == 1
