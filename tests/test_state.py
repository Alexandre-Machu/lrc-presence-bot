from utils import storage
from utils.storage import PresenceState


def test_state_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "STATE_FILE", str(tmp_path / "state.json"))
    s = PresenceState()
    s.presence["1"] = "Présent"
    s.games["1"] = ["CS2"]
    s.message_id = 42
    s.save()
    loaded = PresenceState()
    loaded.load()
    assert loaded.presence == {"1": "Présent"} and loaded.games == {"1": ["CS2"]}
    assert loaded.message_id == 42


def test_stale_state_is_ignored(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "STATE_FILE", str(tmp_path / "state.json"))
    s = PresenceState()
    s.presence["1"] = "Présent"
    s.date = "01/01/2020"
    s.save()
    loaded = PresenceState()
    loaded.load()
    assert loaded.presence == {}


def test_corrupt_state_file(tmp_path, monkeypatch):
    path = tmp_path / "state.json"
    path.write_text("{pas du json")
    monkeypatch.setattr(storage, "STATE_FILE", str(path))
    s = PresenceState()
    s.load()
    assert s.presence == {}
