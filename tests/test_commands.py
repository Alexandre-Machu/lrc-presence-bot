"""Appelle chaque commande et chaque menu avec une fausse interaction Discord."""
import asyncio
import json
import os
import sys
from datetime import date, datetime, timedelta
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from config.settings import TIMEZONE  # noqa: E402
from utils import absences as absences_utils  # noqa: E402
from utils import history as history_utils  # noqa: E402
from utils import storage  # noqa: E402

from cogs import absences as absences_cog  # noqa: E402
from cogs import birthdays as birthdays_cog  # noqa: E402
from cogs import info as info_cog  # noqa: E402
from cogs import presence as presence_cog  # noqa: E402
from cogs import stats as stats_cog  # noqa: E402


def today():
    return datetime.now(TIMEZONE).date()


# ---------------------------------------------------------------- fakes

class FakeResponse:
    def __init__(self):
        self.calls = []

    async def send_message(self, content=None, **kw):
        self.calls.append(("send_message", content, kw))

    async def send_modal(self, modal):
        self.calls.append(("send_modal", modal, {}))

    async def edit_message(self, **kw):
        self.calls.append(("edit_message", None, kw))

    async def defer(self, **kw):
        self.calls.append(("defer", None, kw))

    def is_done(self):
        return bool(self.calls)


class FakeFollowup:
    def __init__(self):
        self.calls = []

    async def send(self, content=None, **kw):
        self.calls.append((content, kw))


def member(uid, admin=False):
    return SimpleNamespace(
        id=uid, mention=f"<@{uid}>", bot=False,
        guild_permissions=SimpleNamespace(administrator=admin),
    )


class FakeChannel:
    def __init__(self):
        self.sent = []

    async def history(self, limit=50):
        for m in []:
            yield m

    async def send(self, content=None, **kw):
        self.sent.append((content, kw))
        return SimpleNamespace(id=4242)


def make_interaction(user, members=None, channel=None):
    members = members or {}
    guild = SimpleNamespace(
        get_member=lambda i: members.get(i),
        fetch_member=None,
    )
    return SimpleNamespace(
        user=user, guild=guild, channel=channel or FakeChannel(),
        response=FakeResponse(), followup=FakeFollowup(),
    )


def last(interaction):
    return interaction.response.calls[-1]


def text_of(interaction):
    kind, content, kw = last(interaction)
    return content if content is not None else kw.get("content")


def cog_commands(cog):
    return {c.name: c for c in cog.__cog_app_commands__}


@pytest.fixture(autouse=True)
def isolated_data(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "STATE_FILE", str(tmp_path / "state.json"))
    monkeypatch.setattr(storage, "BIRTHDAYS_FILE", str(tmp_path / "birthdays.json"))
    monkeypatch.setattr(storage, "LEGACY_BIRTHDAYS_FILE", str(tmp_path / "nope.json"))
    monkeypatch.setattr(storage, "META_FILE", str(tmp_path / "meta.json"))
    monkeypatch.setattr(absences_utils, "ABSENCES_FILE", str(tmp_path / "absences.json"))


def run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------- guide

def test_guide_matches_registered_commands():
    stub = SimpleNamespace(get_cog=lambda n: None)
    registered = set()
    for cog in (presence_cog.Presence(stub), birthdays_cog.Birthdays(stub),
                absences_cog.Absences(stub), stats_cog.Stats(stub), info_cog.Info(stub)):
        registered |= set(cog_commands(cog))
    cited = info_cog.guide_command_names()
    assert cited <= registered, f"commandes citées dans le guide mais inexistantes : {cited - registered}"
    assert registered <= cited, f"commandes absentes du guide : {registered - cited}"
    assert "lrcbirthday" in registered and "lrcaddbirthday" not in registered


def test_lrcinfo_sends_guide_embed():
    cog = info_cog.Info(None)
    inter = make_interaction(member(1))
    run(cog.lrcinfo.callback(cog, inter))
    kind, _, kw = last(inter)
    assert kind == "send_message" and kw["ephemeral"] is True
    assert len(kw["embed"].fields) >= 4


