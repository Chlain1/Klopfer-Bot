""""
Copyright © Krypton 2019-2023 - https://github.com/kkrypt0nn (https://krypton.ninja)
Description:
🐍 A simple template to start to code your own and personalized discord bot in Python programming language.

Version: 6.1.0
"""
import discord
from discord.ext import commands
from discord.ext.commands import Context
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
    async def klopf(self, context: Context) -> None:
        """
        This is a testing command that does nothing.

        :param context: The application command context.
        """

        '''a person is doing the klopf'''

        # user_roles = [r.name.lower() for r in context.message.author.roles]



        if 778977339660697630 in [role.id for role in context.message.author.roles]:
            currentTime = datetime.now().strftime(r"%I:%M %p")
            legalTime = ["12:00 AM", "01:01 AM", "02:02 AM", "03:03 AM", "04:04 AM", "05:05 AM", "06:06 AM", "07:07 AM",
                         "08:08 AM", "09:09 AM", "10:10 AM", "11:11 AM", "12:12 PM", "01:13 PM", "02:14 PM", "03:15 PM",
                         "04:16 PM", "05:17 PM", "06:18 PM", "07:19 PM", "08:20 PM", "09:21 PM", "10:22 PM", "11:23 PM"]
            if currentTime in legalTime:
                embed = discord.Embed(
                    description='Gut gemacht! Du hast richtig geklopft'
                )
                await context.send(embed=embed)
            else:
                embed = discord.Embed(
                    description='Duu H*** hast falsch geklopft'
                )
                await context.send(embed=embed)
        else:
            embed = discord.Embed(
                description='Du nimmst noch nicht teil, nimm teil mit kjoin um Klopfen zu können.'
            )
            await context.send(embed=embed)

    @commands.hybrid_command(
        name="kjoin",
        description="With this command you join the klopf",
    )
    async def kjoin(self, context: Context) -> None:
        """
        This is a command with which the users can join the klopf

        :param context: The application command context.
        """
        role_id = 778977339660697630
        role = context.guild.get_role(role_id)
        user_roles = [r.name.lower() for r in context.message.author.roles]

        if 778977339660697630 in [role.id for role in context.message.author.roles]:
            embed = discord.Embed(
                description='Du nimmst doch schon teil, wasn dein Problem.'
            )
            await context.send(embed=embed)
        else:
            member = context.message.author
            role = context.guild.get_role(778977339660697630)
            await member.add_roles(role)
            embed = discord.Embed(
                description='Du nimmst nun Teil'
            )
            await context.send(embed=embed)



# And then we finally add the cog to the bot so that it can load, unload, reload and use it's content.
async def setup(bot) -> None:
    await bot.add_cog(Klopf(bot))
