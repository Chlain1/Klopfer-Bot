import discord
from discord.ext import commands
from pytube import YouTube
import os
import asyncio
from collections import deque

class Music(commands.Cog, name="music"):
    def __init__(self, bot) -> None:
        self.bot = bot

    @commands.command(
        name="play",
        description="This command plays single songs",
    )
    async def play(self, ctx: commands.Context, url: str) -> None:
        """
        This command plays a song from a given URL in the voice channel that the command author is in.

        :param ctx: The command context.
        :param url: The URL of the song to play.
        """
        # Check if the bot is already connected to a voice channel
        voice_channel = discord.utils.get(ctx.bot.voice_clients, guild=ctx.guild)
        if ctx.voice_client is not None:
            # If the bot is in the same voice channel as the command author
            if ctx.voice_client.channel == ctx.author.voice.channel:
                # Download the audio from the URL and play it
                try:
                    youtube = YouTube(url)
                    video = youtube.streams.filter(only_audio=True).first()
                    filename = video.download()
                    voice_channel.play(discord.FFmpegPCMAudio(filename))
                    await asyncio.sleep(1)  # wait for the audio to start playing
                    print("audio should play now")
                    # Wait for the audio to finish playing before deleting the file
                    while voice_channel.is_playing():
                        await asyncio.sleep(1)
                    os.remove(filename)  # remove the audio file after playing
                except Exception as e:
                    await ctx.send(f"An error occurred while downloading the video: {e}")

            else:
                # If the bot is in a different voice channel
                await ctx.send('The bot is already in a different voice channel.')
        else:
            # If the bot is not in a voice channel, connect to the command author's channel
            channel = ctx.author.voice.channel
            voice_channel = await channel.connect()
            # Download the audio from the URL and play it
            try:
                youtube = YouTube(url)
                video = youtube.streams.filter(only_audio=True).first()
                filename = video.download()
                voice_channel.play(discord.FFmpegPCMAudio(filename))
                await asyncio.sleep(1)  # wait for the audio to start playing
                print("audio should play now")
                # Wait for the audio to finish playing before deleting the file
                while voice_channel.is_playing():
                    await asyncio.sleep(1)
                os.remove(filename)  # remove the audio file after playing
            except Exception as e:
                await ctx.send(f"An error occurred while downloading the video: {e}")

    @commands.command(
        name="stop",
        description="This command stops the music",
    )
    async def stop(self, ctx: commands.Context) -> None:
        voice_channel = discord.utils.get(ctx.bot.voice_clients, guild=ctx.guild)
        if voice_channel and voice_channel.is_playing():
            voice_channel.stop()
            await ctx.send("Stopped the music.")
        else:
            await ctx.send("No music is playing right now.")

    @commands.command(
        name="leave",
        description="With this command the bot leaves the voice channel",
    )
    async def leave(self, ctx: commands.Context) -> None:
        voice_channel = discord.utils.get(ctx.bot.voice_clients, guild=ctx.guild)
        if voice_channel:
            await voice_channel.disconnect()
        else:
            await ctx.send("I'm not in a voice channel.")

    async def cog_command_error(self, ctx: commands.Context, error: commands.CommandError):
        await ctx.send('An error occurred: {}'.format(str(error)))

async def setup(bot) -> None:
    await bot.add_cog(Music(bot))