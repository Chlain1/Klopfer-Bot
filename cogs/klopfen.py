""""
Copyright © Krypton 2019-2023 - https://github.com/kkrypt0nn (https://krypton.ninja)
Description:
🐍 A simple template to start to code your own and personalized discord bot in Python programming language.

Version: 6.1.0
"""
import json

import discord
from discord.ext import commands
from discord.ext.commands import Context
from datetime import datetime


LEADERBOARD_FILE = 'leaderboard.json'

# Here we name the cog and create a new class for the cog.
class Klopf(commands.Cog, name="klopf"):
    def __init__(self, bot) -> None:
        self.bot = bot
        try:
            with open(LEADERBOARD_FILE, 'r') as file:
                self.leaderboard = json.load(file)
        except (FileNotFoundError, json.JSONDecodeError):
            self.leaderboard = {}


    async def update_leaderboard(self, user_id, correct=True):
        if user_id not in self.leaderboard:
            self.leaderboard[user_id] = {'correct_times': 0, 'wrong_times': 0}

        if correct:
            self.leaderboard[user_id]['correct_times'] += 1
        else:
            self.leaderboard[user_id]['wrong_times'] += 1

        await self.save_leaderboard()

    async def save_leaderboard(self):
        with open(LEADERBOARD_FILE, 'w') as file:
            json.dump(self.leaderboard, file)

    @commands.hybrid_command(
        name="leaderboard",
        description="This prints the leaderboard of the Klopf"
    )
    async def leaderboard(self, context: Context) -> None:
        """
        This is the command that prints the leaderboard
        :param context: The application command context
        """

        embed = discord.Embed(
            title="Leaderboard:",
            colour=0xC0DC04
        )

        #embed.add_field(name="Correct Times", value="**User ID**: *Times*", inline=False)
        for user_id, stats in self.leaderboard.items():
            user = context.guild.get_member(int(user_id))
            if user:
                embed.add_field(
                    name=user.name,
                    value=f"Correct Times: {stats['correct_times']}, Wrong Times: {stats['wrong_times']}, Score: {stats['correct_times'] - 5 * stats['wrong_times']} ",
                    inline=False)
        await context.send(embed=embed)



    @commands.hybrid_command(
        name="klopf",
        description="This is the klopf",
    )
    async def klopf(self, context: Context) -> None:
        """
        This is the klopf command

        :param context: The application command context.
        """

        '''a person is doing the klopf'''

        if 778977339660697630 in [role.id for role in context.message.author.roles]:
            currentTime = datetime.now()
            hour = currentTime.hour
            minute = currentTime.minute
            hourStr = str(hour).zfill(2)
            minuteStr = str(minute).zfill(2)
            print("before if!")
            if hour == minute and 1225212871462355034 not in [role.id for role in context.message.author.roles]:
                print("if hour == minutes starts")
                await self.update_leaderboard(str(context.author.id), correct=True)
                embed = discord.Embed(
                    description='Gut gemacht! Du hast um ' + hourStr + ':' + minuteStr + ' richtig geklopft',
                    colour=0x00FF00
                )
                member = context.message.author
                role = context.guild.get_role(1225212871462355034)
                await member.add_roles(role)
                await context.send(embed=embed)

            else:
                print("else hour == minutes starts")
                await self.update_leaderboard(str(context.author.id), correct=False)
                embed = discord.Embed(
                    description='Duu H***, was ist an ' + hourStr + ':' + minuteStr + ' richtig? Du hast obviously falsch geklopft! Aber ich will mal nicht so sein, du weist ja, keep yourself safe!',
                    color=0xFF0000
                )
                await context.send(embed=embed)
                print("else hour == minutes ends")
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


    @commands.hybrid_command(
        name="kleave",
        description="With this command you leave the klopf",
    )
    async def kleave(self, context: Context) -> None:
        """
        This is a command with which the users can join the klopf

        :param context: The application command context.
        """


        if 778977339660697630 in [role.id for role in context.message.author.roles]:
            member = context.message.author
            role = context.guild.get_role(778977339660697630)
            await member.remove_roles(role)
            embed = discord.Embed(
                description='Du nimmst nun nicht mehr Teil'
            )
            await context.send(embed=embed)
        else:
            embed = discord.Embed(
                description='Du nimmst doch schon nicht teil, wasn dein Problem.'
            )
            await context.send(embed=embed)


# And then we finally add the cog to the bot so that it can load, unload, reload and use it's content.
async def setup(bot) -> None:
    await bot.add_cog(Klopf(bot))
