import os
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import discord

from cogs.moderation import Moderation
from tests.helpers import DummyChannel, DummyContext, DummyGuild, DummyMember, DummyMessage


class DummyAttachment:
    def __init__(self, url="http://example.com/file.png"):
        self.url = url


class DummyUser:
    def __str__(self):
        return "User"


class DummyBot:
    def __init__(self):
        self.http = SimpleNamespace(ban=AsyncMock())
        self.get_user = MagicMock(return_value=None)
        self.fetch_user = AsyncMock(return_value=DummyUser())


class TestModerationCog(unittest.IsolatedAsyncioTestCase):
    async def test_purge(self):
        bot = DummyBot()
        cog = Moderation(bot)
        channel = DummyChannel()
        channel.purge = AsyncMock(return_value=[1, 2, 3])
        context = DummyContext(channel=channel, author=DummyMember())
        await cog.purge.callback(cog, context, amount=2)
        self.assertTrue(context.send.called)
        self.assertTrue(channel.send.called)

    async def test_hackban_success(self):
        bot = DummyBot()
        cog = Moderation(bot)
        context = DummyContext(guild=DummyGuild(), author=DummyMember())
        await cog.hackban.callback(cog, context, user_id="123", reason="x")
        embed = context.send.call_args.kwargs["embed"]
        self.assertIn("banned", embed.description)

    async def test_hackban_failure(self):
        bot = DummyBot()
        bot.http.ban = AsyncMock(side_effect=Exception("fail"))
        cog = Moderation(bot)
        context = DummyContext(guild=DummyGuild(), author=DummyMember())
        await cog.hackban.callback(cog, context, user_id="123")
        embed = context.send.call_args.kwargs["embed"]
        self.assertIn("error", embed.description.lower())

    async def test_archive(self):
        bot = DummyBot()
        cog = Moderation(bot)
        channel = DummyChannel(channel_id=999)
        author = DummyMember()
        guild = DummyGuild(name="g", guild_id=1)
        context = DummyContext(channel=channel, guild=guild, author=author)
        msg = DummyMessage(author, content="hello", attachments=[DummyAttachment()], channel=channel)
        channel.set_history([msg])
        with unittest.mock.patch("cogs.moderation.discord.File", return_value=MagicMock()):
            await cog.archive.callback(cog, context, limit=1)
        self.assertTrue(context.send.called)
        self.assertFalse(os.path.exists("999.log"))

    async def test_archive_without_attachments(self):
        bot = DummyBot()
        cog = Moderation(bot)
        channel = DummyChannel(channel_id=1000)
        author = DummyMember()
        guild = DummyGuild(name="g", guild_id=1)
        context = DummyContext(channel=channel, guild=guild, author=author)
        msg = DummyMessage(author, content="hello", attachments=[], channel=channel)
        channel.set_history([msg])
        with unittest.mock.patch("cogs.moderation.discord.File", return_value=MagicMock()):
            await cog.archive.callback(cog, context, limit=1)
        self.assertTrue(context.send.called)
        self.assertFalse(os.path.exists("1000.log"))

    async def test_setup(self):
        bot = AsyncMock()
        bot.add_cog = AsyncMock()
        await __import__("cogs.moderation").moderation.setup(bot)
        bot.add_cog.assert_awaited()
