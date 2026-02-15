import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import discord

from cogs.fun import Choice, Fun, RockPaperScissors, RockPaperScissorsView
from tests.helpers import DummyContext, DummyInteraction, DummyUser


class TestFunCog(unittest.IsolatedAsyncioTestCase):
    async def test_choice_buttons(self):
        choice = Choice()
        interaction = DummyInteraction()
        await choice.children[0].callback(interaction)
        self.assertEqual(choice.value, "heads")
        await choice.children[1].callback(interaction)
        self.assertEqual(choice.value, "tails")

    async def test_rps_draw(self):
        select = RockPaperScissors()
        interaction = DummyInteraction(user=DummyUser(name="U"))
        select._values = ["rock"]
        with patch("cogs.fun.random.choice", return_value="rock"):
            await select.callback(interaction)
        args = interaction.response.edit_message.call_args.kwargs
        embed = args["embed"]
        self.assertIn("draw", embed.description.lower())

    async def test_rps_win(self):
        select = RockPaperScissors()
        interaction = DummyInteraction(user=DummyUser(name="U"))
        select._values = ["rock"]
        with patch("cogs.fun.random.choice", return_value="scissors"):
            await select.callback(interaction)
        args = interaction.response.edit_message.call_args.kwargs
        embed = args["embed"]
        self.assertIn("won", embed.description.lower())

    async def test_rps_lose(self):
        select = RockPaperScissors()
        interaction = DummyInteraction(user=DummyUser(name="U"))
        select._values = ["rock"]
        with patch("cogs.fun.random.choice", return_value="paper"):
            await select.callback(interaction)
        args = interaction.response.edit_message.call_args.kwargs
        embed = args["embed"]
        self.assertIn("lost", embed.description.lower())

    async def test_randomfact_success(self):
        cog = Fun(MagicMock())
        context = DummyContext()
        response = AsyncMock()
        response.status = 200
        response.json = AsyncMock(return_value={"text": "fact"})
        response.__aenter__ = AsyncMock(return_value=response)
        response.__aexit__ = AsyncMock(return_value=None)

        request_ctx = AsyncMock()
        request_ctx.__aenter__ = AsyncMock(return_value=response)
        request_ctx.__aexit__ = AsyncMock(return_value=None)

        session = AsyncMock()
        session.get = MagicMock(return_value=request_ctx)
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=None)

        with patch("cogs.fun.aiohttp.ClientSession", return_value=session):
            await cog.randomfact.callback(cog, context)

        embed = context.send.call_args.kwargs["embed"]
        self.assertEqual(embed.description, "fact")

    async def test_randomfact_failure(self):
        cog = Fun(MagicMock())
        context = DummyContext()
        response = AsyncMock()
        response.status = 500
        response.__aenter__ = AsyncMock(return_value=response)
        response.__aexit__ = AsyncMock(return_value=None)

        request_ctx = AsyncMock()
        request_ctx.__aenter__ = AsyncMock(return_value=response)
        request_ctx.__aexit__ = AsyncMock(return_value=None)

        session = AsyncMock()
        session.get = MagicMock(return_value=request_ctx)
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=None)

        with patch("cogs.fun.aiohttp.ClientSession", return_value=session):
            await cog.randomfact.callback(cog, context)

        embed = context.send.call_args.kwargs["embed"]
        self.assertIn("Error", embed.title)

    async def test_coinflip_correct(self):
        cog = Fun(MagicMock())
        context = DummyContext()
        message = AsyncMock()
        context.send = AsyncMock(return_value=message)

        async def set_value(self):
            self.value = "heads"

        with patch("cogs.fun.Choice.wait", new=set_value):
            with patch("cogs.fun.random.choice", return_value="heads"):
                await cog.coinflip.callback(cog, context)
        args = message.edit.call_args.kwargs
        embed = args["embed"]
        self.assertIn("Correct", embed.description)

    async def test_coinflip_incorrect(self):
        cog = Fun(MagicMock())
        context = DummyContext()
        message = AsyncMock()
        context.send = AsyncMock(return_value=message)

        async def set_value(self):
            self.value = "tails"

        with patch("cogs.fun.Choice.wait", new=set_value):
            with patch("cogs.fun.random.choice", return_value="heads"):
                await cog.coinflip.callback(cog, context)

        args = message.edit.call_args.kwargs
        embed = args["embed"]
        self.assertIn("Woops", embed.description)

    async def test_rock_paper_scissors_command(self):
        cog = Fun(MagicMock())
        context = DummyContext()
        await cog.rock_paper_scissors.callback(cog, context)
        args = context.send.call_args.args
        self.assertIn("Please make your choice", args[0])

    async def test_rps_view(self):
        view = RockPaperScissorsView()
        self.assertEqual(len(view.children), 1)

    async def test_setup(self):
        bot = MagicMock()
        bot.add_cog = AsyncMock()
        await __import__("cogs.fun").fun.setup(bot)
        bot.add_cog.assert_awaited()