def test_lrcinfo_topics():
    from discord import app_commands
    cog = info_cog.Info(None)
    for key in info_cog.TOPICS:
        inter = make_interaction(member(1))
        run(cog.lrcinfo.callback(cog, inter, app_commands.Choice(name=key, value=key)))
        assert last(inter)[2]["embed"].fields and last(inter)[2]["ephemeral"] is True
    inter = make_interaction(member(1))
    run(cog.lrcinfo.callback(cog, inter, app_commands.Choice(name="Anniversaires", value="anniversaires")))
    text = " ".join(f.value for f in last(inter)[2]["embed"].fields)
    for expected in ("/lrcbirthday", "/lrcbirthdays", "/lrcremovebirthday", "8h05"):
        assert expected in text
    assert "lrcaddbirthday" not in text


# ---------------------------------------------------------------- anniversaires

def test_birthday_with_date_saves_for_self():
    cog = birthdays_cog.Birthdays(None)
    inter = make_interaction(member(1))
    run(cog.lrcbirthday.callback(cog, inter, "5/3", None))
    assert storage.load_birthdays() == {"1": "05/03"}
    assert "05/03" in text_of(inter)


def test_birthday_without_date_opens_modal():
    cog = birthdays_cog.Birthdays(None)
    inter = make_interaction(member(1))
    run(cog.lrcbirthday.callback(cog, inter, None, None))
    assert last(inter)[0] == "send_modal"


def test_birthday_modal_submit():
    async def go():
        modal = birthdays_cog.BirthdayModal(member(1))
        modal.date._value = "25/12"
        inter = make_interaction(member(1))
        await modal.on_submit(inter)
        return inter
    inter = run(go())
    assert storage.load_birthdays() == {"1": "25/12"}
    assert "25/12" in text_of(inter)


def test_birthday_modal_rejects_garbage():
    async def go():
        modal = birthdays_cog.BirthdayModal(member(1))
        modal.date._value = "pas une date"
        inter = make_interaction(member(1))
        await modal.on_submit(inter)
        return inter
    inter = run(go())
    assert storage.load_birthdays() == {}
    assert "invalide" in text_of(inter).lower()


@pytest.mark.parametrize("bad", ["31/02", "abc", "12-25", "1/13"])
def test_birthday_invalid_dates(bad):
    cog = birthdays_cog.Birthdays(None)
    inter = make_interaction(member(1))
    run(cog.lrcbirthday.callback(cog, inter, bad, None))
    assert storage.load_birthdays() == {}
    assert "invalide" in text_of(inter).lower()


def test_birthday_leap_day_ok():
    cog = birthdays_cog.Birthdays(None)
    inter = make_interaction(member(1))
    run(cog.lrcbirthday.callback(cog, inter, "29/02", None))
    assert storage.load_birthdays() == {"1": "29/02"}


def test_birthday_for_someone_else_needs_admin():
    cog = birthdays_cog.Birthdays(None)
    other = member(2)
    run(cog.lrcbirthday.callback(cog, make_interaction(member(1)), "01/01", other))
    assert storage.load_birthdays() == {}
    inter = make_interaction(member(9, admin=True))
    run(cog.lrcbirthday.callback(cog, inter, "01/01", other))
    assert storage.load_birthdays() == {"2": "01/01"}


def test_remove_birthday():
    storage.save_birthdays({"1": "01/01", "2": "02/02"})
    cog = birthdays_cog.Birthdays(None)
    inter = make_interaction(member(1))
    run(cog.lrcremovebirthday.callback(cog, inter, None))
    assert storage.load_birthdays() == {"2": "02/02"}
    run(cog.lrcremovebirthday.callback(cog, inter, None))
    assert "Aucun" in text_of(inter)
    run(cog.lrcremovebirthday.callback(cog, make_interaction(member(1)), member(2)))
    assert storage.load_birthdays() == {"2": "02/02"}  # pas admin : refusé


