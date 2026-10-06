"""Saisie d'une heure d'arrivée libre."""
import re

_PATTERN = re.compile(r"^\s*(\d{1,2})\s*(?:[:hH.]\s*(\d{1,2})?)?\s*$")


def parse_arrival_time(text):
    """'21:40', '21h40', '21h', '9.05' -> 'HH:MM'. Lève ValueError si invalide."""
    m = _PATTERN.match(text or "")
    if not m:
        raise ValueError(text)
    hour = int(m.group(1))
    minute = int(m.group(2) or 0)
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError(text)
    return f"{hour:02d}:{minute:02d}"
