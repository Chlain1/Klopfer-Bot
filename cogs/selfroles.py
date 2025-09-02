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

    @commands.hybrid_command(
        name="add_role",
        description="This adds a role that can be selected"
    )
    async def add_roles(self, context: Context, role: discord.role=None):
        if role is None:
            embed = discord.Embed(
                title="Role Selector",
                description="Select the roles that should be Self-Roles",
                color=0xFF00DC
            )

            view = RoleView
            await context.send(embed=embed, view=view)
        else:
            self.update_roles(str(role.id), str(context.guild.id))

class RoleView(discord.ui.View):
    def __init__(self, ctx: Context, options: list[discord.SelectOption]):
        super().__init__(timeout=300)
        self.ctx = ctx
        self.add_item(RoleSelect(ctx, options))
    async def on_timeout(self):
        for item in self.children:
            item.disable = True


class RoleSelect(discord.ui.Select):
    def __init__(self, ctx: Context, options: list[discord.SelectOption]):
        options = []
        for role in ctx.guild.roles:
            options.append(discord.SelectOption(label=role.name, value=str(role.id)))
        super().__init__(
            placeholder="Choose another Role for Self Roles",
            min_values=1,
            max_values=1,
            options=options,
        )
        self.ctx = ctx
    
    async def callback(self, interaction: discord.Interaction):
        print(TODO)
        # TODO do it

async def setup(bot) -> None:
    await bot.add_cog(Selfroles(bot))