def test_list_birthdays_upcoming_only():
    t = today()
    soon = (t + timedelta(days=3)).strftime("%d/%m")
    far = (t + timedelta(days=120)).strftime("%d/%m")
    storage.save_birthdays({"1": soon, "2": far, "3": "01/01"})
    cog = birthdays_cog.Birthdays(None)
    inter = make_interaction(member(9), members={1: member(1), 2: member(2), 3: member(3)})
    run(cog.lrcbirthdays.callback(cog, inter))
    msg = inter.followup.calls[-1][0]
    assert "<@1>" in msg and "dans 3 j" in msg and "<@2>" not in msg


def test_list_birthdays_member_not_in_cache_is_fetched():
    t = today()
    storage.save_birthdays({"1": t.strftime("%d/%m")})

    async def fetch_member(uid):
        return member(uid)

    async def go():
        guild = SimpleNamespace(get_member=lambda i: None, fetch_member=fetch_member)
        inter = make_interaction(member(9))
        inter.guild = guild
        cog = birthdays_cog.Birthdays(None)
        await cog.lrcbirthdays.callback(cog, inter)
        return inter
    inter = run(go())
    assert "aujourd'hui" in inter.followup.calls[-1][0]


def test_announce_birthdays_today_only_and_remembers():
    t = today()
    storage.save_birthdays({"1": t.strftime("%d/%m"), "2": (t + timedelta(days=1)).strftime("%d/%m"), "3": "garbage"})
    channel = FakeChannel()
    channel.guild = SimpleNamespace(get_member=lambda i: member(i), fetch_member=None)
    cog = birthdays_cog.Birthdays(None)
    assert run(cog.announce_birthdays(channel)) == 1
    assert "<@1>" in channel.sent[0][0]
    assert storage.get_last_birthday_notice() == t.isoformat()


# ---------------------------------------------------------------- absences

def make_absences_cog():
    pres = presence_cog.Presence(SimpleNamespace(get_channel=lambda i: None))
    bot = SimpleNamespace(get_cog=lambda n: pres if n == "Presence" else None)
    return absences_cog.Absences(bot), pres


def test_absence_period_saved_and_prefilled():
    cog, pres = make_absences_cog()
    t = today()
    start, end = t + timedelta(days=5), t + timedelta(days=9)
    inter = make_interaction(member(1))
    run(cog.lrcabsence.callback(cog, inter, start.strftime("%d/%m/%Y"), end.strftime("%d/%m/%Y")))
    saved = absences_utils.load_absences()
    assert saved == {"1": [{"start": start.isoformat(), "end": end.isoformat()}]}
    pres.state.reset(save=False)
    # jour J : pré-rempli absent par le message du matin
    absences_utils.save_absences({"1": [{"start": t.isoformat(), "end": t.isoformat()}]})
    pres.apply_planned_absences()
    assert pres.state.presence == {"1": "Absent"}


def test_absence_errors():
    cog, _ = make_absences_cog()
    t = today()
    for args in [("abc", None), ("31/02", None),
                 ((t + timedelta(days=5)).strftime("%d/%m/%Y"), (t + timedelta(days=2)).strftime("%d/%m/%Y"))]:
        inter = make_interaction(member(1))
        run(cog.lrcabsence.callback(cog, inter, *args))
        assert last(inter)[0] == "send_message"
    assert absences_utils.load_absences() == {}


def test_absence_without_args_opens_calendar():
    cog, _ = make_absences_cog()
    inter = make_interaction(member(1))
    run(cog.lrcabsence.callback(cog, inter, None, None))
    kind, content, kw = last(inter)
    assert kind == "send_message" and kw["ephemeral"] and kw["view"] is not None
    labels = [getattr(c, "label", None) for c in kw["view"].children]
    assert "Toute la semaine" in labels and "Terminé" in labels
    assert any(isinstance(c, absences_cog.WeeklySelect) for c in kw["view"].children)


