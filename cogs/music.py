import asyncio
import json
import os
import random
import re
import sys

import discord
from discord.ext import commands, tasks

url_rx = re.compile(r'https?://(?:www\.)?.+')

# yt-dlp is run as a subprocess instead of being imported as a module. Every
# extraction therefore picks up whatever version is currently installed, which
# lets the self-update task below fix site breakage (usually YouTube) while the
# bot keeps running - no cookies, no restart, no redeploy needed.
YTDLP_COMMON_ARGS = [
    '--quiet',
    '--no-warnings',
    '--no-check-certificates',
    '--source-address', '0.0.0.0',
    '--default-search', 'ytsearch',
]

# Search providers tried in order when the user gives a plain search term (or a
# track from a search can't be streamed anymore): YouTube first, SoundCloud as
# fallback. Both are yt-dlp search prefixes, so adding another provider here is
# enough to enable it.
SEARCH_PROVIDERS = ('ytsearch', 'scsearch')

# How long a single yt-dlp invocation may take before it's killed, so a hanging
# extractor can't freeze the queue indefinitely.
EXTRACTION_TIMEOUT = 30

# Caps how many tracks a single playlist link can enqueue at once. Also passed
# to yt-dlp via --playlist-items so huge playlists aren't even listed fully.
MAX_PLAYLIST_TRACKS = 50

# After this many failed track resolutions in a row, give up on repeat/repeat-queue
# instead of retrying the same broken track (or cycling a queue full of broken tracks)
# forever.
MAX_CONSECUTIVE_FAILURES = 3

# Reconnect flags help FFmpeg survive brief network hiccups while streaming instead of
# just dying, since it's reading the audio live over the network rather than from a file.
FFMPEG_BEFORE_OPTIONS = '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5'
FFMPEG_OPTIONS = '-vn'


class ExtractionError(Exception):
    """Raised when yt-dlp fails to resolve a query."""


def _pot_provider_args() -> list[str]:
    """
    The bgutil-ytdlp-pot-provider plugin (installed alongside yt-dlp) generates the
    "PO tokens" YouTube demands from IPs it distrusts (e.g. datacenter/server IPs),
    without any account or cookies. It needs the companion provider service from
    docker-compose.yml; when POT_PROVIDER_URL is unset (e.g. local development),
    yt-dlp simply runs without it.
    """
    base_url = os.environ.get('POT_PROVIDER_URL')
    if not base_url:
        return []
    return ['--extractor-args', f'youtubepot-bgutilhttp:base_url={base_url}']


def _last_error_line(stderr: bytes) -> str:
    lines = [line.strip() for line in stderr.decode(errors='replace').splitlines() if line.strip()]
    for line in reversed(lines):
        if line.startswith('ERROR:'):
            return line.removeprefix('ERROR:').strip()[:300]
    return (lines[-1] if lines else 'unknown yt-dlp error')[:300]


async def _run_ytdlp(*args: str) -> dict | None:
    process = await asyncio.create_subprocess_exec(
        sys.executable, '-m', 'yt_dlp', *YTDLP_COMMON_ARGS, *_pot_provider_args(), *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), EXTRACTION_TIMEOUT)
    except asyncio.TimeoutError:
        process.kill()
        await process.wait()
        raise ExtractionError(f'yt-dlp timed out after {EXTRACTION_TIMEOUT}s')

    if process.returncode != 0:
        raise ExtractionError(_last_error_line(stderr))
    if not stdout.strip():
        return None
    try:
        return json.loads(stdout)
    except ValueError as exc:
        raise ExtractionError(f'yt-dlp returned invalid JSON: {exc}')


async def _extract_flat(query: str) -> dict | None:
    """
    Cheaply lists what a query/URL points at (search result, single track or
    playlist) without resolving playable stream URLs for every entry up front.
    """
    return await _run_ytdlp(
        '-J', '--flat-playlist', '--playlist-items', f'1:{MAX_PLAYLIST_TRACKS}', query
    )


async def _extract_stream(query: str) -> dict | None:
    """
    Resolves the direct, streamable audio URL of a single track, right before
    playback. Nothing is ever downloaded: FFmpeg reads straight from the
    returned URL and pipes the decoded audio into Discord.
    """
    info = await _run_ytdlp('-J', '--format', 'bestaudio/best', '--no-playlist', query)
    # Search queries come back wrapped in a one-entry playlist; unwrap it.
    if info and info.get('entries') is not None:
        entries = [entry for entry in info['entries'] if entry]
        info = entries[0] if entries else None
    return info


