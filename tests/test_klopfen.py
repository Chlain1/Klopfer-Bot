import importlib
import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import discord

from tests.helpers import DummyContext, DummyGuild, DummyMember, DummyRole


class FixedDatetime:
    def __init__(self, hour, minute):
        self._hour = hour
        self._minute = minute

    def now(self):
        return SimpleNamespace(hour=self._hour, minute=self._minute)


class TestKlopfenCog(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.leaderboard_path = os.path.join(self.tmpdir.name, "leaderboard.json")
        os.environ["LEADERBOARD_PATH"] = self.leaderboard_path
        self.klopfen = importlib.import_module("cogs.klopfen")
        importlib.reload(self.klopfen)

    async def asyncTearDown(self):
        self.tmpdir.cleanup()

    async def test_update_leaderboard_and_save(self):
        cog = self.klopfen.Klopf(bot=None)
        await cog.update_leaderboard("1", correct=True)
        await cog.update_leaderboard("1", correct=False)
        self.assertEqual(cog.leaderboard["1"]["correct_times"], 1)
        self.assertEqual(cog.leaderboard["1"]["wrong_times"], 1)
        self.assertTrue(os.path.exists(self.leaderboard_path))

    async def test_load_existing_leaderboard(self):
        with open(self.leaderboard_path, "w") as file:
            file.write('{"2": {"correct_times": 3, "wrong_times": 1}}')
        cog = self.klopfen.Klopf(bot=None)
        self.assertEqual(cog.leaderboard["2"]["correct_times"], 3)

    async def test_leaderboard_command(self):
        role = DummyRole(role_id=778977339660697630)
        member = DummyMember(user_id=1, roles=[role])
        guild = DummyGuild(members=[member])
        context = DummyContext(guild=guild, author=member)
        cog = self.klopfen.Klopf(bot=None)
        cog.leaderboard = {"1": {"correct_times": 2, "wrong_times": 1}}
        await self.klopfen.Klopf.leaderboard.callback(cog, context)
        embed = context.send.call_args.kwargs["embed"]
        self.assertIn("Leaderboard", embed.title)

    async def test_leaderboard_command_missing_user(self):
        guild = DummyGuild(members=[])
        context = DummyContext(guild=guild, author=DummyMember())
        cog = self.klopfen.Klopf(bot=None)
        cog.leaderboard = {"99": {"correct_times": 1, "wrong_times": 0}}
        await self.klopfen.Klopf.leaderboard.callback(cog, context)
        embed = context.send.call_args.kwargs["embed"]
        self.assertIn("Leaderboard", embed.title)

    async def test_klopf_correct_time(self):
        role = DummyRole(role_id=778977339660697630)
        gain_role = DummyRole(role_id=1225212871462355034)
        member = DummyMember(user_id=1, roles=[role])
        guild = DummyGuild(roles=[gain_role])
        context = DummyContext(guild=guild, author=member)
        context.message.author = member
        with patch("cogs.klopfen.datetime", new=FixedDatetime(10, 10)):
            cog = self.klopfen.Klopf(bot=None)
            await cog.klopf.callback(cog, context)
        embed = context.send.call_args.kwargs["embed"]
        self.assertIn("richtig geklopft", embed.description)

    async def test_klopf_wrong_time(self):
        role = DummyRole(role_id=778977339660697630)
        member = DummyMember(user_id=1, roles=[role])
        guild = DummyGuild(roles=[DummyRole(role_id=1225212871462355034)])
        context = DummyContext(guild=guild, author=member)
        context.message.author = member
        with patch("cogs.klopfen.datetime", new=FixedDatetime(10, 9)):
            cog = self.klopfen.Klopf(bot=None)
            await cog.klopf.callback(cog, context)
        embed = context.send.call_args.kwargs["embed"]
        self.assertIn("falsch", embed.description)

    async def test_klopf_not_participating(self):
        member = DummyMember(user_id=1, roles=[])
        guild = DummyGuild()
        context = DummyContext(guild=guild, author=member)
        context.message.author = member
        cog = self.klopfen.Klopf(bot=None)
        await cog.klopf.callback(cog, context)
        embed = context.send.call_args.kwargs["embed"]
        self.assertIn("nicht teil", embed.description)

    async def test_kjoin_already_in(self):
        role = DummyRole(role_id=778977339660697630)
        member = DummyMember(user_id=1, roles=[role])
        guild = DummyGuild(roles=[role])
        context = DummyContext(guild=guild, author=member)
        context.message.author = member
        cog = self.klopfen.Klopf(bot=None)
        await cog.kjoin.callback(cog, context)
        embed = context.send.call_args.kwargs["embed"]
        self.assertIn("schon teil", embed.description)

    async def test_kjoin_new(self):
        role = DummyRole(role_id=778977339660697630)
        member = DummyMember(user_id=1, roles=[])
        guild = DummyGuild(roles=[role])
        context = DummyContext(guild=guild, author=member)
        context.message.author = member
        cog = self.klopfen.Klopf(bot=None)
        await cog.kjoin.callback(cog, context)
        member.add_roles.assert_awaited()

    async def test_kleave(self):
        role = DummyRole(role_id=778977339660697630)
        member = DummyMember(user_id=1, roles=[role])
        guild = DummyGuild(roles=[role])
        context = DummyContext(guild=guild, author=member)
        context.message.author = member
        cog = self.klopfen.Klopf(bot=None)
        await cog.kleave.callback(cog, context)
        member.remove_roles.assert_awaited()

    async def test_kleave_not_in(self):
        member = DummyMember(user_id=1, roles=[])
        guild = DummyGuild(roles=[DummyRole(role_id=778977339660697630)])
        context = DummyContext(guild=guild, author=member)
        context.message.author = member
        cog = self.klopfen.Klopf(bot=None)
        await cog.kleave.callback(cog, context)
        embed = context.send.call_args.kwargs["embed"]
        self.assertIn("nicht teil", embed.description)

    async def test_setup(self):
        bot = AsyncMock()
        bot.add_cog = AsyncMock()
        await self.klopfen.setup(bot)
        bot.add_cog.assert_awaited()