def test_calendar_toggle_day_and_week_and_today():
    async def go():
        cog, pres = make_absences_cog()
        t = today()
        inter = make_interaction(member(1))
        monday = absences_cog.monday_of(t)
        # un jour futur
        future = t + timedelta(days=2)
        await cog.toggle(inter, [future], absences_cog.monday_of(future))
        assert absences_utils.load_absences()["1"] == [{"start": future.isoformat(), "end": future.isoformat()}]
        # le retirer
        await cog.toggle(inter, [future], absences_cog.monday_of(future))
        assert absences_utils.load_absences() == {}
        # aujourd'hui => présent marqué Absent, puis annulé
        await cog.toggle(inter, [t], monday)
        assert pres.state.presence.get("1") == "Absent"
        await cog.toggle(inter, [t], monday)
        assert "1" not in pres.state.presence
        # navigation / vue : jours passés désactivés
        view = cog.panel_view(1, monday)
        day_buttons = [c for c in view.children if isinstance(c, absences_cog.DayButton)]
        assert len(day_buttons) == 7
        assert all(b.disabled == (b.day < t) for b in day_buttons)
        prev = [c for c in view.children if isinstance(c, absences_cog.NavButton) and c.delta == -1][0]
        assert prev.disabled is True  # pas de retour avant la semaine en cours
    run(go())


def test_list_and_remove_absences():
    cog, _ = make_absences_cog()
    t = today()
    s = t + timedelta(days=3)
    absences_utils.save_absences({"1": [{"start": s.isoformat(), "end": s.isoformat()}],
                                  "2": [{"start": s.isoformat(), "end": s.isoformat()}]})
    inter = make_interaction(member(1))
    run(cog.lrcabsences.callback(cog, inter, False))
    assert "<@1>" in text_of(inter) and "<@2>" not in text_of(inter)
    inter = make_interaction(member(1))
    run(cog.lrcabsences.callback(cog, inter, True))
    assert "<@2>" in text_of(inter)
    choices = run(cog.absence_autocomplete(make_interaction(member(1)), ""))
    assert [c.value for c in choices] == [s.isoformat()]
    run(cog.lrcremoveabsence.callback(cog, make_interaction(member(1)), s.isoformat()))
    assert "1" not in absences_utils.load_absences() and "2" in absences_utils.load_absences()


# ---------------------------------------------------------------- présence

def view_children(cog):
    view = presence_cog.PresenceView(cog)
    return view, {type(c).__name__: c for c in view.children}


def new_presence():
    return presence_cog.Presence(SimpleNamespace(get_channel=lambda i: None))


def select(child, *values):
    child._values = list(values)
    return child


def test_presence_view_has_all_components():
    async def go():
        view, kids = view_children(new_presence())
        assert set(kids) == {"PresenceSelect", "ArrivalTimeSelect", "GameSelect", "AbsencePanelButton"}
        ids = [c.custom_id for c in view.children]
        assert len(ids) == len(set(ids))  # custom_id uniques (vue persistante)
        n_options = len(kids["ArrivalTimeSelect"].options)
        assert n_options == 9
    run(go())


def test_arrival_slots_match_requested_list():
    assert presence_cog.ARRIVAL_SLOTS == [
        "19:30", "20:00", "20:30", "21:00", "21:30", "22:00", "22:30", "23:00"]


def test_arrival_select_first_option_is_manual_entry():
    async def go():
        _, kids = view_children(new_presence())
        options = kids["ArrivalTimeSelect"].options
        assert options[0].label == "Entrer manuellement" and options[0].value == presence_cog.MANUAL_VALUE
        assert [o.label for o in options[1:]] == [
            "19h30", "20h00", "20h30", "21h00", "21h30", "22h00", "22h30", "23h00"]
    run(go())


