import unittest
from unittest.mock import AsyncMock, patch

from cogs.rollbutler import DiceSelect, DiceView, RollModal, RollButler
from tests.helpers import DummyContext, DummyInteraction


class TestRollButlerCog(unittest.IsolatedAsyncioTestCase):
    async def test_roll_command(self):
        cog = RollButler(bot=None)
        context = DummyContext()
        await cog.roll.callback(cog, context)
        args = context.send.call_args.kwargs
        self.assertIn("Dice Roller", args["embed"].title)

    async def test_dice_select_opens_modal(self):
        select = DiceSelect()
        interaction = DummyInteraction()
        select._values = ["6"]
        await select.callback(interaction)
        self.assertTrue(interaction.response.send_modal.called)

    async def test_roll_modal_invalid(self):
        modal = RollModal(6)
        interaction = DummyInteraction()
        modal.rolls_input._value = "x"
        await modal.on_submit(interaction)
        args = interaction.response.send_message.call_args
        self.assertIn("valid", args.args[0])

    async def test_roll_modal_out_of_range(self):
        modal = RollModal(6)
        interaction = DummyInteraction()
        modal.rolls_input._value = "0"
        await modal.on_submit(interaction)
        args = interaction.response.send_message.call_args
        self.assertIn("between", args.args[0])

    async def test_roll_modal_boundary_min(self):
        modal = RollModal(6)
        interaction = DummyInteraction()
        modal.rolls_input._value = "1"
        await modal.on_submit(interaction)
        self.assertTrue(interaction.response.send_message.called)

    async def test_roll_modal_boundary_max(self):
        modal = RollModal(6)
        interaction = DummyInteraction()
        modal.rolls_input._value = "100"
        await modal.on_submit(interaction)
        self.assertTrue(interaction.response.send_message.called)

    async def test_view_timeout_disables(self):
        view = DiceView()
        await view.on_timeout()
        for child in view.children:
            self.assertTrue(child.disabled)

    async def test_setup(self):
        bot = AsyncMock()
        bot.add_cog = AsyncMock()
        await __import__("cogs.rollbutler").rollbutler.setup(bot)
        bot.add_cog.assert_awaited()
