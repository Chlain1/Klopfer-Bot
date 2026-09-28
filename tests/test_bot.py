import asyncio
import logging
import unittest
import runpy
from inspect import Parameter
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import discord
from discord.ext import commands

import bot as bot_module
from tests.helpers import DummyChannel, DummyContext, DummyGuild, DummyMember, DummyMessage, DummyRole, DummyUser


class FixedDatetime:
    def __init__(self, hour, minute):
        self._hour = hour
        self._minute = minute

    def now(self):
        return SimpleNamespace(hour=self._hour, minute=self._minute)


class TestBot(unittest.IsolatedAsyncioTestCase):
    async def test_logging_formatter(self):
        formatter = bot_module.LoggingFormatter()
        record = logging.LogRecord("x", logging.INFO, "", 1, "msg", (), None)
        output = formatter.format(record)
        self.assertIn("msg", output)

    async def test_init_db_success(self):
        bot = bot_module.DiscordBot()
        conn = AsyncMock()
        conn.__aenter__ = AsyncMock(return_value=conn)
        conn.__aexit__ = AsyncMock(return_value=None)
        with patch("bot.aiosqlite.connect", return_value=conn):
            file_mock = MagicMock()
            file_mock.__enter__.return_value.read.return_value = ""
            with patch("builtins.open", return_value=file_mock):
                await bot.init_db()

    async def test_init_db_failure(self):
        bot = bot_module.DiscordBot()
        with patch("bot.aiosqlite.connect", side_effect=Exception("fail")):
            await bot.init_db()

    async def test_load_cogs(self):
        bot = bot_module.DiscordBot()
        bot.logger = MagicMock()
        with patch("bot.os.listdir", return_value=["a.py", "b.py", "c.txt"]):
            bot.load_extension = AsyncMock(side_effect=[None, Exception("x")])
            await bot.load_cogs()

    async def test_status_task(self):
        bot = bot_module.DiscordBot()
        bot.change_presence = AsyncMock()
        await bot.status_task.coro(bot)
        bot.change_presence.assert_awaited()

    async def test_before_status_task(self):
        bot = bot_module.DiscordBot()
        bot.wait_until_ready = AsyncMock()
        await bot.before_status_task()
        bot.wait_until_ready.assert_awaited()

    async def test_setup_hook_success(self):
        bot = bot_module.DiscordBot()
        bot._connection.user = SimpleNamespace(name="bot")
        bot.logger = MagicMock()
        bot.init_db = AsyncMock()
        bot.load_cogs = AsyncMock()
        bot.status_task.start = MagicMock()
        bot.check_time.start = MagicMock()
        bot.did_you_klopf = AsyncMock()
        with patch("bot.aiosqlite.connect", new=AsyncMock()):
            await bot.setup_hook()
        bot.status_task.start.assert_called_once()

    async def test_setup_hook_db_failure(self):
        bot = bot_module.DiscordBot()
        bot._connection.user = SimpleNamespace(name="bot")
        bot.logger = MagicMock()
        bot.init_db = AsyncMock()
        bot.load_cogs = AsyncMock()
        bot.status_task.start = MagicMock()
        bot.check_time.start = MagicMock()
        bot.did_you_klopf = AsyncMock()
        with patch("bot.aiosqlite.connect", side_effect=Exception("fail")):
            await bot.setup_hook()

    async def test_on_message_ignores_bot(self):
        bot = bot_module.DiscordBot()
        bot._connection.user = DummyUser(user_id=999)
        msg = DummyMessage(author=bot.user, content="hi")
        bot.process_commands = AsyncMock()
        await bot.on_message(msg)
        bot.process_commands.assert_not_called()

    async def test_on_message_processes(self):
        bot = bot_module.DiscordBot()
        bot._connection.user = DummyUser(user_id=999)
        msg = DummyMessage(author=DummyUser(), content="hi")
        bot.process_commands = AsyncMock()
        await bot.on_message(msg)
        bot.process_commands.assert_awaited()

    async def test_on_command_completion(self):
        bot = bot_module.DiscordBot()
        guild = DummyGuild(guild_id=1, name="g")
        author = DummyMember(user_id=2, name="m")
        context = DummyContext(guild=guild, author=author, command_name="ping")
        bot.logger = MagicMock()
        await bot.on_command_completion(context)
        context.guild = None
        await bot.on_command_completion(context)

    async def test_on_command_error_branches(self):
        bot = bot_module.DiscordBot()
        ctx = DummyContext()

        cooldown = commands.Cooldown(1, 1)
        await bot.on_command_error(ctx, commands.CommandOnCooldown(cooldown, 1.0, commands.BucketType.default))
        ctx.guild = DummyGuild(guild_id=1, name="g")
        await bot.on_command_error(ctx, commands.NotOwner())
        ctx.guild = None
        await bot.on_command_error(ctx, commands.NotOwner())
        await bot.on_command_error(ctx, commands.MissingPermissions(["x"]))
        await bot.on_command_error(ctx, commands.BotMissingPermissions(["y"]))
        missing_param = SimpleNamespace(name="arg", displayed_name="arg")
        await bot.on_command_error(ctx, commands.MissingRequiredArgument(missing_param))

        with self.assertRaises(Exception):
            await bot.on_command_error(ctx, Exception("boom"))

    async def test_send_periodic_message(self):
        bot = bot_module.DiscordBot()
        channel = DummyChannel()
        bot.get_channel = MagicMock(return_value=channel)

        async def fake_sleep(_):
            raise asyncio.CancelledError()

        with patch("bot.asyncio.sleep", side_effect=fake_sleep):
            with patch("bot.datetime", new=FixedDatetime(10, 11)):
                with self.assertRaises(asyncio.CancelledError):
                    await bot.send_periodic_message()
        channel.send.assert_awaited()

    async def test_send_periodic_message_no_channel(self):
        bot = bot_module.DiscordBot()
        bot.get_channel = MagicMock(return_value=None)

        async def fake_sleep(_):
            raise asyncio.CancelledError()

        with patch("bot.asyncio.sleep", side_effect=fake_sleep):
            with patch("bot.datetime", new=FixedDatetime(10, 11)):
                with self.assertRaises(asyncio.CancelledError):
                    await bot.send_periodic_message()

    async def test_send_periodic_message_no_trigger(self):
        bot = bot_module.DiscordBot()
        channel = DummyChannel()
        bot.get_channel = MagicMock(return_value=channel)

        async def fake_sleep(_):
            raise asyncio.CancelledError()

        with patch("bot.asyncio.sleep", side_effect=fake_sleep):
            with patch("bot.datetime", new=FixedDatetime(10, 10)):
                with self.assertRaises(asyncio.CancelledError):
                    await bot.send_periodic_message()
        channel.send.assert_not_called()

    async def test_did_you_klopf(self):
        bot = bot_module.DiscordBot()
        def fake_create_task(coro):
            coro.close()
            return MagicMock()

        with patch("bot.asyncio.create_task", side_effect=fake_create_task) as create_task:
            await bot.did_you_klopf()
        self.assertTrue(create_task.called)

    async def test_check_time_branches(self):
        bot = bot_module.DiscordBot()

        with patch("bot.datetime", new=FixedDatetime(1, 2)):
            await bot.check_time.coro(bot)

        with patch("bot.datetime", new=FixedDatetime(23, 59)):
            bot.get_guild = MagicMock(return_value=None)
            await bot.check_time.coro(bot)

        role = DummyRole(role_id=1225212871462355034, name="r")
        member = DummyMember(roles=[role])
        member_without_role = DummyMember(roles=[])
        guild = DummyGuild(guild_id=746337211074478190, roles=[role], members=[member, member_without_role])
        bot.get_guild = MagicMock(return_value=guild)
        with patch("bot.datetime", new=FixedDatetime(23, 59)):
            await bot.check_time.coro(bot)

        role_missing_guild = DummyGuild(guild_id=746337211074478190, roles=[], members=[member])
        bot.get_guild = MagicMock(return_value=role_missing_guild)
        with patch("bot.datetime", new=FixedDatetime(23, 59)):
            await bot.check_time.coro(bot)

        def raise_http(*args, **kwargs):
            raise Exception("http")

        member.remove_roles = AsyncMock(side_effect=raise_http)
        bot.get_guild = MagicMock(return_value=guild)
        with patch("bot.datetime", new=FixedDatetime(23, 59)):
            with patch("bot.discord.HTTPException", Exception):
                await bot.check_time.coro(bot)

    async def test_event_on_message_crazy(self):
        module_bot = bot_module.bot
        module_bot._connection.user = DummyUser(user_id=999)
        message = DummyMessage(author=DummyUser(), content="crazy")
        message.reply = AsyncMock()
        module_bot.process_commands = AsyncMock()
        await bot_module.on_message(message)
        message.reply.assert_awaited()

    async def test_event_on_message_ignore_self(self):
        module_bot = bot_module.bot
        module_bot._connection.user = DummyUser(user_id=999)
        message = DummyMessage(author=module_bot.user, content="hi")
        message.reply = AsyncMock()
        module_bot.process_commands = AsyncMock()
        await bot_module.on_message(message)
        module_bot.process_commands.assert_not_called()

    async def test_event_on_message_no_crazy(self):
        module_bot = bot_module.bot
        module_bot._connection.user = DummyUser(user_id=999)
        message = DummyMessage(author=DummyUser(), content="hello")
        message.reply = AsyncMock()
        module_bot.process_commands = AsyncMock()
        await bot_module.on_message(message)
        module_bot.process_commands.assert_awaited()

    async def test_member_join_leave(self):
        module_bot = bot_module.bot
        channel = DummyChannel()
        role = DummyRole(role_id=746355774409670657, name="role")
        guild = DummyGuild(guild_id=746337211074478190, roles=[role], system_channel=channel, name="g")
        member = DummyMember(user_id=1, roles=[], guild=guild)
        await bot_module.on_member_join(member)
        await bot_module.on_member_remove(member)

        other_guild = DummyGuild(guild_id=2, roles=[role], system_channel=channel, name="g2")
        other_member = DummyMember(user_id=2, roles=[], guild=other_guild)
        await bot_module.on_member_join(other_member)

        guild.system_channel = None
        await bot_module.on_member_join(member)
        await bot_module.on_member_remove(member)

    async def test_config_missing_exits(self):
        with patch("os.path.isfile", return_value=False):
            with patch("sys.exit", side_effect=SystemExit) as exit_mock:
                with self.assertRaises(SystemExit):
                    runpy.run_module("bot", run_name="__test__")
        self.assertTrue(exit_mock.called)

    async def test_main_guard_runs(self):
        file_mock = MagicMock()
        file_mock.__enter__.return_value.read.return_value = '{"prefix": "!"}'
        with patch("os.path.isfile", return_value=True):
            with patch("builtins.open", return_value=file_mock):
                with patch("discord.ext.commands.Bot.run", return_value=None):
                    runpy.run_module("bot", run_name="__main__")