def test_present_absent_maybe_flow_keeps_games():
    async def go():
        cog = new_presence()
        _, kids = view_children(cog)
        for v in ("present",):
            inter = make_interaction(member(1))
            await select(kids["PresenceSelect"], v).callback(inter)
        inter = make_interaction(member(1))
        await select(kids["GameSelect"], "CS2", "OW").callback(inter)
        inter = make_interaction(member(1))
        await select(kids["ArrivalTimeSelect"], "21:30").callback(inter)
        assert cog.state.arrival == {"1": "21:30"} and cog.state.games == {"1": ["CS2", "OW"]}
        # absent : les jeux sont CONSERVÉS
        inter = make_interaction(member(1))
        await select(kids["PresenceSelect"], "absent").callback(inter)
        assert cog.state.presence == {"1": "Absent"} and cog.state.games == {"1": ["CS2", "OW"]}
        assert "1" not in cog.state.arrival
        # puis peut-être : l'heure devient « pas avant »
        inter = make_interaction(member(1))
        await select(kids["PresenceSelect"], "maybe").callback(inter)
        inter = make_interaction(member(1))
        await select(kids["ArrivalTimeSelect"], "22:15").callback(inter)
        assert cog.state.maybe == {"1": "22:15"}
        desc = cog.build_embed().description
        assert "pas avant 22h15" in desc
        return cog
    run(go())


def test_games_of_absent_not_counted():
    async def go():
        cog = new_presence()
        cog.state.presence.update({"1": "Absent", "2": "Présent"})
        cog.state.games.update({"1": ["CS2"], "2": ["CS2"]})
        desc = cog.build_embed().description
        assert "CS2 : 1" in desc
    run(go())


def test_time_or_games_without_presence_gives_hint():
    async def go():
        cog = new_presence()
        _, kids = view_children(cog)
        inter = make_interaction(member(5))
        await select(kids["ArrivalTimeSelect"], "20:30").callback(inter)
        assert inter.followup.calls and "présence" in inter.followup.calls[0][0]
        assert last(inter)[0] == "edit_message"
    run(go())


def test_exact_time_modal():
    async def go():
        cog = new_presence()
        cog.state.presence["1"] = "Présent"
        for raw, expected in [("21:40", "21:40"), ("21h40", "21:40"), ("9.05", "09:05")]:
            modal = presence_cog.ExactTimeModal(cog)
            modal.heure._value = raw
            inter = make_interaction(member(1))
            await modal.on_submit(inter)
            assert cog.state.arrival["1"] == expected
            assert last(inter)[0] == "edit_message"
        assert "21h40" not in cog.build_embed().description  # dernière valeur 09:05
        assert "09h05" in cog.build_embed().description
        modal = presence_cog.ExactTimeModal(cog)
        modal.heure._value = "25:99"
        inter = make_interaction(member(1))
        await modal.on_submit(inter)
        assert cog.state.arrival["1"] == "09:05"  # inchangé
        assert "invalide" in text_of(inter).lower()
    run(go())


def test_manual_option_opens_modal_and_resets_menu():
    async def go():
        cog = new_presence()
        _, kids = view_children(cog)
        edits = []

        async def edit(**kw):
            edits.append(kw)

        inter = make_interaction(member(1))
        inter.message = SimpleNamespace(edit=edit)
        await select(kids["ArrivalTimeSelect"], presence_cog.MANUAL_VALUE).callback(inter)
        assert last(inter)[0] == "send_modal"
        assert isinstance(last(inter)[1], presence_cog.ExactTimeModal)
        assert edits and edits[0]["view"] is not None   # menu remis à zéro
        assert cog.state.arrival == {}                  # rien d'enregistré tant que le formulaire n'est pas validé
    run(go())


