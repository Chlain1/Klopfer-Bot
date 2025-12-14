import json
import discord
from discord.ext import commands
from discord.ext.commands import Context

ROLES_TO_SELECT = "self_roles.json"


class Selfroles(commands.Cog, name="selfroles"):
    def __init__(self, bot):
        self.bot = bot
        try:
            with open(ROLES_TO_SELECT, "r") as file:
                data = json.load(file)
        except (FileNotFoundError, json.JSONDecodeError):
            data = {}
        # Ensure consistent structure: { guild_id(str): [role_id(str), ...] }
        self.roles: dict[str, list[str]] = {
            str(g): [str(r) for r in rs] for g, rs in data.items()
        }

    def _ensure_guild(self, guild_id: int) -> None:
        gid = str(guild_id)
        if gid not in self.roles:
            self.roles[gid] = []

    async def update_roles(self, role_id: str, server_id: str):
        self._ensure_guild(int(server_id))
        if role_id not in self.roles[server_id]:
            self.roles[server_id].append(role_id)
        await self.save_roles()

    async def save_roles(self):
        with open(ROLES_TO_SELECT, "w") as file:
            json.dump(self.roles, file, indent=2)

    @commands.hybrid_command(
        name="print_roles",
        description="This prints all the roles that can be selected",
    )
    async def print_roles(self, context: Context):
        if not context.guild:
            return await context.send("Use this in a server.")
        gid = str(context.guild.id)
        role_ids = self.roles.get(gid, [])
        if not role_ids:
            return await context.send("No self-assignable roles configured yet.")

        embed = discord.Embed(title="Roles:", colour=0xFF00DC)
        for role_id in role_ids:
            role = context.guild.get_role(int(role_id))
            if role:
                embed.add_field(
                    name=role.name,
                    value=f"<@&{role.id}>",
                    inline=False,
                )
        await context.send(embed=embed)

    @commands.hybrid_command(
        name="add_role",
        description="Open a dropdown to pick roles that should be self-assignable",
    )
    @commands.has_guild_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def add_roles(self, context: Context, role: discord.Role | None = None):
        if not context.guild:
            return await context.send("Use this in a server.")

        # Optional: allow adding one role directly via argument
        if role is not None:
            await self.update_roles(str(role.id), str(context.guild.id))
            return await context.send(f"Added {role.mention} as self-assignable.")

        embed = discord.Embed(
            title="Role Selector",
            description="Select the roles that should be Self-Roles",
            colour=0xFF00DC,
        )
        view = RoleView(context, self, mode="admin")
        if not view.select.options:
            return await context.send(
                "No assignable roles found (excludes @everyone, managed roles, and roles above my top role)."
            )
        await context.send(embed=embed, view=view)

    @commands.hybrid_command(
        name="get_role",
        description="Opens a dropdown to pick the roles you can assign yourself",
    )
    @commands.bot_has_guild_permissions(manage_roles=True)
    async def get_role(self, context: Context):
        if not context.guild:
            return await context.send("Use this in a server.")
        
        gid = str(context.guild.id)
        role_ids = self.roles.get(gid, [])
        
        if not role_ids:
            return await context.send("No self-assignable roles configured yet.")
        
        embed = discord.Embed(
            title="Self Role Selection",
            description="Choose which roles you want to assign/remove from yourself",
            colour=0xFF00DC,
        )
        view = RoleView(context, self, mode="user")
        
        if not view.select.options:
            return await context.send("No valid self-assignable roles found.")
        
        await context.send(embed=embed, view=view)


class RoleView(discord.ui.View):
    def __init__(self, ctx: Context, cog: Selfroles, mode: str = "admin"):
        super().__init__(timeout=300)
        self.ctx = ctx
        self.cog = cog
        self.mode = mode
        self.select = RoleSelect(ctx, cog, mode)
        self.add_item(self.select)

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True


class RoleSelect(discord.ui.Select):
    def __init__(self, ctx: Context, cog: Selfroles, mode: str = "admin"):
        self.ctx = ctx
        self.cog = cog
        self.mode = mode

        guild = ctx.guild
        
        if mode == "admin":
            # Admin mode: show all assignable roles from guild
            me = guild.me
            roles = [
                r for r in guild.roles
                if r != guild.default_role and not r.managed and (r < me.top_role)
            ]
            roles = sorted(roles, key=lambda r: r.position, reverse=True)[:25]
            options = [
                discord.SelectOption(label=r.name[:100], value=str(r.id))
                for r in roles
            ]
            placeholder = "Choose role(s) for Self Roles"
        else:
            # User mode: show only self-assignable roles from config
            gid = str(guild.id)
            role_ids = cog.roles.get(gid, [])
            options = []
            for role_id in role_ids:
                role = guild.get_role(int(role_id))
                if role:
                    options.append(
                        discord.SelectOption(
                            label=role.name[:100],
                            value=str(role.id),
                            description=f"Toggle {role.name}"
                        )
                    )
            options = options[:25]
            placeholder = "Choose role(s) to toggle"

        super().__init__(
            placeholder=placeholder,
            min_values=1 if options else 0,
            max_values=min(len(options), 25) if options else 1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        if self.mode == "admin":
            # Admin mode: add roles to config
            if interaction.user.id != self.ctx.author.id:
                return await interaction.response.send_message("Not your menu.", ephemeral=True)

            gid = str(interaction.guild.id)
            self.cog._ensure_guild(interaction.guild.id)

            existing = set(self.cog.roles.get(gid, []))
            selected = set(self.values)
            updated = list(existing | selected)
            self.cog.roles[gid] = updated
            await self.cog.save_roles()

            names = []
            for rid in selected:
                r = interaction.guild.get_role(int(rid))
                if r:
                    names.append(r.name)

            await interaction.response.send_message(
                f"Added as self-assignable: {', '.join(names)}" if names else "Updated.",
                ephemeral=True,
            )
        else:
            # User mode: toggle roles on member
            member = interaction.guild.get_member(interaction.user.id)
            if not member:
                return await interaction.response.send_message(
                    "Could not find you in this server.", ephemeral=True
                )

            added = []
            removed = []
            
            for role_id in self.values:
                role = interaction.guild.get_role(int(role_id))
                if not role:
                    continue
                
                if role in member.roles:
                    try:
                        await member.remove_roles(role)
                        removed.append(role.name)
                    except discord.Forbidden:
                        pass
                else:
                    try:
                        await member.add_roles(role)
                        added.append(role.name)
                    except discord.Forbidden:
                        pass

            response_parts = []
            if added:
                response_parts.append(f"✅ Added: {', '.join(added)}")
            if removed:
                response_parts.append(f"❌ Removed: {', '.join(removed)}")
            
            message = "\n".join(response_parts) if response_parts else "No changes made."
            await interaction.response.send_message(message, ephemeral=True)


async def setup(bot) -> None:
    await bot.add_cog(Selfroles(bot))