import json
import asyncio
from datetime import datetime

import discord
from discord.ext import commands, tasks
from discord.ext.commands import Context
import feedparser

YOUTUBE_SUBSCRIPTIONS_FILE = "youtube_subscriptions.json"


class YouTube(commands.Cog, name="youtube"):
    def __init__(self, bot) -> None:
        self.bot = bot
        self.subscriptions = self.load_subscriptions()
        self.check_youtube_updates.start()

    def cog_unload(self):
        self.check_youtube_updates.cancel()

    def load_subscriptions(self) -> dict:
        """Load YouTube subscriptions from JSON file."""
        try:
            with open(YOUTUBE_SUBSCRIPTIONS_FILE, "r") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def save_subscriptions(self) -> None:
        """Save YouTube subscriptions to JSON file."""
        with open(YOUTUBE_SUBSCRIPTIONS_FILE, "w") as f:
            json.dump(self.subscriptions, f, indent=2)

    @commands.hybrid_command(
        name="youtube_subscribe",
        description="Subscribe to YouTube channel notifications.",
    )
    @commands.has_permissions(manage_guild=True)
    async def youtube_subscribe(self, context: Context) -> None:
        """
        Subscribe to YouTube channel notifications via modal.

        :param context: The hybrid command context.
        """
        if context.interaction is None:
            embed = discord.Embed(
                description="❌ This command only works as a slash command: `/youtube_subscribe`",
                color=0xE02B2B,
            )
            return await context.send(embed=embed)
        
        modal = YouTubeSubscribeModal(self, context.guild)
        await context.interaction.response.send_modal(modal)

    @commands.hybrid_command(
        name="youtube_unsubscribe",
        description="Unsubscribe from YouTube channel notifications.",
    )
    @commands.has_permissions(manage_guild=True)
    async def youtube_unsubscribe(self, context: Context) -> None:
        """
        Unsubscribe from YouTube channel notifications via dropdown.

        :param context: The hybrid command context.
        """
        guild_id = str(context.guild.id)

        if guild_id not in self.subscriptions or not self.subscriptions[guild_id]:
            embed = discord.Embed(
                description="No YouTube subscriptions found for this server.",
                color=0xE02B2B,
            )
            return await context.send(embed=embed)

        embed = discord.Embed(
            title="Unsubscribe from YouTube Channel",
            description="Select a channel to unsubscribe from:",
            color=0xFF0000,
        )
        view = YouTubeUnsubscribeView(self, context.guild)
        await context.send(embed=embed, view=view)

    @commands.hybrid_command(
        name="youtube_list",
        description="List all YouTube subscriptions for this server.",
    )
    @commands.has_permissions(manage_guild=True)
    async def youtube_list(self, context: Context) -> None:
        """
        List all YouTube subscriptions for this server.

        :param context: The hybrid command context.
        """
        guild_id = str(context.guild.id)

        if guild_id not in self.subscriptions or not self.subscriptions[guild_id]:
            embed = discord.Embed(
                description="No YouTube subscriptions found for this server.",
                color=0xE02B2B,
            )
            return await context.send(embed=embed)

        embed = discord.Embed(
            title="YouTube Subscriptions",
            description="List of all active YouTube subscriptions:",
            color=0xFF0000,
        )

        for sub in self.subscriptions[guild_id]:
            channel = self.bot.get_channel(int(sub["channel_id"]))
            role = context.guild.get_role(int(sub["role_id"]))
            channel_mention = channel.mention if channel else "Unknown Channel"
            role_mention = role.mention if role else "@everyone"

            embed.add_field(
                name=f"📺 {sub['youtube_channel']}",
                value=f"Channel: {channel_mention}\nRole: {role_mention}",
                inline=False,
            )

        await context.send(embed=embed)

    @tasks.loop(minutes=10)
    async def check_youtube_updates(self) -> None:
        """Check for new YouTube videos every 10 minutes."""
        await self.bot.wait_until_ready()

        for guild_id, subscriptions in self.subscriptions.items():
            guild = self.bot.get_guild(int(guild_id))
            if not guild:
                continue

            for sub in subscriptions:
                try:
                    # Get YouTube RSS feed
                    youtube_id = sub["youtube_channel"]
                    
                    # Support both channel IDs and handles
                    if youtube_id.startswith("@"):
                        # For handles, we need to use a different approach
                        # For now, skip handles (would need YouTube API)
                        continue
                    elif youtube_id.startswith("UC"):
                        rss_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={youtube_id}"
                    else:
                        # Assume it's a channel ID
                        rss_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={youtube_id}"

                    # Parse RSS feed
                    feed = await asyncio.to_thread(feedparser.parse, rss_url)
                    
                    if not feed.entries:
                        continue

                    latest_video = feed.entries[0]
                    video_id = latest_video.yt_videoid
                    video_url = latest_video.link
                    video_title = latest_video.title

                    # Check if this is a new video
                    if sub["last_video_id"] != video_id:
                        # Update last video ID
                        sub["last_video_id"] = video_id
                        self.save_subscriptions()

                        # Send notification only if it's not the first check
                        if sub.get("last_video_id") is not None or len(self.subscriptions[guild_id]) > 0:
                            channel = self.bot.get_channel(int(sub["channel_id"]))
                            if channel:
                                role = guild.get_role(int(sub["role_id"]))
                                role_mention = role.mention if role else "@everyone"

                                embed = discord.Embed(
                                    title="🎬 New YouTube Video!",
                                    description=f"**{video_title}**\n\n{video_url}",
                                    color=0xFF0000,
                                    timestamp=datetime.now(),
                                )
                                embed.set_footer(text=f"Channel: {youtube_id}")

                                await channel.send(content=role_mention, embed=embed)

                except Exception as e:
                    self.bot.logger.error(
                        f"Error checking YouTube updates for {sub.get('youtube_channel', 'unknown')}: {e}"
                    )
                    continue


