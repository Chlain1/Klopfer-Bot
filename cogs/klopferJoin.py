""""
Copyright © Krypton 2019-2023 - https://github.com/kkrypt0nn (https://krypton.ninja)
Description:
🐍 A simple template to start to code your own and personalized discord bot in Python programming language.

Version: 6.1.0
"""

from discord.ext import commands
from discord.ext.commands import Context


# Here we name the cog and create a new class for the cog.
class klopferJoin(commands.Cog, name="template"):
    def __init__(self, bot) -> None:
        self.bot = bot

    # Here you can just add your own commands, you'll always need to provide "self" as first parameter.

    @commands.hybrid_command(
        name="kjoin",
        description="With this command you join the klopf",
    )
    async def kjoin(self, ctx: Context) -> None:
        """
        This is a command with which the users can join the klopf

        :param context: The application command context.
        """

        user_roles = [r.name.lower() for r in ctx.message.author.roles]

        if "Klopfer-Teilnehmer" not in user_roles:
            member = ctx.message.author
            # TODO: get role and give it to member
        else:
            pass
            # TODO: tell the user they already participate


# And then we finally add the cog to the bot so that it can load, unload, reload and use it's content.
async def setup(bot) -> None:
    await bot.add_cog(klopferJoin(bot))
