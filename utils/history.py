"""Historique des soirées : {"2026-10-12": {"presence": {...}, "games": {...}}} et stats."""
import os
from collections import Counter
from datetime import date, datetime

from config.settings import DATA_DIR
from utils.storage import _read_json, _write_json

HISTORY_FILE = os.path.join(DATA_DIR, "history.json")
PRESENT = "Présent"


def load_history():
    return _read_json(HISTORY_FILE, {})


def record_day(day_fr, presence, games):
    """Enregistre (ou remplace) la journée 'JJ/MM/AAAA'. Rien si personne n'a répondu."""
    if not presence:
        return
    iso = datetime.strptime(day_fr, "%d/%m/%Y").date().isoformat()
    history = load_history()
    history[iso] = {"presence": dict(presence), "games": {u: list(g) for u, g in games.items()}}
    _write_json(HISTORY_FILE, history)


def compute_stats(history, since: date = None):
    """Stats des soirées depuis `since` (incluse), ou depuis le début."""
    days = {d: v for d, v in history.items() if since is None or date.fromisoformat(d) >= since}
    attendance, games = Counter(), Counter()
    nights, record = 0, None
    for iso, day in sorted(days.items()):
        presents = [u for u, s in day.get("presence", {}).items() if s == PRESENT]
        if not presents:
            continue
        nights += 1
        attendance.update(presents)
        for uid in presents:
            games.update(day.get("games", {}).get(uid, []))
        if record is None or len(presents) > record[1]:
            record = (iso, len(presents))
    return {
        "nights": nights,
        "average": sum(attendance.values()) / nights if nights else 0,
        "record": record,
        "top_players": attendance.most_common(10),
        "top_games": games.most_common(5),
        "first_day": min(history) if history else None,
    }