class YouTubeSubscribeModal(discord.ui.Modal, title="Subscribe to YouTube Channel"):
    def __init__(self, cog: 'YouTube', guild: discord.Guild):
        super().__init__()
        self.cog = cog
        self.guild = guild

    youtube_channel = discord.ui.TextInput(
        label="YouTube Channel ID",
        placeholder="UC... or @username",
        required=True,
        max_length=100,
    )

    discord_channel = discord.ui.TextInput(
        label="Discord Channel ID",
        placeholder="Channel ID where notifications will be sent",
        required=True,
        max_length=20,
    )

    role_id = discord.ui.TextInput(
        label="Role ID (optional)",
        placeholder="Leave empty for @everyone",
        required=False,
        max_length=20,
    )

    async def on_submit(self, interaction: discord.Interaction):
        youtube_channel_id = self.youtube_channel.value.strip()
        discord_channel_id = self.discord_channel.value.strip()
        role_id_value = self.role_id.value.strip()

        # Validate Discord channel
        try:
            channel = self.guild.get_channel(int(discord_channel_id))
            if not channel or not isinstance(channel, discord.TextChannel):
                embed = discord.Embed(
                    description="❌ Invalid Discord channel ID!",
                    color=0xE02B2B,
                )
                return await interaction.response.send_message(embed=embed, ephemeral=True)
        except ValueError:
            embed = discord.Embed(
                description="❌ Discord channel ID must be a number!",
                color=0xE02B2B,
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        # Validate role ID (optional)
        if role_id_value:
            try:
                role = self.guild.get_role(int(role_id_value))
                if not role:
                    embed = discord.Embed(
                        description="❌ Invalid role ID!",
                        color=0xE02B2B,
                    )
                    return await interaction.response.send_message(embed=embed, ephemeral=True)
                role_id = str(role.id)
                role_mention = role.mention
            except ValueError:
                embed = discord.Embed(
                    description="❌ Role ID must be a number!",
                    color=0xE02B2B,
                )
                return await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            role_id = str(self.guild.default_role.id)
            role_mention = "@everyone"

        guild_id = str(self.guild.id)

        # Initialize guild subscriptions if not exists
        if guild_id not in self.cog.subscriptions:
            self.cog.subscriptions[guild_id] = []

        # Check if subscription already exists
        for sub in self.cog.subscriptions[guild_id]:
            if sub["youtube_channel"] == youtube_channel_id:
                embed = discord.Embed(
                    description=f"❌ Already subscribed to **{youtube_channel_id}**!",
                    color=0xE02B2B,
                )
                return await interaction.response.send_message(embed=embed, ephemeral=True)

        # Add new subscription
        subscription = {
            "youtube_channel": youtube_channel_id,
            "channel_id": discord_channel_id,
            "role_id": role_id,
            "last_video_id": None,
        }
        self.cog.subscriptions[guild_id].append(subscription)
        self.cog.save_subscriptions()

        embed = discord.Embed(
            description=f"✅ Successfully subscribed to **{youtube_channel_id}**!\n"
            f"📺 Notifications will be sent to {channel.mention}\n"
            f"🔔 Role to ping: {role_mention}",
            color=0x00FF00,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


class YouTubeUnsubscribeView(discord.ui.View):
    def __init__(self, cog: 'YouTube', guild: discord.Guild):
        super().__init__(timeout=300)
        self.cog = cog
        self.guild = guild
        self.select = YouTubeUnsubscribeSelect(cog, guild)
        self.add_item(self.select)

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True


class YouTubeUnsubscribeSelect(discord.ui.Select):
    def __init__(self, cog: 'YouTube', guild: discord.Guild):
        self.cog = cog
        self.guild = guild
        guild_id = str(guild.id)

        # Get all subscriptions for this guild
        subscriptions = cog.subscriptions.get(guild_id, [])

        # Build options
        options = []
        for sub in subscriptions:
            channel = guild.get_channel(int(sub["channel_id"]))
            channel_name = channel.name if channel else "Unknown Channel"
            options.append(
                discord.SelectOption(
                    label=sub["youtube_channel"][:100],
                    value=sub["youtube_channel"],
                    description=f"Notifications in #{channel_name}"
                )
            )

        options = options[:25]  # Discord limit

        super().__init__(
            placeholder="Choose a channel to unsubscribe",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        youtube_channel_id = self.values[0]
        guild_id = str(self.guild.id)

        # Remove subscription
        initial_count = len(self.cog.subscriptions[guild_id])
        self.cog.subscriptions[guild_id] = [
            sub
            for sub in self.cog.subscriptions[guild_id]
            if sub["youtube_channel"] != youtube_channel_id
        ]

        if len(self.cog.subscriptions[guild_id]) == initial_count:
            embed = discord.Embed(
                description=f"❌ Subscription not found for **{youtube_channel_id}**.",
                color=0xE02B2B,
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        self.cog.save_subscriptions()
        embed = discord.Embed(
            description=f"✅ Successfully unsubscribed from **{youtube_channel_id}**!",
            color=0x00FF00,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

        # Disable the view
        for item in self.view.children:
            item.disabled = True
        await interaction.message.edit(view=self.view)


async def setup(bot) -> None:
    await bot.add_cog(YouTube(bot))