def test_exact_time_for_maybe_is_not_before():
    async def go():
        cog = new_presence()
        cog.state.presence["1"] = "Ne sait pas"
        modal = presence_cog.ExactTimeModal(cog)
        modal.heure._value = "22h30"
        await modal.on_submit(make_interaction(member(1)))
        assert cog.state.maybe == {"1": "22:30"} and cog.state.arrival == {}
    run(go())


def test_state_survives_restart():
    async def go():
        cog = new_presence()
        cog.state.presence["1"] = "Présent"
        cog.state.arrival["1"] = "21:40"
        cog.state.save()
        again = new_presence()
        again.state.load()
        assert again.state.arrival == {"1": "21:40"}
    run(go())


def test_lrcreset_admin_flow_and_permission_decorator():
    async def go():
        cog = new_presence()
        cog.state.presence["1"] = "Présent"
        channel = FakeChannel()
        inter = make_interaction(member(9, admin=True), channel=channel)
        await cog.lrcreset.callback(cog, inter)
        assert channel.sent and cog.state.presence == {}
        assert cog.state.message_id == 4242
        assert inter.followup.calls
    run(go())
    cog = new_presence()
    perms = cog.lrcreset.checks
    assert perms, "lrcreset doit exiger les droits administrateur"


def test_birthday_and_absence_commands_open_to_everyone():
    assert not birthdays_cog.Birthdays(None).lrcbirthday.checks
    assert not absences_cog.Absences(None).lrcabsence.checks


# ---------------------------------------------------------------- nettoyage

def test_cleanup_removes_old_birthday_wishes_but_keeps_todays():
    bot_user = SimpleNamespace(id=1)
    cog = presence_cog.Presence(SimpleNamespace(user=bot_user, get_channel=lambda i: None))
    now = datetime.now(TIMEZONE)
    deleted = []

    def msg(name, content, created_at, author=bot_user):
        async def delete():
            deleted.append(name)
        return SimpleNamespace(author=author, content=content, embeds=[], created_at=created_at, delete=delete)

    wish = f"{birthdays_cog.BIRTHDAY_PREFIX} <@5> !** 🎂"
    messages = [
        msg("hier", wish, now - timedelta(days=1)),
        msg("aujourdhui", wish, now),
        msg("humain", wish, now - timedelta(days=3), author=SimpleNamespace(id=2)),
        msg("autre", "Bonjour", now - timedelta(days=3)),
    ]

    class Channel(FakeChannel):
        async def history(self, limit=50):
            for m in messages:
                yield m

    run(cog.clear_old_presence_messages(Channel()))
    assert deleted == ["hier"]


# ---------------------------------------------------------------- absences récurrentes

def test_weekly_utils():
    data = {}
    absences_utils.set_weekly(data, 1, [3, 0, 3])
    assert data == {"1": [0, 3]}
    assert absences_utils.weekly_label(data["1"]) == "lundi, jeudi"
    thursday = date(2026, 10, 15)
    assert absences_utils.weekly_absent_on(data, thursday) == {"1"}
    assert absences_utils.weekly_absent_on(data, thursday + timedelta(days=1)) == set()
    absences_utils.set_weekly(data, 1, [])
    assert data == {}


def test_weekly_absence_prefilled_in_morning():
    pres = new_presence()
    absences_utils.save_weekly({"7": [today().weekday()], "8": [(today().weekday() + 1) % 7]})
    pres.state.reset(save=False)
    pres.apply_planned_absences()
    assert pres.state.presence == {"7": "Absent"}


