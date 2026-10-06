"""Logique pure des anniversaires (dates JJ/MM)."""
from datetime import date, datetime


def parse_birthday(date_str):
    """'JJ/MM' -> (jour, mois). Lève ValueError si invalide (29/02 accepté)."""
    d = datetime.strptime(f"{date_str.strip()}/2000", "%d/%m/%Y")
    return d.day, d.month


def format_birthday(day, month):
    return f"{day:02d}/{month:02d}"


def birthday_on(year, day, month):
    """Date de l'anniversaire pour une année ; le 29/02 devient le 28/02 hors bissextile."""
    try:
        return date(year, month, day)
    except ValueError:
        return date(year, 2, 28)


def days_until(date_str, today: date):
    day, month = parse_birthday(date_str)
    nxt = birthday_on(today.year, day, month)
    if nxt < today:
        nxt = birthday_on(today.year + 1, day, month)
    return (nxt - today).days