class Track:
    def __init__(self, *, query, title, webpage_url, duration, requester, search_query=None):
        # `query` is what gets re-resolved to a stream URL right before playback, since
        # direct stream URLs expire and shouldn't be resolved for the whole queue at once.
        self.query = query
        self.title = title
        self.webpage_url = webpage_url
        self.duration = duration
        self.requester = requester
        # The user's original search text, if this track came from a search. Kept so
        # playback can fall back to another provider when the resolved URL breaks.
        self.search_query = search_query
        # Stream info resolved ahead of time while the previous track plays, so the
        # transition between tracks is instant. Consumed (and cleared) by _play_next.
        self.prefetched: dict | None = None


class GuildMusicState:
    def __init__(self):
        self.queue: list[Track] = []
        self.current: Track | None = None
        self.repeat = False
        self.repeat_queue = False
        self.channel_id: int | None = None
        self.lowpass_freq: float = 0.0
        # Circuit breaker for _play_next: without this, `repeat`/`repeat_queue` would
        # retry a permanently broken track (e.g. a taken-down video) forever, recursing
        # without bound instead of ever reaching an empty queue.
        self.consecutive_failures: int = 0


def _track_from_entry(entry: dict, requester_id: int, search_query: str | None = None) -> Track:
    webpage_url = entry.get('webpage_url')
    raw_url = entry.get('url')
    if webpage_url:
        query = webpage_url
    elif raw_url and url_rx.match(raw_url):
        query = raw_url
    elif entry.get('id') and entry.get('ie_key', '').lower() == 'youtube':
        # Only YouTube's flat listing is known to sometimes return a bare video ID
        # instead of a full URL; don't guess a YouTube URL for other extractors.
        query = f"https://www.youtube.com/watch?v={entry['id']}"
    else:
        query = raw_url

    return Track(
        query=query,
        title=entry.get('title') or 'Unknown title',
        webpage_url=webpage_url or query,
        duration=entry.get('duration'),
        requester=requester_id,
        search_query=search_query,
    )


def _tracks_from_info(info: dict | None, requester_id: int, search_query: str | None):
    if not info:
        return [], None

    entries = info.get('entries')
    if entries is not None:
        entries = [entry for entry in entries if entry][:MAX_PLAYLIST_TRACKS]
        tracks = [_track_from_entry(entry, requester_id, search_query) for entry in entries]
        # Searches also come back as a "playlist", but their title ("some song") is
        # not a real playlist title.
        playlist_title = info.get('title') if search_query is None else None
        return tracks, playlist_title

    return [_track_from_entry(info, requester_id, search_query)], None


async def ensure_voice(ctx: commands.Context):
    """
    A check that is invoked before any commands marked with `@commands.check(ensure_voice)` can run.

    This makes sure the invoking user is in a voice channel, and connects the bot to it
    for commands that are allowed to start playback.
    """
    if ctx.guild is None:
        raise commands.NoPrivateMessage()

    # These are commands that require the bot to join a voice channel (i.e. initiating playback).
    # Commands such as volume/skip etc don't require the bot to be in a voice channel so don't need listing here.
    should_connect = ctx.command.name in ('play', 'horror', 'fight', 'travel', 'tavern')

    voice_client = ctx.voice_client

    if not ctx.author.voice or not ctx.author.voice.channel:
        if voice_client is not None:
            raise commands.CommandInvokeError('You need to join my voice channel first.')
        raise commands.CommandInvokeError('Join a voicechannel first.')

    voice_channel = ctx.author.voice.channel

    if voice_client is None:
        if not should_connect:
            raise commands.CommandInvokeError("I'm not playing music.")

        permissions = voice_channel.permissions_for(ctx.me)
        if not permissions.connect or not permissions.speak:
            raise commands.CommandInvokeError('I need the `CONNECT` and `SPEAK` permissions.')

        if voice_channel.user_limit > 0:
            if len(voice_channel.members) >= voice_channel.user_limit and not ctx.me.guild_permissions.move_members:
                raise commands.CommandInvokeError('Your voice channel is full!')

        await voice_channel.connect()
    elif voice_client.channel.id != voice_channel.id:
        raise commands.CommandInvokeError('You need to be in my voicechannel.')

    return True


