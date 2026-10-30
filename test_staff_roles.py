"""Staff HQ Discord roles: apply only what Discord accepts, and record what the bot sees."""

import asyncio
import os
import tempfile
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch
from zoneinfo import ZoneInfo

os.environ.setdefault("DB_PATH", os.path.join(tempfile.gettempdir(), "pimp-staff-roles-test.db"))

import discord

import bot


class Perms:
    def __init__(self, manage=False, audit=False):
        self.manage_roles = manage
        self.view_audit_log = audit


class Role:
    def __init__(self, rid, name, position=1, managed=False, color=0, members=None):
        self.id = rid
        self.name = name
        self.position = position
        self.managed = managed
        self.color = discord.Colour(color)
        self.members = list(members or [])

    def is_default(self):
        return self.name == "@everyone"


class Member:
    def __init__(self, uid, name, roles, guild=None, is_bot=False):
        self.id = uid
        self.display_name = name
        self.name = name
        self.roles = list(roles)
        self.guild = guild
        self.bot = is_bot
        self.added = []
        self.removed = []

    async def add_roles(self, role, reason=None):
        self.added.append((role.id, reason))
        if all(item.id != role.id for item in self.roles):
            self.roles.append(role)
        if all(item.id != self.id for item in role.members):
            role.members.append(self)

    async def remove_roles(self, role, reason=None):
        self.removed.append((role.id, reason))
        self.roles = [item for item in self.roles if item.id != role.id]
        role.members = [item for item in role.members if item.id != self.id]


class Guild:
    def __init__(self, roles, members, me, gid=42):
        self.id = gid
        self.roles = roles
        self.members = members
        self.me = me
        self.entries = []
        self.created = []
        for member in members:
            member.guild = self

    def get_role(self, rid):
        for role in self.roles:
            if int(role.id) == int(rid):
                return role
        return None

    def get_member(self, uid):
        for member in self.members:
            if int(member.id) == int(uid):
                return member
        return None

    async def fetch_member(self, uid):
        found = self.get_member(uid)
        if found is None:
            raise discord.NotFound(Mock(status=404, reason="Not Found"), "missing")
        return found

    async def create_role(self, name, colour=None, reason=None):
        self.created.append(name)
        raise discord.Forbidden(Mock(status=403, reason="Forbidden"), "no")

    def audit_logs(self, limit=8, action=None):
        async def gen():
            for entry in self.entries:
                yield entry
        return gen()


class Store:
    def __init__(self):
        self.data = {}

    def get(self, gid, key):
        return self.data.get((int(gid), key))

    def set(self, gid, key, value):
        if value is None:
            self.data.pop((int(gid), key), None)
        else:
            self.data[(int(gid), key)] = value