def test_calendar_weekly_select_and_today():
    async def go():
        cog, pres = make_absences_cog()
        t = today()
        monday = absences_cog.monday_of(t)
        inter = make_interaction(member(1))
        # cocher le jour de la semaine d'aujourd'hui => absent tout de suite
        await cog.update_weekly(inter, [t.weekday()], monday)
        assert absences_utils.load_weekly() == {"1": [t.weekday()]}
        assert pres.state.presence.get("1") == "Absent"
        assert "Chaque semaine" in last(inter)[2]["content"]
        # le jour apparaît avec 🔁 et n'est plus cliquable ; le menu est pré-coché
        view = cog.panel_view(1, monday)
        day = [c for c in view.children if isinstance(c, absences_cog.DayButton) and c.day == t][0]
        assert day.disabled and str(day.emoji) == "🔁"
        weekly = [c for c in view.children if isinstance(c, absences_cog.WeeklySelect)][0]
        assert [o.value for o in weekly.options if o.default] == [str(t.weekday())]
        # décocher => plus absent
        await cog.update_weekly(make_interaction(member(1)), [], monday)
        assert absences_utils.load_weekly() == {}
        assert "1" not in pres.state.presence
    run(go())


def test_weekly_removed_keeps_one_off_absence_today():
    async def go():
        cog, pres = make_absences_cog()
        t = today()
        absences_utils.save_absences({"1": [{"start": t.isoformat(), "end": t.isoformat()}]})
        await cog.update_weekly(make_interaction(member(1)), [t.weekday()], absences_cog.monday_of(t))
        await cog.update_weekly(make_interaction(member(1)), [], absences_cog.monday_of(t))
        assert pres.state.presence.get("1") == "Absent"
    run(go())


def test_list_absences_shows_weekly():
    cog, _ = make_absences_cog()
    absences_utils.save_weekly({"1": [3]})
    inter = make_interaction(member(1))
    run(cog.lrcabsences.callback(cog, inter, False))
    assert "chaque jeudi" in text_of(inter)


# ---------------------------------------------------------------- historique et stats

def test_history_recorded_on_save_only_with_answers():
    state = storage.PresenceState()
    state.save()
    assert history_utils.load_history() == {}
    state.presence = {"1": "Présent", "2": "Absent"}
    state.games = {"1": ["Valorant"]}
    state.save()
    iso = today().isoformat()
    assert history_utils.load_history()[iso]["presence"] == {"1": "Présent", "2": "Absent"}


def test_compute_stats():
    history = {
        "2026-10-01": {"presence": {"1": "Présent", "2": "Présent", "3": "Absent"},
                       "games": {"1": ["LoL"], "2": ["LoL", "Valorant"], "3": ["LoL"]}},
        "2026-10-02": {"presence": {"1": "Présent", "2": "Ne sait pas"}, "games": {"1": ["Valorant"]}},
        "2026-10-03": {"presence": {"3": "Absent"}, "games": {}},
    }
    s = history_utils.compute_stats(history)
    assert s["nights"] == 2
    assert s["average"] == 1.5
    assert s["record"] == ("2026-10-01", 2)
    assert s["top_players"] == [("1", 2), ("2", 1)]
    assert s["top_games"] == [("LoL", 2), ("Valorant", 2)]  # le jeu d'un absent ne compte pas
    assert s["first_day"] == "2026-10-01"
    assert history_utils.compute_stats(history, since=date(2026, 10, 2))["nights"] == 1


def test_lrcstats_command():
    cog = stats_cog.Stats(None)
    inter = make_interaction(member(1))
    run(cog.lrcstats.callback(cog, inter, None))
    kind, _, kw = last(inter)
    assert kind == "send_message" and "Pas encore" in kw["embed"].description
    assert "ephemeral" not in kw  # visible par tous

    t = today()
    history_utils._write_json(history_utils.HISTORY_FILE, {
        t.isoformat(): {"presence": {"1": "Présent", "2": "Présent"}, "games": {"1": ["LoL"]}},
        (t - timedelta(days=60)).isoformat(): {"presence": {"3": "Présent"}, "games": {}},
    })
    inter = make_interaction(member(1))
    run(cog.lrcstats.callback(cog, inter, None))  # 30 jours par défaut
    embed = last(inter)[2]["embed"]
    text = "\n".join(f.value for f in embed.fields)
    assert "<@1>" in text and "<@3>" not in text and "LoL" in text
    assert last(inter)[2]["allowed_mentions"].users is False