class Music(commands.Cog, name="music"):
    def __init__(self, bot):
        self.bot = bot
        self.guild_states: dict[int, GuildMusicState] = {}
        # Keeps strong references to fire-and-forget prefetch tasks so they aren't
        # garbage collected mid-flight.
        self._prefetch_tasks: set[asyncio.Task] = set()

    async def cog_load(self):
        self.update_ytdlp.start()

    async def cog_unload(self):
        self.update_ytdlp.cancel()
        for task in self._prefetch_tasks:
            task.cancel()

    @tasks.loop(hours=12)
    async def update_ytdlp(self):
        """
        Upgrades yt-dlp and its PO-token plugin in place (on startup and every 12
        hours after). Since extraction runs yt-dlp as a subprocess, the new version
        is used on the very next song - site breakage heals itself without
        redeploying the bot.
        """
        before = await self._ytdlp_version()

        command = [sys.executable, '-m', 'pip', 'install', '--upgrade', '--quiet']
        if sys.prefix == sys.base_prefix:
            # Not in a virtualenv (e.g. the Docker container, which runs as a non-root
            # user): install into the user site, which is writable and shadows the
            # system-wide copy.
            command.append('--user')
        command += ['yt-dlp', 'bgutil-ytdlp-pot-provider']

        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await asyncio.wait_for(process.communicate(), 300)
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            self.bot.logger.warning('yt-dlp self-update timed out')
            return
        except OSError as exc:
            self.bot.logger.warning(f'yt-dlp self-update failed to start: {exc}')
            return

        if process.returncode != 0:
            self.bot.logger.warning(f'yt-dlp self-update failed: {_last_error_line(stderr)}')
            return

        after = await self._ytdlp_version()
        if after != before:
            self.bot.logger.info(f'yt-dlp updated: {before} -> {after}')

    async def _ytdlp_version(self) -> str:
        try:
            process = await asyncio.create_subprocess_exec(
                sys.executable, '-m', 'yt_dlp', '--version',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            stdout, _ = await asyncio.wait_for(process.communicate(), 60)
            return stdout.decode().strip() or 'unknown'
        except (OSError, asyncio.TimeoutError):
            return 'unknown'

    def get_state(self, guild_id: int) -> GuildMusicState:
        state = self.guild_states.get(guild_id)
        if state is None:
            state = GuildMusicState()
            self.guild_states[guild_id] = state
        return state

    async def cog_command_error(self, ctx, error):
        if isinstance(error, commands.CommandInvokeError):
            await ctx.send(error.original)
            # The above handles errors thrown in this cog and shows them to the user.
            # This shouldn't be a problem as the only errors thrown in this cog are from `ensure_voice`
            # which contain a reason string, such as "Join a voicechannel" etc.

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        # Clean up guild state once the bot itself leaves/is removed from a voice channel,
        # so a stale queue doesn't start playing the next time someone joins.
        if member.id != self.bot.user.id or after.channel is not None:
            return
        state = self.guild_states.pop(member.guild.id, None)
        if state:
            state.queue.clear()
            state.current = None

    async def resolve_tracks(self, query: str, requester_id: int):
        """
        Resolves a query (URL or search term) to a list of Tracks and an optional
        playlist title. This only lists what's available; it does not resolve a
        playable stream URL, that only happens right before a track is played.

        Plain search terms are tried against each provider in SEARCH_PROVIDERS
        until one returns a result, so a broken provider doesn't take the whole
        play command down with it.
        """
        if url_rx.match(query):
            info = await _extract_flat(query)
            return _tracks_from_info(info, requester_id, None)

        last_error = None
        for provider in SEARCH_PROVIDERS:
            try:
                info = await _extract_flat(f'{provider}1:{query}')
            except ExtractionError as exc:
                self.bot.logger.warning(f"Search via {provider} failed for {query!r}: {exc}")
                last_error = exc
                continue
            tracks, _ = _tracks_from_info(info, requester_id, query)
            if tracks:
                return tracks, None

        if last_error is not None:
            raise last_error
        return [], None

    async def _resolve_stream_info(self, track: Track) -> dict | None:
        """
        Resolves the playable stream info for a track. If the track came from a
        search and its resolved URL no longer works, the original search text is
        retried on each provider so playback can transparently switch provider.
        """
        candidates = [track.query] if track.query else []
        if track.search_query:
            for provider in SEARCH_PROVIDERS:
                candidate = f'{provider}1:{track.search_query}'
                if candidate not in candidates:
                    candidates.append(candidate)

        last_error = None
        for candidate in candidates:
            try:
                info = await _extract_stream(candidate)
            except ExtractionError as exc:
                last_error = exc
                continue
            if info and info.get('url'):
                return info

        if last_error is not None:
            raise last_error
        return None

    def _schedule_prefetch(self, state: GuildMusicState):
        # Resolve the next track's stream URL in the background while the current
        # track plays, so the transition doesn't pause for a yt-dlp round trip.
        next_track = state.queue[0] if state.queue else None
        if next_track is None or next_track.prefetched is not None:
            return

        async def prefetch(track: Track):
            try:
                track.prefetched = await self._resolve_stream_info(track)
            except ExtractionError:
                # Resolution is retried (with a user-visible error) when it's
                # actually this track's turn to play.
                pass

        task = asyncio.get_running_loop().create_task(prefetch(next_track))
        self._prefetch_tasks.add(task)
        task.add_done_callback(self._prefetch_tasks.discard)

    async def _notify(self, guild: discord.Guild, state: GuildMusicState, content: str):
        channel = guild.get_channel(state.channel_id) if state.channel_id else None
        if channel:
            await channel.send(content)

    async def _play_next(self, guild_id: int):
        state = self.guild_states.get(guild_id)
        guild = self.bot.get_guild(guild_id)

        if state is None or guild is None or guild.voice_client is None:
            return

        if state.consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
            state.consecutive_failures = 0
            if state.repeat or state.repeat_queue:
                state.repeat = False
                state.repeat_queue = False
                await self._notify(
                    guild, state,
                    "⚠ | Wiederholung wurde deaktiviert, da ein Track wiederholt nicht geladen werden konnte."
                )

        if state.repeat and state.current is not None:
            track = state.current
        else:
            if state.repeat_queue and state.current is not None:
                state.queue.append(state.current)
            if not state.queue:
                state.current = None
                await guild.voice_client.disconnect(force=True)
                return
            track = state.queue.pop(0)

        state.current = track

        info, track.prefetched = track.prefetched, None
        if not info:
            try:
                info = await self._resolve_stream_info(track)
            except Exception as exc:
                state.consecutive_failures += 1
                await self._notify(guild, state, f"⚠ | Konnte `{track.title}` nicht laden: {exc}")
                return await self._play_next(guild_id)

        stream_url = info.get('url') if info else None
        if not stream_url:
            state.consecutive_failures += 1
            await self._notify(guild, state, f"⚠ | Konnte keinen Stream für `{track.title}` finden.")
            return await self._play_next(guild_id)

        state.consecutive_failures = 0

        # Some extractors (e.g. SoundCloud) don't include a title in the flat listing
        # used by resolve_tracks(), only in the full extraction done here.
        if track.title == 'Unknown title' and info.get('title'):
            track.title = info['title']

        options = FFMPEG_OPTIONS
        if state.lowpass_freq:
            options = f'{FFMPEG_OPTIONS} -af "lowpass=f={state.lowpass_freq}"'

        source = discord.FFmpegPCMAudio(stream_url, before_options=FFMPEG_BEFORE_OPTIONS, options=options)

        def _after(error):
            if error:
                self.bot.logger.warning(f"Player error in guild {guild_id}: {error}")
            future = asyncio.run_coroutine_threadsafe(self._play_next(guild_id), self.bot.loop)
            try:
                future.result()
            except Exception as exc:
                self.bot.logger.warning(f"Error advancing queue in guild {guild_id}: {exc}")

        guild.voice_client.play(source, after=_after)
        await self._notify(guild, state, f"🎶 | Now playing: **{track.title}**")
        self._schedule_prefetch(state)

    @commands.hybrid_command(
        name="play",
        description="Searches and plays a song from a given query."
    )
    @commands.check(ensure_voice)
    async def play(self, ctx, *, query: str):
        # Remove leading and trailing <>. <> may be used to suppress embedding links in Discord.
        query = query.strip('<>')

        state = self.get_state(ctx.guild.id)
        state.channel_id = ctx.channel.id

        try:
            tracks, playlist_title = await self.resolve_tracks(query, ctx.author.id)
        except Exception as exc:
            return await ctx.send(f"⚠ | I couldn't load tracks for that query: {exc}")

        if not tracks:
            return await ctx.send("I couldn't find any tracks for that query.")

        state.queue.extend(tracks)

        embed = discord.Embed(color=discord.Color.blurple())
        if playlist_title and len(tracks) > 1:
            embed.title = 'Playlist Enqueued!'
            embed.description = f'{playlist_title} - {len(tracks)} tracks'
        else:
            track = tracks[0]
            embed.title = 'Track Enqueued'
            embed.description = f'[{track.title}]({track.webpage_url})'

        await ctx.send(embed=embed)

        voice_client = ctx.voice_client
        # We don't want to start playback if we're already playing/paused, as that would
        # effectively skip the current track.
        if voice_client is not None and not voice_client.is_playing() and not voice_client.is_paused():
            await self._play_next(ctx.guild.id)

    @commands.hybrid_command(
        name="lowpass",
        description="Sets the strength of the low pass filter."
    )
    @commands.check(ensure_voice)
    async def lowpass(self, ctx, strength: float):
        state = self.get_state(ctx.guild.id)

        # This enforces that strength should be a minimum of 0.
        strength = max(0.0, strength)
        # Even though there's no upper limit, we will enforce one anyway to prevent
        # extreme values from being entered. This will enforce a maximum of 100.
        strength = min(100, strength)

        embed = discord.Embed(color=discord.Color.blurple(), title='Low Pass Filter')

        state.lowpass_freq = strength
        if strength == 0.0:
            embed.description = 'Disabled **Low Pass Filter**'
        else:
            embed.description = f'Set **Low Pass Filter** strength to {strength}. This applies to the next track played.'

        await ctx.send(embed=embed)

    @commands.hybrid_command(
        name="disconnect",
        description="Disconnects the player from the voice channel and clears its queue."
    )
    @commands.check(ensure_voice)
    async def disconnect(self, ctx):
        # The necessary voice channel checks are handled in "ensure_voice."
        # We don't need to duplicate code checking them again.

        voice_client = ctx.voice_client
        if voice_client.is_playing() or voice_client.is_paused():
            voice_client.stop()
        await voice_client.disconnect(force=True)

        # Drop the whole state (queue, repeat flags, lowpass setting, ...) so a later
        # `!play` in this guild starts clean instead of inheriting stale settings.
        self.guild_states.pop(ctx.guild.id, None)

        await ctx.send('✳ | Disconnected.')

    @commands.hybrid_command(
        name="skip",
        description="Skips the current track."
    )
    @commands.check(ensure_voice)
    async def skip(self, ctx):
        voice_client = ctx.voice_client
        # The necessary voice channel checks are handled in "ensure_voice."
        # We don't need to duplicate code checking them again.

        # Stopping the current source triggers the `after` callback, which advances the queue.
        voice_client.stop()
        await ctx.send('⏭ | Skipped.')

    @commands.hybrid_command(
        name="pause",
        description="Pauses the current track."
    )
    @commands.check(ensure_voice)
    async def pause(self, ctx):
        voice_client = ctx.voice_client
        # The necessary voice channel checks are handled in "ensure_voice."
        # We don't need to duplicate code checking them again.

        if not voice_client.is_playing() and not voice_client.is_paused():
            return await ctx.send('⏸ | I am not playing anything.')
        elif voice_client.is_paused():
            return await ctx.send('⏸ | I am already paused.')
        else:
            voice_client.pause()
            await ctx.send('⏸ | Paused.')

    @commands.hybrid_command(
        name="resume",
        description="Resumes the current track."
    )
    @commands.check(ensure_voice)
    async def resume(self, ctx):
        voice_client = ctx.voice_client
        # The necessary voice channel checks are handled in "ensure_voice."
        # We don't need to duplicate code checking them again.

        if not voice_client.is_playing() and not voice_client.is_paused():
            return await ctx.send('▶ | I am not playing anything.')
        elif not voice_client.is_paused():
            return await ctx.send('▶ | I am not paused.')
        else:
            voice_client.resume()
            await ctx.send('▶ | Resumed.')

    @commands.hybrid_command(
        name="queue",
        description="Displays the current queue."
    )
    @commands.check(ensure_voice)
    async def queue(self, ctx):
        state = self.get_state(ctx.guild.id)
        # The necessary voice channel checks are handled in "ensure_voice."
        # We don't need to duplicate code checking them again.

        if not state.queue:
            return await ctx.send('📭 | The queue is empty.')

        embed = discord.Embed(color=discord.Color.blurple(), title='Queue')
        embed.description = '\n'.join(
            f'**{i + 1}.** [{t.title}]({t.webpage_url})' for i, t in enumerate(state.queue[:5])
        )
        if len(state.queue) > 5:
            embed.set_footer(text=f'and {len(state.queue) - 5} more...')
        await ctx.send(embed=embed)

    @commands.hybrid_command(
        name="clear",
        description="Clears the current queue."
    )
    @commands.check(ensure_voice)
    async def clear(self, ctx):
        state = self.get_state(ctx.guild.id)
        # The necessary voice channel checks are handled in "ensure_voice."
        # We don't need to duplicate code checking them again.

        state.queue.clear()
        await ctx.send('🗑 | Queue cleared.')

    @commands.hybrid_command(
        name="connect",
        description="Connects the bot to the voice channel."
    )
    @commands.check(ensure_voice)
    async def connect(self, ctx):
        # The necessary voice channel checks (including connecting) are handled in "ensure_voice."
        # We don't need to duplicate code checking them again.
        await ctx.send('🔊 | Connected.')

    @commands.hybrid_command(
        name="loop",
        description="Loops the current track."
    )
    @commands.check(ensure_voice)
    async def loop(self, ctx):
        state = self.get_state(ctx.guild.id)
        voice_client = ctx.voice_client
        # The necessary voice channel checks are handled in "ensure_voice."
        # We don't need to duplicate code checking them again.

        if not voice_client.is_playing() and not voice_client.is_paused():
            return await ctx.send('🔄 | I am not playing anything.')
        else:
            state.repeat = not state.repeat
            await ctx.send('🔄 | Loop is now ' + ('enabled' if state.repeat else 'disabled') + '.')

    @commands.hybrid_command(
        name="loopqueue",
        description="Loops the current queue."
    )
    @commands.check(ensure_voice)
    async def loopqueue(self, ctx):
        state = self.get_state(ctx.guild.id)
        if not state.queue:
            return await ctx.send('🔁 | The queue is empty.')
        else:
            state.repeat_queue = not state.repeat_queue
            await ctx.send('🔁 | Queue repeat is now ' + ('enabled' if state.repeat_queue else 'disabled') + '.')

    @commands.hybrid_command(
        name="shuffle",
        description="Shuffles the current queue."
    )
    @commands.check(ensure_voice)
    async def shuffle(self, ctx):
        state = self.get_state(ctx.guild.id)
        if not state.queue:
            return await ctx.send('🔀 | The queue is empty.')
        else:
            random.shuffle(state.queue)
            await ctx.send('🔀 | Queue shuffled.')

    '''
    from this point onwards are custom DnD playlist commands that I have added for a curse of strahd campaign
    '''

    @commands.hybrid_command(
        name='horror',
        description='Plays a horror themed playlist.'
    )
    @commands.check(ensure_voice)
    async def horror(self, ctx):
        state = self.get_state(ctx.guild.id)
        if state.queue:
            await ctx.invoke(self.clear)
        await self.play(ctx, query="https://on.soundcloud.com/iVhBF7R2ZucSGeG59")
        await self.play(ctx, query="https://on.soundcloud.com/nWBTwdNGhyZpjKxt7")
        await self.play(ctx, query="https://on.soundcloud.com/e6VZuGe2NPsRSfgH7")
        await self.play(ctx, query="https://on.soundcloud.com/nan8sHRxuqJ6jHT29")
        await self.shuffle(ctx)
        await self.skip(ctx)

    @commands.hybrid_command(
        name='fight',
        description='Plays a fight themed playlist.'
    )
    @commands.check(ensure_voice)
    async def fight(self, ctx):
        state = self.get_state(ctx.guild.id)
        if state.queue:
            await ctx.invoke(self.clear)
        await self.play(ctx, query="https://on.soundcloud.com/NPPDVPGDFMP8snkXA")
        await self.shuffle(ctx)
        await self.skip(ctx)

    @commands.hybrid_command(
        name='travel',
        description='Plays a travel themed playlist.'
    )
    @commands.check(ensure_voice)
    async def travel(self, ctx):
        state = self.get_state(ctx.guild.id)
        if state.queue:
            await ctx.invoke(self.clear)
        await self.play(ctx, query="https://on.soundcloud.com/96hDKXQgDRkowF4z6")
        await self.shuffle(ctx)
        await self.skip(ctx)

    @commands.hybrid_command(
        name='tavern',
        description='Plays a tavern themed playlist.'
    )
    @commands.check(ensure_voice)
    async def tavern(self, ctx):
        state = self.get_state(ctx.guild.id)
        if state.queue:
            await ctx.invoke(self.clear)
        await self.play(ctx, query="https://on.soundcloud.com/qgSEe2MapiDpdoBH6")
        await self.play(ctx, query="https://on.soundcloud.com/oCJu1EhocxQ43Fqz9")
        await self.shuffle(ctx)
        await self.skip(ctx)


async def setup(bot) -> None:
    await bot.add_cog(Music(bot))
