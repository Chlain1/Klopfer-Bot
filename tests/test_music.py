import asyncio
import json
import os
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from discord.ext import commands

from cogs.music import (
    ExtractionError,
    GuildMusicState,
    Music,
    Track,
    _last_error_line,
    _run_ytdlp,
    _extract_stream,
    _track_from_entry,
    ensure_voice,
)
from tests.helpers import DummyContext, DummyGuild, DummyMember, make_permissions


class DummyVoiceChannel:
    def __init__(self, guild, members=None, limit=0, connect=True, speak=True):
        self.guild = guild
        self.id = 1
        self.members = members or []
        self.user_limit = limit
        self._permissions = make_permissions(connect=connect, speak=speak)
        self.connect = AsyncMock()

    def permissions_for(self, me):
        return self._permissions


class DummyVoice:
    def __init__(self, channel):
        self.channel = channel


class DummyVoiceClient:
    def __init__(self, channel):
        self.channel = channel
        self.connect = AsyncMock()
        self.disconnect = AsyncMock()
        self.play = MagicMock()
        self.stop = MagicMock()
        self.pause = MagicMock()
        self.resume = MagicMock()
        self._playing = False
        self._paused = False

    def is_playing(self):
        return self._playing

    def is_paused(self):
        return self._paused


class DummyBot:
    def __init__(self):
        self.user = SimpleNamespace(id=1)
        self.logger = MagicMock()
        self.loop = MagicMock()
        self.get_guild = MagicMock(return_value=None)


def make_process(returncode=0, stdout=b"", stderr=b""):
    process = SimpleNamespace()
    process.returncode = returncode
    process.communicate = AsyncMock(return_value=(stdout, stderr))
    process.kill = MagicMock()
    process.wait = AsyncMock()
    return process


class TestEnsureVoice(unittest.IsolatedAsyncioTestCase):
    async def test_guild_none(self):
        ctx = DummyContext(bot=DummyBot(), guild=None, command_name="play")
        with self.assertRaises(commands.NoPrivateMessage):
            await ensure_voice(ctx)

    async def test_no_voice_with_client(self):
        guild = DummyGuild()
        ctx = DummyContext(bot=DummyBot(), guild=guild, command_name="play")
        ctx.author.voice = None
        ctx.voice_client = DummyVoiceClient(SimpleNamespace(id=1))
        with self.assertRaises(commands.CommandInvokeError):
            await ensure_voice(ctx)

    async def test_no_voice_without_client(self):
        guild = DummyGuild()
        ctx = DummyContext(bot=DummyBot(), guild=guild, command_name="play")
        ctx.author.voice = None
        ctx.voice_client = None
        with self.assertRaises(commands.CommandInvokeError):
            await ensure_voice(ctx)

    async def test_not_playing_command_without_client(self):
        guild = DummyGuild()
        ctx = DummyContext(bot=DummyBot(), guild=guild, command_name="pause")
        ctx.author.voice = DummyVoice(DummyVoiceChannel(guild))
        ctx.voice_client = None
        with self.assertRaises(commands.CommandInvokeError):
            await ensure_voice(ctx)

    async def test_missing_permissions(self):
        guild = DummyGuild()
        voice_channel = DummyVoiceChannel(guild, connect=False, speak=False)
        ctx = DummyContext(bot=DummyBot(), guild=guild, command_name="play")
        ctx.author.voice = DummyVoice(voice_channel)
        ctx.voice_client = None
        with self.assertRaises(commands.CommandInvokeError):
            await ensure_voice(ctx)

    async def test_full_channel(self):
        guild = DummyGuild()
        members = [DummyMember(), DummyMember()]
        voice_channel = DummyVoiceChannel(guild, members=members, limit=1)
        ctx = DummyContext(bot=DummyBot(), guild=guild, command_name="play")
        ctx.author.voice = DummyVoice(voice_channel)
        ctx.voice_client = None
        with self.assertRaises(commands.CommandInvokeError):
            await ensure_voice(ctx)

    async def test_full_channel_with_move_permission(self):
        guild = DummyGuild()
        members = [DummyMember(), DummyMember()]
        voice_channel = DummyVoiceChannel(guild, members=members, limit=1)
        ctx = DummyContext(bot=DummyBot(), guild=guild, command_name="play")
        ctx.author.voice = DummyVoice(voice_channel)
        ctx.voice_client = None
        ctx.me.guild_permissions.move_members = True
        await ensure_voice(ctx)
        voice_channel.connect.assert_awaited()

    async def test_connects_successfully(self):
        guild = DummyGuild()
        voice_channel = DummyVoiceChannel(guild)
        ctx = DummyContext(bot=DummyBot(), guild=guild, command_name="play")
        ctx.author.voice = DummyVoice(voice_channel)
        ctx.voice_client = None
        await ensure_voice(ctx)
        voice_channel.connect.assert_awaited()

    async def test_wrong_channel(self):
        guild = DummyGuild()
        voice_channel = DummyVoiceChannel(guild)
        ctx = DummyContext(bot=DummyBot(), guild=guild, command_name="play")
        ctx.author.voice = DummyVoice(voice_channel)
        ctx.voice_client = DummyVoiceClient(SimpleNamespace(id=2))
        with self.assertRaises(commands.CommandInvokeError):
            await ensure_voice(ctx)

    async def test_same_channel_no_reconnect(self):
        guild = DummyGuild()
        voice_channel = DummyVoiceChannel(guild)
        ctx = DummyContext(bot=DummyBot(), guild=guild, command_name="skip")
        ctx.author.voice = DummyVoice(voice_channel)
        ctx.voice_client = DummyVoiceClient(voice_channel)
        result = await ensure_voice(ctx)
        self.assertTrue(result)
        voice_channel.connect.assert_not_awaited()


