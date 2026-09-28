import unittest
from unittest.mock import AsyncMock, MagicMock

from cogs.owner import Owner
from tests.helpers import DummyContext


class DummyTree:
    def __init__(self):
        self.sync = AsyncMock()
        self.copy_global_to = MagicMock()
        self.clear_commands = MagicMock()


class DummyBot:
    def __init__(self):
        self.tree = DummyTree()
        self.load_extension = AsyncMock()
        self.unload_extension = AsyncMock()
        self.reload_extension = AsyncMock()
        self.close = AsyncMock()


class TestOwnerCog(unittest.IsolatedAsyncioTestCase):
    async def test_sync_global(self):
        bot = DummyBot()
        cog = Owner(bot)
        context = DummyContext(bot=bot)
        await cog.sync.callback(cog, context, scope="global")
        self.assertTrue(context.send.called)

    async def test_sync_guild(self):
        bot = DummyBot()
        cog = Owner(bot)
        context = DummyContext(bot=bot, guild=MagicMock())
        await cog.sync.callback(cog, context, scope="guild")
        self.assertTrue(context.send.called)

    async def test_sync_invalid(self):
        bot = DummyBot()
        cog = Owner(bot)
        context = DummyContext(bot=bot)
        await cog.sync.callback(cog, context, scope="x")
        embed = context.send.call_args.kwargs["embed"]
        self.assertIn("scope", embed.description)

    async def test_unsync_global(self):
        bot = DummyBot()
        cog = Owner(bot)
        context = DummyContext(bot=bot)
        await cog.unsync.callback(cog, context, scope="global")
        self.assertTrue(context.send.called)

    async def test_unsync_guild(self):
        bot = DummyBot()
        cog = Owner(bot)
        context = DummyContext(bot=bot, guild=MagicMock())
        await cog.unsync.callback(cog, context, scope="guild")
        self.assertTrue(context.send.called)

    async def test_unsync_invalid(self):
        bot = DummyBot()
        cog = Owner(bot)
        context = DummyContext(bot=bot)
        await cog.unsync.callback(cog, context, scope="x")
        embed = context.send.call_args.kwargs["embed"]
        self.assertIn("scope", embed.description)

    async def test_load_success(self):
        bot = DummyBot()
        cog = Owner(bot)
        context = DummyContext(bot=bot)
        await cog.load.callback(cog, context, cog="x")
        embed = context.send.call_args.kwargs["embed"]
        self.assertIn("Successfully", embed.description)

    async def test_load_failure(self):
        bot = DummyBot()
        bot.load_extension = AsyncMock(side_effect=Exception("fail"))
        cog = Owner(bot)
        context = DummyContext(bot=bot)
        await cog.load.callback(cog, context, cog="x")
        embed = context.send.call_args.kwargs["embed"]
        self.assertIn("Could not", embed.description)

    async def test_unload_success(self):
        bot = DummyBot()
        cog = Owner(bot)
        context = DummyContext(bot=bot)
        await cog.unload.callback(cog, context, cog="x")
        embed = context.send.call_args.kwargs["embed"]
        self.assertIn("Successfully", embed.description)

    async def test_unload_failure(self):
        bot = DummyBot()
        bot.unload_extension = AsyncMock(side_effect=Exception("fail"))
        cog = Owner(bot)
        context = DummyContext(bot=bot)
        await cog.unload.callback(cog, context, cog="x")
        embed = context.send.call_args.kwargs["embed"]
        self.assertIn("Could not", embed.description)

    async def test_reload_success(self):
        bot = DummyBot()
        cog = Owner(bot)
        context = DummyContext(bot=bot)
        await cog.reload.callback(cog, context, cog="x")
        embed = context.send.call_args.kwargs["embed"]
        self.assertIn("Successfully", embed.description)

    async def test_reload_failure(self):
        bot = DummyBot()
        bot.reload_extension = AsyncMock(side_effect=Exception("fail"))
        cog = Owner(bot)
        context = DummyContext(bot=bot)
        await cog.reload.callback(cog, context, cog="x")
        embed = context.send.call_args.kwargs["embed"]
        self.assertIn("Could not", embed.description)

    async def test_shutdown(self):
        bot = DummyBot()
        cog = Owner(bot)
        context = DummyContext(bot=bot)
        await cog.shutdown.callback(cog, context)
        bot.close.assert_awaited()

    async def test_say(self):
        bot = DummyBot()
        cog = Owner(bot)
        context = DummyContext(bot=bot)
        await cog.say.callback(cog, context, message="hi")
        context.send.assert_awaited_with("hi")

    async def test_embed(self):
        bot = DummyBot()
        cog = Owner(bot)
        context = DummyContext(bot=bot)
        await cog.embed.callback(cog, context, message="hi")
        embed = context.send.call_args.kwargs["embed"]
        self.assertIn("hi", embed.description)

    async def test_setup(self):
        bot = DummyBot()
        bot.add_cog = AsyncMock()
        await __import__("cogs.owner").owner.setup(bot)
        bot.add_cog.assert_awaited()
