import json

import discord
from discord.ext import commands
from discord.ext.commands import Context

ROLES_TO_SELECT = 'self_roles.json'

class Selfroles(commands.Cog, name="selfRoles"):
    def __init__(self, config, bot):
        self.bot = bot
        self.config = config

        try:
            with open(ROLES_TO_SELECT, 'r') as file:
                self.roles = json.load(file)
        except (FileNotFoundError, json.JSONDecodeError):
            self.roles = {}
        
    async def update_roles(self, role_id, server_id):
        self.roles[server_id] = {role_id}
        await self.save_roles()

    async def save_roles(self):
        with open(ROLES_TO_SELECT, 'w') as file:
            json.dump(self.roles, file)

    @commands.hybrid_command(
        name="print_roles",
        description="This prints all the roles that can be selected"
    )
    async def print_roles(self, context: Context):
        """
        This is the command that prints all the choosable roles
        :param context: The application command context
        """

        embed = discord.Embed(
            title="Roles:",
            colour=0xFF00DC
        )
        for role_id in self.roles.items():
            role = context.guild.get_role(int(role_id))
            if role:
                embed.add_field(
                    name=role.name,
                    color=role.color,
                )
        await context.send(embed=embed)

    @command.hybrid_command(
        name="add_role",
        description="This adds a role that can be selected"
    )
    async def add_roles(self, context: Context, role: discord.role=None):
        if role is None:
            print(TODO)
            #TODO Role stuff
        else:
            self.update_roles(str(role.id), str(context.guild.id))

async def setup(bot) -> None:
    await bot.add_cog(Selfroles(bot))