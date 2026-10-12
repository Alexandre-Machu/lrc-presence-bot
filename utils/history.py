"""Historique des soirées : {"2026-10-12": {"presence": {...}, "games": {...}, "arrival": {...}}} et stats."""
import os
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta

from config.settings import DATA_DIR
from utils.storage import _read_json, _write_json

HISTORY_FILE = os.path.join(DATA_DIR, "history.json")
PRESENT, MAYBE = "Présent", "Ne sait pas"
STREAK_MIN = 3  # 🔥 affiché à partir de 3 soirées d'affilée


def load_history():
    return _read_json(HISTORY_FILE, {})


def record_day(day_fr, presence, games, arrival=None):
    """Enregistre (ou remplace) la journée 'JJ/MM/AAAA'. Rien si personne n'a répondu."""
    if not presence:
        return
    iso = datetime.strptime(day_fr, "%d/%m/%Y").date().isoformat()
    history = load_history()
    history[iso] = {
        "presence": dict(presence),
        "games": {u: list(g) for u, g in games.items()},
        "arrival": dict(arrival or {}),
    }
    _write_json(HISTORY_FILE, history)


def presents_of(day):
    return [u for u, s in day.get("presence", {}).items() if s == PRESENT]


def in_range(history, since: date = None, until: date = None):
    return {
        d: v for d, v in history.items()
        if (since is None or date.fromisoformat(d) >= since) and (until is None or date.fromisoformat(d) <= until)
    }


def compute_stats(history, since: date = None, until: date = None):
    """Stats des soirées entre `since` et `until` (incluses)."""
    days = in_range(history, since, until)
    attendance, games = Counter(), Counter()
    nights, record = 0, None
    for iso, day in sorted(days.items()):
        presents = presents_of(day)
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


# ---- séries 🔥 : soirées d'affilée (les jours sans aucun présent ne cassent pas la série)

def session_days(history):
    return sorted(d for d, v in history.items() if presents_of(v))


def current_streaks(history, today_iso):
    """{uid: n} pour les présents du jour : nombre de soirées d'affilée, aujourd'hui compris."""
    sessions = [d for d in session_days(history) if d <= today_iso]
    if not sessions or sessions[-1] != today_iso:
        return {}
    streaks = {}
    for uid in presents_of(history[today_iso]):
        n = 0
        for d in reversed(sessions):
            if uid not in presents_of(history[d]):
                break
            n += 1
        streaks[uid] = n
    return streaks


def best_streaks(history):
    """{uid: plus longue série} sur la période donnée."""
    best, running = defaultdict(int), defaultdict(int)
    for d in session_days(history):
        presents = set(presents_of(history[d]))
        for uid in set(running) | presents:
            running[uid] = running[uid] + 1 if uid in presents else 0
            best[uid] = max(best[uid], running[uid])
    return dict(best)


# ---- récap du mois

MONTHS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet",
          "août", "septembre", "octobre", "novembre", "décembre"]


def month_bounds(year, month):
    start = date(year, month, 1)
    end = (date(year + month // 12, month % 12 + 1, 1)) - timedelta(days=1)
    return start, end


def previous_month(day: date):
    first = day.replace(day=1) - timedelta(days=1)
    return first.year, first.month


def arrival_minutes(value):
    """'21:40' -> 1300 ; après minuit compte comme la même soirée ('00:30' -> 1470)."""
    try:
        h, m = (int(x) for x in value.split(":"))
    except (ValueError, AttributeError):
        return None
    return (h + 24 if h < 6 else h) * 60 + m


def fmt_minutes(total):
    total = round(total) % (24 * 60)
    return f"{total // 60}h{total % 60:02d}"


def month_titles(days):
    """Titres rigolos du mois : [(titre, uid, détail), ...]."""
    titles = []
    arrivals, maybes, game_sets = defaultdict(list), Counter(), defaultdict(set)
    for day in days.values():
        for uid, status in day.get("presence", {}).items():
            if status == MAYBE:
                maybes[uid] += 1
            if status != PRESENT:
                continue
            minutes = arrival_minutes(day.get("arrival", {}).get(uid))
            if minutes is not None:
                arrivals[uid].append(minutes)
            game_sets[uid].update(day.get("games", {}).get(uid, []))

    averages = {u: sum(v) / len(v) for u, v in arrivals.items() if len(v) >= 3}
    if averages:
        late = max(averages, key=averages.get)
        titles.append(("🦉 Le couche-tard", late, f"arrive en moyenne à {fmt_minutes(averages[late])}"))
        early = min(averages, key=averages.get)
        if early != late:
            titles.append(("🐓 Le lève-tôt", early, f"arrive en moyenne à {fmt_minutes(averages[early])}"))
    if maybes and maybes.most_common(1)[0][1] >= 2:
        uid, n = maybes.most_common(1)[0]
        titles.append(("👻 Le fantôme", uid, f"{n} « Ne sait pas »"))
    variety = {u: len(g) for u, g in game_sets.items() if len(g) >= 3}
    if variety:
        uid = max(variety, key=variety.get)
        titles.append(("🎲 Le touche-à-tout", uid, f"{variety[uid]} jeux différents"))
    streaks = {u: n for u, n in best_streaks(days).items() if n >= STREAK_MIN}
    if streaks:
        uid = max(streaks, key=streaks.get)
        titles.append(("🔥 Le plus assidu", uid, f"{streaks[uid]} soirées d'affilée"))
    return titles


def month_recap(history, year, month):
    start, end = month_bounds(year, month)
    days = in_range(history, start, end)
    stats = compute_stats(history, start, end)
    return stats, month_titles(days)
