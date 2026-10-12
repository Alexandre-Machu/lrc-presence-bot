"""Persistance JSON (écriture atomique) pour l'état du jour et les anniversaires."""
import json
import logging
import os
import shutil
from datetime import datetime

from config.settings import BASE_DIR, DATA_DIR, TIMEZONE

log = logging.getLogger(__name__)

STATE_FILE = os.path.join(DATA_DIR, "state.json")
BIRTHDAYS_FILE = os.path.join(DATA_DIR, "birthdays.json")
META_FILE = os.path.join(DATA_DIR, "meta.json")
LEGACY_BIRTHDAYS_FILE = os.path.join(BASE_DIR, "birthdays.json")


def _read_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default
    except (json.JSONDecodeError, OSError) as e:
        log.error("Lecture de %s impossible : %s", path, e)
        return default


def _write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def today_str():
    return datetime.now(TIMEZONE).strftime("%d/%m/%Y")


class PresenceState:
    """État des présences du jour, sauvegardé à chaque modification."""

    def __init__(self):
        self.reset(save=False)

    def reset(self, save=True):
        self.date = today_str()
        self.message_id = None
        self.presence = {}   # {user_id: "Présent" | "Absent" | "Ne sait pas"}
        self.arrival = {}    # {user_id: "20:30"}
        self.maybe = {}      # {user_id: "21:30"} (pas avant)
        self.games = {}      # {user_id: [nom, ...]}
        if save:
            self.save()

    def ensure_today(self):
        """Repart de zéro si l'état date d'un autre jour."""
        if self.date != today_str():
            self.reset()

    def load(self):
        data = _read_json(STATE_FILE, None)
        if not data or data.get("date") != today_str():
            return
        self.date = data["date"]
        self.message_id = data.get("message_id")
        self.presence = data.get("presence", {})
        self.arrival = data.get("arrival", {})
        self.maybe = data.get("maybe", {})
        self.games = data.get("games", {})
        log.info("État restauré (%d réponses)", len(self.presence))

    def save(self):
        try:
            _write_json(STATE_FILE, {
                "date": self.date,
                "message_id": self.message_id,
                "presence": self.presence,
                "arrival": self.arrival,
                "maybe": self.maybe,
                "games": self.games,
            })
        except OSError as e:
            log.error("Sauvegarde de l'état impossible : %s", e)
        try:
            from utils.history import record_day
            record_day(self.date, self.presence, self.games)
        except (OSError, ValueError) as e:
            log.error("Sauvegarde de l'historique impossible : %s", e)


def load_birthdays():
    if not os.path.exists(BIRTHDAYS_FILE) and os.path.exists(LEGACY_BIRTHDAYS_FILE):
        os.makedirs(DATA_DIR, exist_ok=True)
        shutil.copy(LEGACY_BIRTHDAYS_FILE, BIRTHDAYS_FILE)
        log.info("birthdays.json migré vers data/")
    return _read_json(BIRTHDAYS_FILE, {})


def save_birthdays(data):
    _write_json(BIRTHDAYS_FILE, data)


def get_last_birthday_notice():
    """Date ISO du dernier envoi des vœux d'anniversaire."""
    return _read_json(META_FILE, {}).get("last_birthday_notice")


def set_last_birthday_notice(iso_date):
    meta = _read_json(META_FILE, {})
    meta["last_birthday_notice"] = iso_date
    _write_json(META_FILE, meta)