class TestLastErrorLine(unittest.TestCase):
    def test_prefers_error_line(self):
        stderr = b"WARNING: something\nERROR: Video unavailable\ntrailing noise"
        self.assertEqual(_last_error_line(stderr), "Video unavailable")

    def test_falls_back_to_last_line(self):
        stderr = b"some output\nlast line"
        self.assertEqual(_last_error_line(stderr), "last line")

    def test_empty_stderr(self):
        self.assertEqual(_last_error_line(b""), "unknown yt-dlp error")


class TestRunYtdlp(unittest.IsolatedAsyncioTestCase):
    async def test_returns_parsed_json(self):
        process = make_process(stdout=json.dumps({"title": "Song"}).encode())
        with patch("cogs.music.asyncio.create_subprocess_exec", AsyncMock(return_value=process)):
            info = await _run_ytdlp("-J", "query")
        self.assertEqual(info, {"title": "Song"})

    async def test_raises_on_nonzero_exit(self):
        process = make_process(returncode=1, stderr=b"ERROR: Sign in to confirm")
        with patch("cogs.music.asyncio.create_subprocess_exec", AsyncMock(return_value=process)):
            with self.assertRaises(ExtractionError) as caught:
                await _run_ytdlp("-J", "query")
        self.assertIn("Sign in to confirm", str(caught.exception))

    async def test_returns_none_on_empty_output(self):
        process = make_process(stdout=b"\n")
        with patch("cogs.music.asyncio.create_subprocess_exec", AsyncMock(return_value=process)):
            self.assertIsNone(await _run_ytdlp("-J", "query"))

    async def test_raises_on_invalid_json(self):
        process = make_process(stdout=b"not json")
        with patch("cogs.music.asyncio.create_subprocess_exec", AsyncMock(return_value=process)):
            with self.assertRaises(ExtractionError):
                await _run_ytdlp("-J", "query")

    async def test_includes_pot_provider_args_when_configured(self):
        process = make_process(stdout=b"{}")
        with patch.dict(os.environ, {"POT_PROVIDER_URL": "http://pot-provider:4416"}):
            with patch("cogs.music.asyncio.create_subprocess_exec", AsyncMock(return_value=process)) as exec_mock:
                await _run_ytdlp("-J", "query")
        args = exec_mock.call_args.args
        self.assertIn("--extractor-args", args)
        self.assertIn("youtubepot-bgutilhttp:base_url=http://pot-provider:4416", args)

    async def test_omits_pot_provider_args_by_default(self):
        process = make_process(stdout=b"{}")
        with patch.dict(os.environ):
            os.environ.pop("POT_PROVIDER_URL", None)
            with patch("cogs.music.asyncio.create_subprocess_exec", AsyncMock(return_value=process)) as exec_mock:
                await _run_ytdlp("-J", "query")
        self.assertNotIn("--extractor-args", exec_mock.call_args.args)

    async def test_kills_process_on_timeout(self):
        process = make_process()

        async def never_finish():
            await asyncio.sleep(3600)

        process.communicate = MagicMock(side_effect=never_finish)
        with patch("cogs.music.asyncio.create_subprocess_exec", AsyncMock(return_value=process)):
            with patch("cogs.music.EXTRACTION_TIMEOUT", 0.01):
                with self.assertRaises(ExtractionError):
                    await _run_ytdlp("-J", "query")
        process.kill.assert_called_once()


class TestExtractStream(unittest.IsolatedAsyncioTestCase):
    async def test_unwraps_search_playlist(self):
        wrapped = {"entries": [None, {"title": "Song", "url": "https://stream"}]}
        with patch("cogs.music._run_ytdlp", AsyncMock(return_value=wrapped)):
            info = await _extract_stream("ytsearch1:song")
        self.assertEqual(info["title"], "Song")

    async def test_empty_search_playlist(self):
        with patch("cogs.music._run_ytdlp", AsyncMock(return_value={"entries": []})):
            self.assertIsNone(await _extract_stream("ytsearch1:song"))

    async def test_passes_through_single_track(self):
        info = {"title": "Song", "url": "https://stream"}
        with patch("cogs.music._run_ytdlp", AsyncMock(return_value=info)):
            self.assertEqual(await _extract_stream("https://x"), info)


