import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("CHANNEL_ID", "1")


@pytest.fixture(autouse=True)
def isolated_extra_data(tmp_path, monkeypatch):
    """Historique et absences récurrentes dans un dossier temporaire (jamais dans data/)."""
    from utils import absences, history
    monkeypatch.setattr(absences, "WEEKLY_FILE", str(tmp_path / "weekly_absences.json"))
    monkeypatch.setattr(history, "HISTORY_FILE", str(tmp_path / "history.json"))
