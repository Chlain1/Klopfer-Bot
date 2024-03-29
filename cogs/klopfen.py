""""
Copyright © Krypton 2019-2023 - https://github.com/kkrypt0nn (https://krypton.ninja)
Description:
🐍 A simple template to start to code your own and personalized discord bot in Python programming language.

Version: 6.1.0
"""

from discord.ext import commands
from discord.ext.commands import Context
import time
from datetime import datetime


# Here we name the cog and create a new class for the cog.
class Klopf(commands.Cog, name="klopf"):
    def __init__(self, bot) -> None:
        self.bot = bot

    # Here you can just add your own commands, you'll always need to provide "self" as first parameter.

    @commands.hybrid_command(
        name="klopf",
        description="This is the klopf",
    )
    async def klopf(self, ctx: Context) -> None:
        """
        This is a testing command that does nothing.

        :param context: The application command context.
        """

        '''a person is doing the klopf'''

        user_roles = [r.name.lower() for r in ctx.message.author.roles]

        if "Klopfer-Teilnehmer" not in user_roles:
            pass
            #TODO print "Du nimmst noch nicht teil, nimm teil mit kjoin um Klopfen zu können."
        else:
            currentTime = datetime.now().strftime(r"%I:%M %p")
            legalTime = ["12:12 AM", "01:01 AM", "02:02 AM", "03:03 AM", "04:04 AM", "05:05 AM", "06:06 AM", "07:07 AM",
                         "08:08 AM", "09:09 AM", "10:10 AM", "11:11 AM", "12:12 PM", "01:01 PM", "02:02 PM", "03:03 PM",
                         "04:04 PM", "05:05 PM", "06:06 PM", "07:07 PM", "08:08 PM", "09:09 PM", "10:10 PM", "11:11 PM"]
            if currentTime in legalTime:
                pass
                #TODO print "Gut gemacht! Du hast richtig geklopft"
            else:
                pass
                #TODO "Duu H*** hast falsch geklopft"


# And then we finally add the cog to the bot so that it can load, unload, reload and use it's content.
async def setup(bot) -> None:
    await bot.add_cog(Klopf(bot))
