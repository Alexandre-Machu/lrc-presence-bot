"""Absences planifiées à l'avance : {user_id: [{"start": ISO, "end": ISO}, ...]}."""
from datetime import date, datetime, timedelta

from config.settings import DATA_DIR
from utils.storage import _read_json, _write_json
import os

ABSENCES_FILE = os.path.join(DATA_DIR, "absences.json")
MAX_SPAN_DAYS = 366


class AbsenceError(ValueError):
    """Erreur de saisie lisible telle quelle par l'utilisateur."""


def parse_date(text, today: date, not_before: date = None):
    """'JJ/MM' ou 'JJ/MM/AAAA' -> date.

    Sans année : la prochaine occurrence (>= not_before, ou aujourd'hui).
    """
    text = text.strip()
    ref = not_before or today
    parts = text.split("/")
    if len(parts) == 3:
        year = int(parts[2])
        if year < 100:
            year += 2000
        return datetime.strptime(f"{parts[0]}/{parts[1]}/{year}", "%d/%m/%Y").date()
    if len(parts) != 2:
        raise ValueError(text)
    d = datetime.strptime(f"{text}/2000", "%d/%m/%Y")  # valide jour/mois
    for year in (ref.year, ref.year + 1, ref.year + 2):
        try:
            candidate = date(year, d.month, d.day)
        except ValueError:  # 29/02
            continue
        if candidate >= ref:
            return candidate
    raise ValueError(text)


def load_absences():
    return _read_json(ABSENCES_FILE, {})


def save_absences(data):
    _write_json(ABSENCES_FILE, data)


def purge_past(data, today: date):
    """Retire les absences terminées. Retourne True si quelque chose a changé."""
    changed = False
    for uid in list(data):
        kept = [a for a in data[uid] if date.fromisoformat(a["end"]) >= today]
        if len(kept) != len(data[uid]):
            changed = True
            data[uid] = kept
        if not data[uid]:
            del data[uid]
    return changed


def add_absence(data, uid, start: date, end: date):
    if end < start:
        raise AbsenceError("La date de fin est avant la date de début.")
    if (end - start).days > MAX_SPAN_DAYS:
        raise AbsenceError("Absence trop longue (1 an maximum).")
    entries = data.setdefault(str(uid), [])
    new = {"start": start.isoformat(), "end": end.isoformat()}
    if new not in entries:
        entries.append(new)
        entries.sort(key=lambda a: a["start"])


def remove_absence(data, uid, start_iso):
    entries = data.get(str(uid), [])
    kept = [a for a in entries if a["start"] != start_iso]
    if len(kept) == len(entries):
        return False
    if kept:
        data[str(uid)] = kept
    else:
        data.pop(str(uid), None)
    return True


def absent_on(data, day: date):
    """Ids des membres absents le jour donné."""
    return {
        uid for uid, entries in data.items()
        if any(date.fromisoformat(a["start"]) <= day <= date.fromisoformat(a["end"]) for a in entries)
    }


def to_days(entries):
    """Liste de périodes -> ensemble de jours."""
    days = set()
    for a in entries:
        d, end = date.fromisoformat(a["start"]), date.fromisoformat(a["end"])
        while d <= end:
            days.add(d)
            d += timedelta(days=1)
    return days


def from_days(days):
    """Ensemble de jours -> périodes consécutives fusionnées."""
    entries = []
    for d in sorted(days):
        if entries and d - date.fromisoformat(entries[-1]["end"]) == timedelta(days=1):
            entries[-1]["end"] = d.isoformat()
        else:
            entries.append({"start": d.isoformat(), "end": d.isoformat()})
    return entries


def toggle_days(data, uid, days):
    """Bascule des jours : tout est absent -> on retire, sinon on ajoute.

    Retourne True si ces jours sont désormais des jours d'absence.
    """
    current = to_days(data.get(str(uid), []))
    days = set(days)
    now_absent = not days <= current
    current = current | days if now_absent else current - days
    if current:
        data[str(uid)] = from_days(current)
    else:
        data.pop(str(uid), None)
    return now_absent
