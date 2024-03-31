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


# Here we name the cog and create a new class for the cog.
class Klopf(commands.Cog, name="klopf"):
    def __init__(self, bot) -> None:
        self.bot = bot

    usage_stats = {}

    def load_leaderboard(self):
        try:
            with open("leaderboard.json", "r") as file:
                return json.load(file)
        except FileNotFoundError:
            print("Leaderboard file not found.")
            return {"usage_stats": {}}


    def save_leaderboard(self):
        with open("leaderboard.json", "w") as file:
            json.dump({"usage_stats": self.usage_stats}, file, indent=4)

    def update_leaderboard(self, user_id, correct_time=False, wrong_time=False):
        if user_id not in self.usage_stats:
            self.usage_stats[user_id] = {"correct_time": 0, "wrong_time": 0}

        if correct_time:
            self.usage_stats[user_id]["correct_time"] += 1
        elif wrong_time:
            self.usage_stats[user_id]["wrong_time"] += 1

        self.save_leaderboard() #Saves Leaderboard after every update


    def process_command(self, user_id, hour, minute):
        if hour == minute:
            self.update_leaderboard(user_id, correct_time=True)
        elif hour != minute:
            self.update_leaderboard(user_id, wrong_time=True)

    @commands.Cog.listener()
    async def on_command_completion(self, context):
        self.save_leaderboard()

    @commands.hybrid_command(
        name="leaderboard",
        description="This prints the leaderboard of the Klopf"
    )
    async def leaderboard(self, context: Context) -> None:
        """
        This is the command that prints the leaderboard
        :param context: The application command context
        """

        print("Usage Stats:", self.usage_stats)

        if self.usage_stats:
            embed = discord.Embed(
                title="Leaderboard",
                description=""
            )
            for user_id, stats in self.usage_stats.items():
                member = context.guild.get_member(int(user_id))
                if member:
                    username = member.display_name
                    correct_time = str(stats.get("correct_time", 0))
                    wrong_time = str(stats.get("wrong_time", 0))
                    embed.description = embed.description + username + ": Correct Time - " + correct_time + ", Wrong Time - " + wrong_time + "\n" #TODO: fix this shitshow

        else:
            embed = discord.Embed(
                title="Leaderboard",
                description="No stats available"
            )

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

            user_id = str(context.message.author.id)
            if user_id not in self.usage_stats:
                self.usage_stats[user_id] = {"correct_time": 0, "wrong_time": 0}

            currentTime = datetime.now()
            hour = currentTime.hour
            minute = currentTime.minute
            hourStr = str(hour).zfill(2)
            minuteStr = str(minute).zfill(2)
            if hour == minute:
                self.usage_stats[user_id]["correct_time"] += 1
                embed = discord.Embed(
                    description='Gut gemacht! Du hast um ' + hourStr + ':' + minuteStr + ' richtig geklopft',
                    colour=0x00FF00
                )
                await context.send(embed=embed)
            else:
                self.usage_stats[user_id]["wrong_time"] += 1
                embed = discord.Embed(
                    description='Duu H***, was ist an ' + hourStr + ':' + minuteStr + ' richtig? Du hast obviously falsch geklopft! Aber ich will mal nicht so sein, du weist ja, keep yourself safe!',
                    color=0xFF0000
                )
                await context.send(embed=embed)
        else:
            embed = discord.Embed(
                description='Du nimmst noch nicht teil, nimm teil mit kjoin um Klopfen zu können.'
            )
            await context.send(embed=embed)
        print("Usage Stats:", self.usage_stats)

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