class StaffRoleTests(unittest.TestCase):
    def setUp(self):
        self.store = Store()
        self.patches = [
            patch.object(bot, "get_setting", self.store.get),
            patch.object(bot, "set_setting", self.store.set),
            patch.object(bot, "staff_gid", lambda gid=None: int(gid) if gid is not None else 42),
            patch.object(bot, "crew_display_name", lambda uid, gid=None: {5: "Levi", 7: "Pimpin Levi"}.get(int(uid), str(uid))),
        ]
        for item in self.patches:
            item.start()
        bot._ROLE_ACTOR.clear()

    def tearDown(self):
        for item in self.patches:
            item.stop()

    def test_marks_are_short_and_split_on_the_role_name(self):
        self.assertEqual(bot.role_mark("Head Admin"), "HA")
        self.assertEqual(bot.role_mark("pimpin lawyer"), "PL")
        self.assertEqual(bot.role_mark("PIMPIN-MEMBERS"), "PM")
        self.assertEqual(bot.role_mark("PIMPIN_TWOTONE"), "PT")
        self.assertEqual(bot.role_mark("VERIFIED_PIMP"), "VP")
        self.assertEqual(len(bot.role_mark("Head Admin")), 2)

    def test_clock_is_america_chicago(self):
        self.assertEqual(bot.role_change_when("2026-10-30T21:14:00+00:00"), "Oct 30, 4:14 PM Central")
        self.assertEqual(bot.role_change_when("2026-01-15T00:05:00+00:00"), "Jan 14, 6:05 PM Central")
        bot.role_log_add(42, 10, "Head Admin", 5, "Levi", "add", "Pimpin Levi", 7)
        raw = bot.role_log_load(42)[0]["at"]
        when = datetime.fromisoformat(raw)
        chicago = ZoneInfo("America/Chicago")
        self.assertEqual(when.utcoffset(), datetime.now(chicago).utcoffset())
        shown = bot.role_changes_public(42)[0]
        self.assertEqual(shown["act"], "add")
        self.assertEqual(shown["who"], "Levi")
        self.assertEqual(shown["by"], "Pimpin Levi")
        self.assertTrue(shown["when"].endswith("Central"))

    def test_same_change_is_not_logged_twice_and_a_name_can_fill_in(self):
        bot.role_log_add(42, 10, "Head Admin", 5, "Levi", "add", "", 0)
        bot.role_log_add(42, 10, "Head Admin", 5, "Levi", "add", "Marshall", 8)
        rows = bot.role_log_load(42)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["by"], "Marshall")
        bot.role_log_add(42, 10, "Head Admin", 5, "Levi", "remove", "Marshall", 8)
        self.assertEqual(len(bot.role_log_load(42)), 2)

    def test_no_manage_roles_does_not_call_discord_or_claim_success(self):
        role = Role(10, "Head Admin", position=5, color=0xF0B429)
        member = Member(5, "Levi", [])
        guild = Guild([role], [member], SimpleNamespace(top_role=Role(1, "bot", position=20), guild_permissions=Perms(False)))
        with patch.object(bot, "_guild_for", return_value=guild):
            ok, note = asyncio.run(bot.switch_discord_role(42, 10, 5, True, 7))
        self.assertFalse(ok)
        self.assertIn("does not have Manage Roles", note)
        self.assertIn("not changed", note)
        self.assertEqual(member.added, [])
        self.assertEqual(bot.role_log_load(42), [])
        self.assertIn("will not reach Discord", bot.bot_manage_note(guild))

    def test_role_above_the_bot_is_refused_before_discord(self):
        role = Role(10, "PIMPIN_LEGEND", position=30)
        member = Member(5, "Levi", [])
        guild = Guild([role], [member], SimpleNamespace(top_role=Role(1, "bot", position=10), guild_permissions=Perms(True)))
        with patch.object(bot, "_guild_for", return_value=guild):
            ok, note = asyncio.run(bot.switch_discord_role(42, 10, 5, True, 7))
        self.assertFalse(ok)
        self.assertIn("not above", note)
        self.assertIn("not changed", note)
        self.assertEqual(member.added, [])

    def test_give_and_take_record_the_person_who_used_the_desk(self):
        role = Role(10, "Head Admin", position=4, color=0xF0B429)
        member = Member(5, "Levi", [])
        guild = Guild([role], [member], SimpleNamespace(top_role=Role(1, "bot", position=10), guild_permissions=Perms(True)))
        with patch.object(bot, "_guild_for", return_value=guild):
            ok, note = asyncio.run(bot.switch_discord_role(42, 10, 5, True, 7))
            self.assertTrue(ok)
            self.assertEqual(note, "Head Admin is on Levi.")
            self.assertEqual(member.added, [(10, "Staff HQ")])
            again_ok, again = asyncio.run(bot.switch_discord_role(42, 10, 5, True, 7))
            self.assertTrue(again_ok)
            self.assertIn("already has", again)
            self.assertEqual(len(member.added), 1)
            off_ok, off = asyncio.run(bot.switch_discord_role(42, 10, 5, False, 7))
        self.assertTrue(off_ok)
        self.assertEqual(off, "Head Admin is off Levi.")
        self.assertEqual(member.removed, [(10, "Staff HQ")])
        rows = bot.role_log_load(42)
        self.assertEqual([(row["act"], row["by"]) for row in rows], [("remove", "Pimpin Levi"), ("add", "Pimpin Levi")])

    def test_discord_refusal_after_the_check_is_not_success(self):
        role = Role(10, "VERIFIED_PIMP", position=2)
        member = Member(5, "Levi", [])

        async def refuse(role, reason=None):
            raise discord.Forbidden(Mock(status=403, reason="Forbidden"), "no")

        member.add_roles = refuse
        guild = Guild([role], [member], SimpleNamespace(top_role=Role(1, "bot", position=10), guild_permissions=Perms(True)))
        with patch.object(bot, "_guild_for", return_value=guild):
            ok, note = asyncio.run(bot.switch_discord_role(42, 10, 5, True, 7))
        self.assertFalse(ok)
        self.assertIn("not changed", note)
        self.assertNotIn("is on", note)
        self.assertEqual(bot.role_log_load(42), [])

    def test_missing_person_is_not_a_success(self):
        role = Role(10, "Head Admin", position=2)
        guild = Guild([role], [], SimpleNamespace(top_role=Role(1, "bot", position=10), guild_permissions=Perms(True)))
        with patch.object(bot, "_guild_for", return_value=guild):
            ok, note = asyncio.run(bot.switch_discord_role(42, 10, 5, True, 7))
        self.assertFalse(ok)
        self.assertIn("not in the server", note)
        self.assertIn("not changed", note)

    def test_replace_says_when_someone_else_could_not_be_cleared(self):
        role = Role(10, "Head Admin", position=2)
        keep = Member(6, "Sam", [])
        target = Member(5, "Levi", [])
        role.members = [keep]
        keep.roles = [role]

        async def stuck(role, reason=None):
            raise discord.Forbidden(Mock(status=403, reason="Forbidden"), "no")

        keep.remove_roles = stuck
        guild = Guild([role], [keep, target], SimpleNamespace(top_role=Role(1, "bot", position=10), guild_permissions=Perms(True)))
        with patch.object(bot, "_guild_for", return_value=guild), patch.object(bot, "MEMBERS_INTENT", True):
            note = asyncio.run(bot.assign_discord_role(42, 10, 5, True, 7))
        self.assertIn("is on Levi", note)
        self.assertIn("Could not take it off 1 other person", note)
        self.assertTrue(bot.role_note_warn(note))

    def test_desk_label_does_not_rename_discord(self):
        role = Role(10, "PIMPIN LEVI", position=2, color=0x7B3FE4)
        guild = Guild([role], [], SimpleNamespace(top_role=Role(1, "bot", position=10), guild_permissions=Perms(True)))
        with patch.object(bot, "_guild_for", return_value=guild):
            ok, note = bot.role_label_set(42, 10, "Levi's chair")
            rows = bot.discord_role_rows(42)
        self.assertTrue(ok)
        self.assertEqual(role.name, "PIMPIN LEVI")
        self.assertEqual(rows[0]["label"], "Levi's chair")
        self.assertEqual(rows[0]["name"], "PIMPIN LEVI")
        self.assertEqual(rows[0]["mark"], "LC")
        self.assertEqual(rows[0]["color"], "#7b3fe4")
        with patch.object(bot, "_guild_for", return_value=guild):
            cleared, _note = bot.role_label_set(42, 10, "")
            rows = bot.discord_role_rows(42)
        self.assertTrue(cleared)
        self.assertEqual(rows[0]["label"], "PIMPIN LEVI")

    def test_gateway_records_add_and_remove_with_the_audit_name(self):
        role = Role(11, "pimpin lawyer", position=3)
        other = Role(12, "VERIFIED_PIMP", position=2)
        before = Member(5, "Levi", [other])
        after = Member(5, "Levi", [other, role])
        guild = Guild([role, other], [after], SimpleNamespace(
            top_role=Role(1, "bot", position=10), guild_permissions=Perms(True, audit=True)))
        before.guild = guild
        after.guild = guild
        guild.entries = [SimpleNamespace(
            target=SimpleNamespace(id=5),
            user=SimpleNamespace(id=8, display_name="Marshall", name="marshall"),
            created_at=datetime.now(timezone.utc),
            before=SimpleNamespace(roles=[]),
            after=SimpleNamespace(roles=[SimpleNamespace(id=11)]),
        )]
        asyncio.run(bot.note_member_role_edits(before, after))
        added = bot.role_log_load(42)
        self.assertEqual(len(added), 1)
        self.assertEqual(added[0]["act"], "add")
        self.assertEqual(added[0]["by"], "Marshall")
        self.assertEqual(added[0]["role_name"], "pimpin lawyer")
        self.assertTrue(added[0]["at"].startswith("20"))
        when = datetime.fromisoformat(added[0]["at"])
        self.assertEqual(when.utcoffset(), datetime.now(ZoneInfo("America/Chicago")).utcoffset())

        later = Member(5, "Levi", [other])
        later.guild = guild
        guild.entries = [SimpleNamespace(
            target=SimpleNamespace(id=5),
            user=SimpleNamespace(id=8, display_name="Marshall", name="marshall"),
            created_at=datetime.now(timezone.utc),
            before=SimpleNamespace(roles=[SimpleNamespace(id=11)]),
            after=SimpleNamespace(roles=[]),
        )]
        asyncio.run(bot.note_member_role_edits(after, later))
        acts = [row["act"] for row in bot.role_log_load(42)]
        self.assertEqual(acts, ["remove", "add"])

    def test_page_lists_give_take_and_a_desk_label(self):
        page = bot.STAFF_HTML
        self.assertIn("Give role", page)
        self.assertIn("Take role", page)
        self.assertIn("Save label", page)
        self.assertIn("rolemark", page)
        self.assertIn("Recent Discord changes", page)
        self.assertIn("Replace head admin", page)
        self.assertIn("Developer and owner only", page)
        self.assertNotIn("Saved on the crew ladder", page)

    def test_api_refuses_when_discord_will_not_and_when_the_caller_is_not_owner(self):
        role = Role(10, "Head Admin", position=5)
        member = Member(5, "Levi", [])
        guild = Guild([role], [member], SimpleNamespace(top_role=Role(1, "bot", position=20), guild_permissions=Perms(False)))

        class Req:
            def __init__(self, body):
                self._body = body

            def json(self):
                return self._body

        async def post(body, owner):
            with patch.object(bot, "staff_uid_from_request", return_value=7), \
                    patch.object(bot, "crew_at_least", return_value=owner), \
                    patch.object(bot, "_guild_for", return_value=guild), \
                    patch.object(bot, "staff_ops", return_value={"version": "test"}):
                return await bot.dash_api_staff_post(Req(body))

        denied = asyncio.run(post({"op": "role", "mode": "add", "role": "10", "who": "5"}, False))
        self.assertEqual(denied.status, 403)
        blocked = asyncio.run(post({"op": "role", "mode": "add", "role": "10", "who": "5"}, True))
        self.assertEqual(blocked.status, 400)
        payload = blocked.body.decode()
        self.assertIn("not changed", payload)
        self.assertIn('"ok": false', payload)
        self.assertEqual(member.added, [])

        guild.me = SimpleNamespace(top_role=Role(1, "bot", position=20), guild_permissions=Perms(True))
        accepted = asyncio.run(post({"op": "role", "mode": "add", "role": "10", "who": "5"}, True))
        self.assertEqual(accepted.status, 200)
        self.assertIn("Head Admin is on Levi", accepted.body.decode())
        self.assertEqual(member.added, [(10, "Staff HQ")])


if __name__ == "__main__":
    unittest.main()
