import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import discord

from cogs.general import General
from tests.helpers import DummyContext, DummyGuild, DummyInteraction, DummyMessage, DummyRole, DummyUser


class DummyAttachment:
    def __init__(self, spoiler=False, url="http://example.com/file.png"):
        self._spoiler = spoiler
        self.url = url

    def is_spoiler(self):
        return self._spoiler


class DummyCog:
    def __init__(self, commands):
        self._commands = commands

    def get_commands(self):
        return self._commands


class DummyCommand:
    def __init__(self, name, description):
        self.name = name
        self.description = description


class DummyBot:
    def __init__(self, cogs, owner=False):
        self.cogs = cogs
        self._owner = owner
        self.tree = MagicMock()
        self.config = {"prefix": "!"}

    async def is_owner(self, user):
        return self._owner

    def get_cog(self, name):
        return self.cogs.get(name)


class TestGeneralCog(unittest.IsolatedAsyncioTestCase):
    async def test_remove_spoilers_no_spoiler(self):
        bot = DummyBot({})
        cog = General(bot)
        message = DummyMessage(DummyUser(), content="hello", attachments=[])
        interaction = DummyInteraction()
        await cog.remove_spoilers(interaction, message)
        embed = interaction.response.send_message.call_args.kwargs["embed"]
        self.assertNotIn("||", embed.description)

    async def test_remove_spoilers_with_spoiler(self):
        bot = DummyBot({})
        cog = General(bot)
        attachment = DummyAttachment(spoiler=True)
        message = DummyMessage(DummyUser(), content="||secret||", attachments=[attachment])
        interaction = DummyInteraction()
        await cog.remove_spoilers(interaction, message)
        embed = interaction.response.send_message.call_args.kwargs["embed"]
        self.assertEqual(embed.image.url, attachment.url)

    async def test_remove_spoilers_second_attachment(self):
        bot = DummyBot({})
        cog = General(bot)
        attachment1 = DummyAttachment(spoiler=False)
        attachment2 = DummyAttachment(spoiler=True)
        message = DummyMessage(DummyUser(), content="||secret||", attachments=[attachment1, attachment2])
        interaction = DummyInteraction()
        await cog.remove_spoilers(interaction, message)
        embed = interaction.response.send_message.call_args.kwargs["embed"]
        self.assertEqual(embed.image.url, attachment2.url)

    async def test_grab_id(self):
        bot = DummyBot({})
        cog = General(bot)
        interaction = DummyInteraction(user=DummyUser())
        await cog.grab_id(interaction, DummyUser(user_id=55))
        embed = interaction.response.send_message.call_args.kwargs["embed"]
        self.assertIn("55", embed.description)

    async def test_help_non_owner(self):
        commands = [DummyCommand("ping", "Ping the bot")]
        bot = DummyBot({"general": DummyCog(commands), "owner": DummyCog(commands), "missing": None}, owner=False)
        cog = General(bot)
        context = DummyContext()
        await cog.help.callback(cog, context)
        embed = context.send.call_args.kwargs["embed"]
        self.assertIn("Help", embed.title)

    async def test_help_owner(self):
        commands = [DummyCommand("ping", "Ping the bot")]
        bot = DummyBot({"general": DummyCog(commands), "owner": DummyCog(commands)}, owner=True)
        cog = General(bot)
        context = DummyContext()
        await cog.help.callback(cog, context)
        embed = context.send.call_args.kwargs["embed"]
        self.assertIn("Help", embed.title)

    async def test_botinfo(self):
        bot = DummyBot({})
        cog = General(bot)
        context = DummyContext()
        await cog.botinfo.callback(cog, context)
        embed = context.send.call_args.kwargs["embed"]
        self.assertIn("Bot Information", embed.author.name)

    async def test_serverinfo_roles_over_limit(self):
        roles = [DummyRole(role_id=i, name=f"r{i}") for i in range(51)]
        guild = DummyGuild(roles=roles, members=[DummyUser()], channels=[object()])
        context = DummyContext(guild=guild)
        bot = DummyBot({})
        cog = General(bot)
        await cog.serverinfo.callback(cog, context)
        embed = context.send.call_args.kwargs["embed"]
        self.assertIn("Roles", embed.fields[3].name)

    async def test_serverinfo_with_icon(self):
        roles = [DummyRole(role_id=1, name="r1")]
        icon = SimpleNamespace(url="http://example.com/icon.png")
        guild = DummyGuild(roles=roles, members=[DummyUser()], channels=[object()], icon=icon)
        context = DummyContext(guild=guild)
        bot = DummyBot({})
        cog = General(bot)
        await cog.serverinfo.callback(cog, context)
        embed = context.send.call_args.kwargs["embed"]
        self.assertEqual(embed.thumbnail.url, icon.url)

    async def test_ping(self):
        bot = DummyBot({})
        bot.latency = 0.01
        cog = General(bot)
        context = DummyContext()
        await cog.ping.callback(cog, context)
        embed = context.send.call_args.kwargs["embed"]
        self.assertIn("Pong", embed.title)

    async def test_eight_ball(self):
        bot = DummyBot({})
        cog = General(bot)
        context = DummyContext()
        with patch("cogs.general.random.choice", return_value="Yes."):
            await cog.eight_ball.callback(cog, context, question="test?")
        embed = context.send.call_args.kwargs["embed"]
        self.assertIn("Yes.", embed.description)

    async def test_setup(self):
        bot = DummyBot({})
        bot.add_cog = AsyncMock()
        await __import__("cogs.general").general.setup(bot)
        bot.add_cog.assert_awaited()
