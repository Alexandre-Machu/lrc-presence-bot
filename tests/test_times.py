import pytest

from utils.times import parse_arrival_time


@pytest.mark.parametrize("text,expected", [
    ("21:40", "21:40"), ("21h40", "21:40"), ("21H", "21:00"), ("9.05", "09:05"),
    (" 20h ", "20:00"), ("0:00", "00:00"), ("23:59", "23:59"), ("21", "21:00"),
])
def test_valid(text, expected):
    assert parse_arrival_time(text) == expected


@pytest.mark.parametrize("text", ["", "abc", "24:00", "21:60", "21h70", "25", "21:4:0", None, "-1"])
def test_invalid(text):
    with pytest.raises(ValueError):
        parse_arrival_time(text)
