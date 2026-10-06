from datetime import date

import pytest

from utils.absences import (
    AbsenceError, absent_on, add_absence, parse_date, purge_past, remove_absence,
)

TODAY = date(2026, 10, 6)


def test_parse_date_with_and_without_year():
    assert parse_date("14/07/2027", TODAY) == date(2027, 7, 14)
    assert parse_date("14/07/27", TODAY) == date(2027, 7, 14)
    assert parse_date("10/10", TODAY) == date(2026, 10, 10)
    assert parse_date("06/10", TODAY) == TODAY
    assert parse_date("01/10", TODAY) == date(2027, 10, 1)  # déjà passé -> année suivante


def test_parse_end_relative_to_start():
    start = date(2026, 12, 28)
    assert parse_date("03/01", TODAY, not_before=start) == date(2027, 1, 3)


@pytest.mark.parametrize("bad", ["", "31/02", "abc", "1/2/3/4"])
def test_parse_invalid(bad):
    with pytest.raises(ValueError):
        parse_date(bad, TODAY)


def test_add_and_active_range():
    data = {}
    add_absence(data, 1, date(2026, 10, 10), date(2026, 10, 17))
    assert absent_on(data, date(2026, 10, 9)) == set()
    assert absent_on(data, date(2026, 10, 10)) == {"1"}
    assert absent_on(data, date(2026, 10, 17)) == {"1"}
    assert absent_on(data, date(2026, 10, 18)) == set()


def test_add_rejects_bad_ranges_and_dedupes():
    data = {}
    with pytest.raises(AbsenceError):
        add_absence(data, 1, date(2026, 10, 10), date(2026, 10, 9))
    with pytest.raises(AbsenceError):
        add_absence(data, 1, date(2026, 10, 10), date(2028, 1, 1))
    add_absence(data, 1, TODAY, TODAY)
    add_absence(data, 1, TODAY, TODAY)
    assert len(data["1"]) == 1


def test_purge_and_remove():
    data = {}
    add_absence(data, 1, date(2026, 9, 1), date(2026, 9, 5))
    add_absence(data, 1, date(2026, 10, 10), date(2026, 10, 12))
    add_absence(data, 2, date(2026, 9, 1), date(2026, 9, 2))
    assert purge_past(data, TODAY) is True
    assert list(data) == ["1"] and len(data["1"]) == 1
    assert remove_absence(data, 1, "2026-10-10") is True
    assert data == {}
    assert remove_absence(data, 1, "2026-10-10") is False


def test_toggle_days_merges_and_splits():
    from utils.absences import toggle_days
    data = {}
    assert toggle_days(data, 1, [date(2026, 10, 12)]) is True
    assert toggle_days(data, 1, [date(2026, 10, 13)]) is True
    assert data["1"] == [{"start": "2026-10-12", "end": "2026-10-13"}]
    assert toggle_days(data, 1, [date(2026, 10, 12)]) is False   # retire un jour
    assert data["1"] == [{"start": "2026-10-13", "end": "2026-10-13"}]
    week = [date(2026, 10, 12 + i) for i in range(7)]
    assert toggle_days(data, 1, week) is True                    # tout ajouter
    assert data["1"] == [{"start": "2026-10-12", "end": "2026-10-18"}]
    assert toggle_days(data, 1, week) is False                   # tout retirer
    assert data == {}