class TestTrackFromEntry(unittest.TestCase):
    def test_prefers_webpage_url(self):
        entry = {"webpage_url": "https://example.com/a", "title": "A", "duration": 10}
        track = _track_from_entry(entry, requester_id=5)
        self.assertEqual(track.query, "https://example.com/a")
        self.assertEqual(track.webpage_url, "https://example.com/a")
        self.assertEqual(track.requester, 5)

    def test_falls_back_to_raw_url(self):
        entry = {"url": "https://example.com/b", "title": "B"}
        track = _track_from_entry(entry, requester_id=5)
        self.assertEqual(track.query, "https://example.com/b")

    def test_builds_youtube_url_from_id(self):
        entry = {"id": "abc123", "title": "C", "ie_key": "Youtube"}
        track = _track_from_entry(entry, requester_id=5)
        self.assertEqual(track.query, "https://www.youtube.com/watch?v=abc123")

    def test_does_not_guess_youtube_url_for_other_extractors(self):
        entry = {"id": "12345", "title": "C", "ie_key": "Soundcloud"}
        track = _track_from_entry(entry, requester_id=5)
        self.assertIsNone(track.query)

    def test_missing_title_defaults(self):
        entry = {"url": "https://example.com/d"}
        track = _track_from_entry(entry, requester_id=5)
        self.assertEqual(track.title, "Unknown title")

    def test_keeps_search_query(self):
        entry = {"url": "https://example.com/e", "title": "E"}
        track = _track_from_entry(entry, requester_id=5, search_query="some song")
        self.assertEqual(track.search_query, "some song")


