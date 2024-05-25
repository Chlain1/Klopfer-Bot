
import json

import discord
from discord.ext import commands
from discord.ext.commands import Context
import random



# Here we name the cog and create a new class for the cog.
class RollButler(commands.Cog, name="RollButler"):
    def __init__(self, bot) -> None:
        self.bot = bot

    @commands.hybrid_command(
        name="roll",
        description="This lets you roll a dice"
    )
    async def roll(self, context: Context, dice: str, times = None) -> None:
        """
        This is the command that rolls a dice you specified the amount of times you specified.
        :param context: The application command context
        """
        if times is None:
            times = 1

        try:
            dice = int(dice)
            times = int(times)
        except ValueError:
            await context.send("Please enter valid numbers.")
            return

        diceInt = int(dice)
        timesInt = int(times)

        embed = discord.Embed(
            title=f"Rolling a D{diceInt} {timesInt} times.",
            colour=0xFC0FC0,
            description=""
        )

        if timesInt > 100 or timesInt < 1:
            await context.send("You can't roll the dice more than 100 times.")
        elif diceInt > 100 or diceInt < 1:
            await context.send(f"Why would you want a dice with {diceInt} sides?")
        else:
            await context.send(f"Rolling a {diceInt} sided dice...")
            for i in range(timesInt):
                embed.description += f"Roll {i + 1}: {random.randint(1, diceInt)}\n"
            await context.send(embed=embed)






# And then we finally add the cog to the bot so that it can load, unload, reload and use it's content.
async def setup(bot) -> None:
    await bot.add_cog(RollButler(bot))