class TestMusicCog(unittest.IsolatedAsyncioTestCase):
    def make_cog(self):
        bot = DummyBot()
        cog = Music(bot)
        return bot, cog

    async def drain_prefetch(self, cog):
        # Prefetch tasks must finish inside the surrounding patch context, so they
        # never hit a real yt-dlp subprocess.
        if cog._prefetch_tasks:
            await asyncio.gather(*cog._prefetch_tasks, return_exceptions=True)

    async def test_cog_command_error(self):
        _, cog = self.make_cog()
        ctx = DummyContext()
        err = commands.CommandInvokeError(Exception("boom"))
        await cog.cog_command_error(ctx, err)
        ctx.send.assert_awaited()

        await cog.cog_command_error(ctx, Exception("other"))

    async def test_get_state_creates_and_reuses(self):
        _, cog = self.make_cog()
        state = cog.get_state(1)
        self.assertIsInstance(state, GuildMusicState)
        self.assertIs(cog.get_state(1), state)

    async def test_on_voice_state_update_cleans_up(self):
        _, cog = self.make_cog()
        state = cog.get_state(1)
        state.queue.append(Track(query="x", title="t", webpage_url="x", duration=1, requester=1))
        member = SimpleNamespace(id=1, guild=SimpleNamespace(id=1))
        await cog.on_voice_state_update(member, None, SimpleNamespace(channel=None))
        self.assertNotIn(1, cog.guild_states)

    async def test_on_voice_state_update_ignores_other_members(self):
        _, cog = self.make_cog()
        cog.get_state(1)
        member = SimpleNamespace(id=999, guild=SimpleNamespace(id=1))
        await cog.on_voice_state_update(member, None, SimpleNamespace(channel=None))
        self.assertIn(1, cog.guild_states)

    async def test_on_voice_state_update_ignores_join(self):
        _, cog = self.make_cog()
        cog.get_state(1)
        member = SimpleNamespace(id=1, guild=SimpleNamespace(id=1))
        await cog.on_voice_state_update(member, None, SimpleNamespace(channel=SimpleNamespace(id=2)))
        self.assertIn(1, cog.guild_states)

    async def test_resolve_tracks_search(self):
        _, cog = self.make_cog()
        info = {"title": "Song", "webpage_url": "https://youtu.be/1", "duration": 5}
        with patch("cogs.music._extract_flat", AsyncMock(return_value=info)) as extract:
            tracks, playlist_title = await cog.resolve_tracks("some song", requester_id=1)
        self.assertEqual(extract.call_args.args[0], "ytsearch1:some song")
        self.assertEqual(len(tracks), 1)
        self.assertEqual(tracks[0].search_query, "some song")
        self.assertIsNone(playlist_title)

    async def test_resolve_tracks_search_falls_back_to_next_provider(self):
        _, cog = self.make_cog()
        info = {"title": "Song", "webpage_url": "https://soundcloud.com/1", "duration": 5}

        async def extract(query):
            if query.startswith("ytsearch"):
                raise ExtractionError("Sign in to confirm you're not a bot")
            return info

        with patch("cogs.music._extract_flat", side_effect=extract) as mock:
            tracks, playlist_title = await cog.resolve_tracks("some song", requester_id=1)
        self.assertEqual(mock.call_count, 2)
        self.assertEqual(mock.call_args.args[0], "scsearch1:some song")
        self.assertEqual(len(tracks), 1)

    async def test_resolve_tracks_search_empty_result_tries_next_provider(self):
        _, cog = self.make_cog()
        results = iter([{"entries": []}, {"title": "Song", "url": "https://soundcloud.com/1"}])
        with patch("cogs.music._extract_flat", AsyncMock(side_effect=lambda q: next(results))):
            tracks, _ = await cog.resolve_tracks("some song", requester_id=1)
        self.assertEqual(len(tracks), 1)

    async def test_resolve_tracks_search_all_providers_fail(self):
        _, cog = self.make_cog()
        with patch("cogs.music._extract_flat", AsyncMock(side_effect=ExtractionError("down"))):
            with self.assertRaises(ExtractionError):
                await cog.resolve_tracks("some song", requester_id=1)

    async def test_resolve_tracks_search_no_results_anywhere(self):
        _, cog = self.make_cog()
        with patch("cogs.music._extract_flat", AsyncMock(return_value={"entries": []})):
            tracks, playlist_title = await cog.resolve_tracks("some song", requester_id=1)
        self.assertEqual(tracks, [])
        self.assertIsNone(playlist_title)

    async def test_resolve_tracks_playlist(self):
        _, cog = self.make_cog()
        info = {
            "title": "My Playlist",
            "entries": [
                {"title": "A", "url": "https://youtu.be/a"},
                None,
                {"title": "B", "url": "https://youtu.be/b"},
            ],
        }
        with patch("cogs.music._extract_flat", AsyncMock(return_value=info)):
            tracks, playlist_title = await cog.resolve_tracks("https://youtube.com/playlist?list=x", requester_id=1)
        self.assertEqual(len(tracks), 2)
        self.assertEqual(playlist_title, "My Playlist")
        self.assertIsNone(tracks[0].search_query)

    async def test_resolve_tracks_playlist_capped(self):
        _, cog = self.make_cog()
        info = {
            "title": "Huge Playlist",
            "entries": [{"title": str(i), "url": f"https://youtu.be/{i}"} for i in range(100)],
        }
        with patch("cogs.music._extract_flat", AsyncMock(return_value=info)):
            tracks, playlist_title = await cog.resolve_tracks("https://youtube.com/playlist?list=x", requester_id=1)
        from cogs.music import MAX_PLAYLIST_TRACKS
        self.assertEqual(len(tracks), MAX_PLAYLIST_TRACKS)

    async def test_resolve_tracks_empty(self):
        _, cog = self.make_cog()
        with patch("cogs.music._extract_flat", AsyncMock(return_value=None)):
            tracks, playlist_title = await cog.resolve_tracks("https://youtube.com/watch?v=x", requester_id=1)
        self.assertEqual(tracks, [])
        self.assertIsNone(playlist_title)

    async def test_resolve_stream_info_falls_back_to_search_providers(self):
        _, cog = self.make_cog()
        track = Track(
            query="https://youtube.com/watch?v=gone", title="Song", webpage_url="https://x",
            duration=1, requester=1, search_query="some song",
        )

        async def extract(query):
            if query == "scsearch1:some song":
                return {"url": "https://stream", "title": "Song"}
            raise ExtractionError("unavailable")

        with patch("cogs.music._extract_stream", side_effect=extract) as mock:
            info = await cog._resolve_stream_info(track)
        self.assertEqual(info["url"], "https://stream")
        self.assertEqual(mock.call_count, 3)  # original URL, ytsearch, scsearch

    async def test_resolve_stream_info_no_fallback_without_search_query(self):
        _, cog = self.make_cog()
        track = Track(query="https://x", title="Song", webpage_url="https://x", duration=1, requester=1)
        with patch("cogs.music._extract_stream", AsyncMock(side_effect=ExtractionError("gone"))) as mock:
            with self.assertRaises(ExtractionError):
                await cog._resolve_stream_info(track)
        self.assertEqual(mock.call_count, 1)

    async def test_play_no_tracks(self):
        bot, cog = self.make_cog()
        ctx = DummyContext(bot=bot, guild=DummyGuild())
        ctx.voice_client = DummyVoiceClient(SimpleNamespace(id=1))
        with patch.object(cog, "resolve_tracks", AsyncMock(return_value=([], None))):
            await cog.play.callback(cog, ctx, query="x")
        ctx.send.assert_awaited_with("I couldn't find any tracks for that query.")

    async def test_play_resolve_error(self):
        bot, cog = self.make_cog()
        ctx = DummyContext(bot=bot, guild=DummyGuild())
        ctx.voice_client = DummyVoiceClient(SimpleNamespace(id=1))
        with patch.object(cog, "resolve_tracks", AsyncMock(side_effect=RuntimeError("boom"))):
            await cog.play.callback(cog, ctx, query="x")
        ctx.send.assert_awaited()

    async def test_play_single_track_starts_playback(self):
        bot, cog = self.make_cog()
        ctx = DummyContext(bot=bot, guild=DummyGuild())
        ctx.voice_client = DummyVoiceClient(SimpleNamespace(id=1))
        track = Track(query="q", title="Song", webpage_url="https://x", duration=1, requester=1)
        with patch.object(cog, "resolve_tracks", AsyncMock(return_value=([track], None))):
            with patch.object(cog, "_play_next", AsyncMock()) as play_next:
                await cog.play.callback(cog, ctx, query="x")
        ctx.send.assert_awaited()
        play_next.assert_awaited_with(ctx.guild.id)
        self.assertEqual(cog.get_state(ctx.guild.id).queue, [track])

    async def test_play_playlist_enqueued_without_starting(self):
        bot, cog = self.make_cog()
        ctx = DummyContext(bot=bot, guild=DummyGuild())
        ctx.voice_client = DummyVoiceClient(SimpleNamespace(id=1))
        ctx.voice_client._playing = True
        tracks = [
            Track(query="a", title="A", webpage_url="https://a", duration=1, requester=1),
            Track(query="b", title="B", webpage_url="https://b", duration=1, requester=1),
        ]
        with patch.object(cog, "resolve_tracks", AsyncMock(return_value=(tracks, "My playlist"))):
            with patch.object(cog, "_play_next", AsyncMock()) as play_next:
                await cog.play.callback(cog, ctx, query="x")
        play_next.assert_not_awaited()
        ctx.send.assert_awaited()

    async def test_lowpass_disable_and_enable(self):
        bot, cog = self.make_cog()
        ctx = DummyContext(bot=bot, guild=DummyGuild())
        await cog.lowpass.callback(cog, ctx, strength=-1)
        self.assertEqual(cog.get_state(ctx.guild.id).lowpass_freq, 0.0)

        await cog.lowpass.callback(cog, ctx, strength=1000)
        self.assertEqual(cog.get_state(ctx.guild.id).lowpass_freq, 100)

    async def test_disconnect(self):
        bot, cog = self.make_cog()
        ctx = DummyContext(bot=bot, guild=DummyGuild())
        vc = DummyVoiceClient(SimpleNamespace(id=1))
        vc._playing = True
        ctx.voice_client = vc
        cog.get_state(ctx.guild.id).queue.append(
            Track(query="a", title="A", webpage_url="https://a", duration=1, requester=1)
        )
        await cog.disconnect.callback(cog, ctx)
        vc.stop.assert_called_once()
        vc.disconnect.assert_awaited()
        self.assertEqual(cog.get_state(ctx.guild.id).queue, [])
        ctx.send.assert_awaited()

    async def test_skip(self):
        bot, cog = self.make_cog()
        ctx = DummyContext(bot=bot, guild=DummyGuild())
        vc = DummyVoiceClient(SimpleNamespace(id=1))
        ctx.voice_client = vc
        await cog.skip.callback(cog, ctx)
        vc.stop.assert_called_once()
        ctx.send.assert_awaited()

    async def test_pause_resume(self):
        bot, cog = self.make_cog()
        ctx = DummyContext(bot=bot, guild=DummyGuild())
        vc = DummyVoiceClient(SimpleNamespace(id=1))
        ctx.voice_client = vc

        await cog.pause.callback(cog, ctx)  # not playing

        vc._playing = True
        await cog.pause.callback(cog, ctx)
        vc.pause.assert_called_once()

        vc._paused = True
        await cog.pause.callback(cog, ctx)  # already paused

        await cog.resume.callback(cog, ctx)
        vc.resume.assert_called_once()

        vc._paused = False
        await cog.resume.callback(cog, ctx)  # not paused

        vc._playing = False
        await cog.resume.callback(cog, ctx)  # not playing at all

    async def test_queue_display_and_clear(self):
        bot, cog = self.make_cog()
        ctx = DummyContext(bot=bot, guild=DummyGuild())
        ctx.voice_client = DummyVoiceClient(SimpleNamespace(id=1))

        await cog.queue.callback(cog, ctx)  # empty

        state = cog.get_state(ctx.guild.id)
        state.queue = [Track(query=str(i), title=str(i), webpage_url=str(i), duration=1, requester=1) for i in range(6)]
        await cog.queue.callback(cog, ctx)

        await cog.clear.callback(cog, ctx)
        self.assertEqual(state.queue, [])

    async def test_connect_command(self):
        bot, cog = self.make_cog()
        ctx = DummyContext(bot=bot, guild=DummyGuild())
        ctx.voice_client = DummyVoiceClient(SimpleNamespace(id=1))
        await cog.connect.callback(cog, ctx)
        ctx.send.assert_awaited_with('🔊 | Connected.')

    async def test_loop_loopqueue_shuffle(self):
        bot, cog = self.make_cog()
        ctx = DummyContext(bot=bot, guild=DummyGuild())
        vc = DummyVoiceClient(SimpleNamespace(id=1))
        ctx.voice_client = vc

        await cog.loop.callback(cog, ctx)  # not playing
        vc._playing = True
        await cog.loop.callback(cog, ctx)
        self.assertTrue(cog.get_state(ctx.guild.id).repeat)

        await cog.loopqueue.callback(cog, ctx)  # empty queue
        state = cog.get_state(ctx.guild.id)
        state.queue = [Track(query="a", title="a", webpage_url="a", duration=1, requester=1)]
        await cog.loopqueue.callback(cog, ctx)
        self.assertTrue(state.repeat_queue)

        state.queue = []
        await cog.shuffle.callback(cog, ctx)  # empty queue
        state.queue = [
            Track(query="a", title="a", webpage_url="a", duration=1, requester=1),
            Track(query="b", title="b", webpage_url="b", duration=1, requester=1),
        ]
        await cog.shuffle.callback(cog, ctx)

    async def test_playlist_commands(self):
        bot, cog = self.make_cog()
        ctx = DummyContext(bot=bot, guild=DummyGuild())
        ctx.author.voice = SimpleNamespace(channel=DummyVoiceChannel(ctx.guild))
        ctx.voice_client = None
        with patch.object(cog, "play", new=AsyncMock()) as play_mock:
            with patch.object(cog, "shuffle", new=AsyncMock()) as shuffle_mock:
                with patch.object(cog, "skip", new=AsyncMock()) as skip_mock:
                    await cog.horror.callback(cog, ctx)
                    await cog.fight.callback(cog, ctx)
                    await cog.travel.callback(cog, ctx)
                    await cog.tavern.callback(cog, ctx)
        self.assertTrue(play_mock.called)
        self.assertTrue(shuffle_mock.called)
        self.assertTrue(skip_mock.called)

    async def test_playlist_commands_with_queue(self):
        bot, cog = self.make_cog()
        ctx = DummyContext(bot=bot, guild=DummyGuild())
        cog.get_state(ctx.guild.id).queue.append(
            Track(query="a", title="A", webpage_url="a", duration=1, requester=1)
        )
        ctx.author.voice = SimpleNamespace(channel=DummyVoiceChannel(ctx.guild))
        ctx.voice_client = DummyVoiceClient(ctx.author.voice.channel)
        with patch.object(cog, "play", new=AsyncMock()):
            with patch.object(cog, "shuffle", new=AsyncMock()):
                with patch.object(cog, "skip", new=AsyncMock()):
                    await cog.horror.callback(cog, ctx)
                    await cog.fight.callback(cog, ctx)
                    await cog.travel.callback(cog, ctx)
                    await cog.tavern.callback(cog, ctx)

    async def test_play_next_no_state_or_guild(self):
        bot, cog = self.make_cog()
        bot.get_guild = MagicMock(return_value=None)
        await cog._play_next(1)  # no state, no guild: should just return

    async def test_play_next_disconnects_when_queue_empty(self):
        bot, cog = self.make_cog()
        guild = SimpleNamespace(voice_client=DummyVoiceClient(SimpleNamespace(id=1)))
        bot.get_guild = MagicMock(return_value=guild)
        cog.get_state(1)
        await cog._play_next(1)
        guild.voice_client.disconnect.assert_awaited()

    async def test_play_next_plays_track(self):
        bot, cog = self.make_cog()
        vc = DummyVoiceClient(SimpleNamespace(id=1))
        guild = SimpleNamespace(voice_client=vc, get_channel=MagicMock(return_value=None))
        bot.get_guild = MagicMock(return_value=guild)
        state = cog.get_state(1)
        track = Track(query="q", title="Song", webpage_url="https://x", duration=1, requester=1)
        state.queue.append(track)

        with patch("cogs.music._extract_stream", AsyncMock(return_value={"url": "https://stream"})):
            with patch("cogs.music.discord.FFmpegPCMAudio"):
                await cog._play_next(1)

        vc.play.assert_called_once()
        self.assertIs(state.current, track)

    async def test_play_next_uses_prefetched_info(self):
        bot, cog = self.make_cog()
        vc = DummyVoiceClient(SimpleNamespace(id=1))
        guild = SimpleNamespace(voice_client=vc, get_channel=MagicMock(return_value=None))
        bot.get_guild = MagicMock(return_value=guild)
        state = cog.get_state(1)
        track = Track(query="q", title="Song", webpage_url="https://x", duration=1, requester=1)
        track.prefetched = {"url": "https://stream"}
        state.queue.append(track)

        with patch("cogs.music._extract_stream", AsyncMock()) as extract:
            with patch("cogs.music.discord.FFmpegPCMAudio"):
                await cog._play_next(1)

        extract.assert_not_awaited()
        vc.play.assert_called_once()
        self.assertIsNone(track.prefetched)

    async def test_play_next_prefetches_next_track(self):
        bot, cog = self.make_cog()
        vc = DummyVoiceClient(SimpleNamespace(id=1))
        guild = SimpleNamespace(voice_client=vc, get_channel=MagicMock(return_value=None))
        bot.get_guild = MagicMock(return_value=guild)
        state = cog.get_state(1)
        first = Track(query="a", title="A", webpage_url="https://a", duration=1, requester=1)
        second = Track(query="b", title="B", webpage_url="https://b", duration=1, requester=1)
        state.queue.extend([first, second])

        with patch("cogs.music._extract_stream", AsyncMock(return_value={"url": "https://stream"})):
            with patch("cogs.music.discord.FFmpegPCMAudio"):
                await cog._play_next(1)
                await self.drain_prefetch(cog)

        self.assertIs(state.current, first)
        self.assertEqual(second.prefetched, {"url": "https://stream"})

    async def test_play_next_backfills_missing_title(self):
        bot, cog = self.make_cog()
        vc = DummyVoiceClient(SimpleNamespace(id=1))
        guild = SimpleNamespace(voice_client=vc, get_channel=MagicMock(return_value=None))
        bot.get_guild = MagicMock(return_value=guild)
        state = cog.get_state(1)
        track = Track(query="q", title="Unknown title", webpage_url="https://x", duration=1, requester=1)
        state.queue.append(track)

        with patch("cogs.music._extract_stream", AsyncMock(return_value={"url": "https://stream", "title": "Real Title"})):
            with patch("cogs.music.discord.FFmpegPCMAudio"):
                await cog._play_next(1)

        self.assertEqual(track.title, "Real Title")

    async def test_play_next_skips_track_on_missing_stream_url(self):
        bot, cog = self.make_cog()
        vc = DummyVoiceClient(SimpleNamespace(id=1))
        guild = SimpleNamespace(voice_client=vc, get_channel=MagicMock(return_value=None))
        bot.get_guild = MagicMock(return_value=guild)
        state = cog.get_state(1)
        bad_track = Track(query="bad", title="Bad", webpage_url="https://bad", duration=1, requester=1)
        good_track = Track(query="good", title="Good", webpage_url="https://good", duration=1, requester=1)
        state.queue.extend([bad_track, good_track])

        results = {"bad": {"url": None}, "good": {"url": "https://stream"}}
        with patch("cogs.music._extract_stream", AsyncMock(side_effect=lambda q: results[q])):
            with patch("cogs.music.discord.FFmpegPCMAudio"):
                await cog._play_next(1)

        vc.play.assert_called_once()
        self.assertIs(state.current, good_track)

    async def test_play_next_handles_extraction_error(self):
        bot, cog = self.make_cog()
        vc = DummyVoiceClient(SimpleNamespace(id=1))
        guild = SimpleNamespace(voice_client=vc, get_channel=MagicMock(return_value=None))
        bot.get_guild = MagicMock(return_value=guild)
        state = cog.get_state(1)
        bad_track = Track(query="bad", title="Bad", webpage_url="https://bad", duration=1, requester=1)
        good_track = Track(query="good", title="Good", webpage_url="https://good", duration=1, requester=1)
        state.queue.extend([bad_track, good_track])

        async def side_effect(query):
            if query == "bad":
                raise ExtractionError("network error")
            return {"url": "https://stream"}

        with patch("cogs.music._extract_stream", side_effect=side_effect):
            with patch("cogs.music.discord.FFmpegPCMAudio"):
                await cog._play_next(1)

        vc.play.assert_called_once()
        self.assertIs(state.current, good_track)

    async def test_play_next_repeat_replays_current(self):
        bot, cog = self.make_cog()
        vc = DummyVoiceClient(SimpleNamespace(id=1))
        guild = SimpleNamespace(voice_client=vc, get_channel=MagicMock(return_value=None))
        bot.get_guild = MagicMock(return_value=guild)
        state = cog.get_state(1)
        track = Track(query="q", title="Song", webpage_url="https://x", duration=1, requester=1)
        state.current = track
        state.repeat = True

        with patch("cogs.music._extract_stream", AsyncMock(return_value={"url": "https://stream"})):
            with patch("cogs.music.discord.FFmpegPCMAudio"):
                await cog._play_next(1)

        self.assertIs(state.current, track)
        self.assertEqual(state.queue, [])

    async def test_play_next_repeat_queue_requeues_current(self):
        bot, cog = self.make_cog()
        vc = DummyVoiceClient(SimpleNamespace(id=1))
        guild = SimpleNamespace(voice_client=vc, get_channel=MagicMock(return_value=None))
        bot.get_guild = MagicMock(return_value=guild)
        state = cog.get_state(1)
        current = Track(query="a", title="A", webpage_url="https://a", duration=1, requester=1)
        next_track = Track(query="b", title="B", webpage_url="https://b", duration=1, requester=1)
        state.current = current
        state.repeat_queue = True
        state.queue.append(next_track)

        with patch("cogs.music._extract_stream", AsyncMock(return_value={"url": "https://stream"})):
            with patch("cogs.music.discord.FFmpegPCMAudio"):
                await cog._play_next(1)
                await self.drain_prefetch(cog)

        self.assertIs(state.current, next_track)
        self.assertEqual(state.queue, [current])

    async def test_play_next_repeat_gives_up_after_repeated_failures(self):
        # A permanently broken track under `repeat` must not recurse forever: after
        # MAX_CONSECUTIVE_FAILURES failed resolutions in a row, repeat is disabled and
        # the guild disconnects instead of retrying the same track indefinitely.
        bot, cog = self.make_cog()
        vc = DummyVoiceClient(SimpleNamespace(id=1))
        guild = SimpleNamespace(voice_client=vc, get_channel=MagicMock(return_value=None))
        bot.get_guild = MagicMock(return_value=guild)
        state = cog.get_state(1)
        track = Track(query="broken", title="Broken", webpage_url="https://broken", duration=1, requester=1)
        state.current = track
        state.repeat = True

        with patch("cogs.music._extract_stream", AsyncMock(side_effect=ExtractionError("always fails"))):
            await cog._play_next(1)

        self.assertFalse(state.repeat)
        self.assertEqual(state.consecutive_failures, 0)
        vc.play.assert_not_called()
        vc.disconnect.assert_awaited()

    async def test_play_next_repeat_queue_drops_broken_track_after_failures(self):
        bot, cog = self.make_cog()
        vc = DummyVoiceClient(SimpleNamespace(id=1))
        guild = SimpleNamespace(voice_client=vc, get_channel=MagicMock(return_value=None))
        bot.get_guild = MagicMock(return_value=guild)
        state = cog.get_state(1)
        broken = Track(query="broken", title="Broken", webpage_url="https://broken", duration=1, requester=1)
        state.current = None
        state.repeat_queue = True
        state.queue.append(broken)

        with patch("cogs.music._extract_stream", AsyncMock(side_effect=ExtractionError("always fails"))):
            await cog._play_next(1)

        self.assertFalse(state.repeat_queue)
        self.assertEqual(state.queue, [])
        vc.play.assert_not_called()
        vc.disconnect.assert_awaited()

    async def test_play_next_applies_lowpass_filter(self):
        bot, cog = self.make_cog()
        vc = DummyVoiceClient(SimpleNamespace(id=1))
        guild = SimpleNamespace(voice_client=vc, get_channel=MagicMock(return_value=None))
        bot.get_guild = MagicMock(return_value=guild)
        state = cog.get_state(1)
        state.lowpass_freq = 50
        state.queue.append(Track(query="q", title="Song", webpage_url="https://x", duration=1, requester=1))

        with patch("cogs.music._extract_stream", AsyncMock(return_value={"url": "https://stream"})):
            with patch("cogs.music.discord.FFmpegPCMAudio") as ffmpeg:
                await cog._play_next(1)

        self.assertIn("lowpass=f=50", ffmpeg.call_args.kwargs["options"])

    async def test_update_ytdlp_logs_version_change(self):
        bot, cog = self.make_cog()
        process = make_process(returncode=0)
        versions = iter(["2026.01.01", "2026.07.01"])
        with patch("cogs.music.asyncio.create_subprocess_exec", AsyncMock(return_value=process)):
            with patch.object(cog, "_ytdlp_version", AsyncMock(side_effect=lambda: next(versions))):
                await cog.update_ytdlp.coro(cog)
        bot.logger.info.assert_called_once()
        self.assertIn("2026.07.01", bot.logger.info.call_args.args[0])

    async def test_update_ytdlp_logs_failure(self):
        bot, cog = self.make_cog()
        process = make_process(returncode=1, stderr=b"ERROR: no network")
        with patch("cogs.music.asyncio.create_subprocess_exec", AsyncMock(return_value=process)):
            with patch.object(cog, "_ytdlp_version", AsyncMock(return_value="2026.01.01")):
                await cog.update_ytdlp.coro(cog)
        bot.logger.warning.assert_called_once()

    async def test_cog_load_and_unload_manage_update_task(self):
        _, cog = self.make_cog()
        with patch.object(cog, "update_ytdlp") as loop_mock:
            await cog.cog_load()
            loop_mock.start.assert_called_once()
            await cog.cog_unload()
            loop_mock.cancel.assert_called_once()

    async def test_setup(self):
        bot = DummyBot()
        bot.add_cog = AsyncMock()
        await __import__("cogs.music").music.setup(bot)
        bot.add_cog.assert_awaited()
