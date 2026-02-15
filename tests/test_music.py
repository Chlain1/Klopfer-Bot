import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import discord
from discord.ext import commands
from lavalink.server import LoadType

from cogs.music import LavalinkVoiceClient, Music
from tests.helpers import DummyChannel, DummyContext, DummyGuild, DummyMember, DummyRole, make_permissions


class FakeTrack:
    def __init__(self, title="t", uri="http://t", author="a"):
        self.title = title
        self.uri = uri
        self.author = author


class FakeResults:
    def __init__(self, load_type, tracks, playlist_name="pl"):
        self.load_type = load_type
        self.tracks = tracks
        self.playlist_info = SimpleNamespace(name=playlist_name)


class FakeNode:
    def __init__(self, results):
        self._results = results

    async def get_tracks(self, query):
        return self._results


class FakePlayer:
    def __init__(self):
        self.queue = []
        self.is_playing = False
        self.is_connected = True
        self.paused = False
        self.repeat = False
        self.repeat_queue = False
        self.channel_id = 1
        self._stored = {}
        self.node = FakeNode(FakeResults(LoadType.SEARCH, [FakeTrack()]))

    def store(self, key, value):
        self._stored[key] = value

    def fetch(self, key):
        return self._stored.get(key)

    def add(self, track, requester):
        self.queue.append(track)

    async def play(self):
        self.is_playing = True

    async def stop(self):
        self.is_playing = False

    async def skip(self):
        return None

    async def set_pause(self, paused):
        self.paused = paused

    async def set_filter(self, filter_obj):
        self.filter_obj = filter_obj

    async def remove_filter(self, name):
        self.filter_removed = name


class FakePlayerManager:
    def __init__(self, player):
        self._player = player
        self.create = MagicMock(return_value=player)
        self.get = MagicMock(return_value=player)
        self.destroy = AsyncMock()


class FakeLavalinkClient:
    def __init__(self, player):
        self.player_manager = FakePlayerManager(player)
        self._event_hooks = ["hook"]

    def add_node(self, **kwargs):
        self.add_node_kwargs = kwargs

    def add_event_hooks(self, cog):
        self._event_hooks.append(cog)

    async def voice_update_handler(self, data):
        self.last_voice_update = data


class DummyVoiceChannel:
    def __init__(self, guild, members=None, limit=0, connect=True, speak=True):
        self.guild = guild
        self.id = 1
        self.members = members or []
        self.user_limit = limit
        self._permissions = make_permissions(connect=connect, speak=speak)

    def permissions_for(self, me):
        return self._permissions

    async def connect(self, cls=None):
        return None


class DummyVoice:
    def __init__(self, channel):
        self.channel = channel


class DummyBot:
    def __init__(self, lavalink_client=None):
        self.user = SimpleNamespace(id=1)
        self.lavalink = lavalink_client


class DummyBotNoLavalink:
    def __init__(self):
        self.user = SimpleNamespace(id=1)


class DummyVoiceClient:
    def __init__(self, channel):
        self.channel = channel
        self.connect = AsyncMock()
        self.disconnect = AsyncMock()


class TestMusicCog(unittest.IsolatedAsyncioTestCase):
    async def test_lavalink_voice_client_init_creates(self):
        player = FakePlayer()
        client = DummyBotNoLavalink()
        channel = SimpleNamespace(guild=SimpleNamespace(id=1))
        with patch("cogs.music.lavalink.Client", return_value=FakeLavalinkClient(player)):
            vc = LavalinkVoiceClient(client, channel)
        self.assertTrue(hasattr(client, "lavalink"))
        self.assertIs(vc.channel, channel)

    async def test_lavalink_voice_client_init_reuse(self):
        player = FakePlayer()
        lavalink_client = FakeLavalinkClient(player)
        client = DummyBot(lavalink_client=lavalink_client)
        channel = SimpleNamespace(guild=SimpleNamespace(id=1))
        with patch("cogs.music.lavalink.Client", side_effect=AssertionError("should not create")):
            vc = LavalinkVoiceClient(client, channel)
        self.assertIs(vc.lavalink, lavalink_client)

    async def test_voice_update_server(self):
        player = FakePlayer()
        lavalink_client = FakeLavalinkClient(player)
        client = DummyBot(lavalink_client=lavalink_client)
        channel = SimpleNamespace(guild=SimpleNamespace(id=1))
        vc = LavalinkVoiceClient(client, channel)
        await vc.on_voice_server_update({"x": 1})
        self.assertEqual(lavalink_client.last_voice_update["t"], "VOICE_SERVER_UPDATE")

    async def test_voice_state_update_disconnect(self):
        player = FakePlayer()
        lavalink_client = FakeLavalinkClient(player)
        client = DummyBot(lavalink_client=lavalink_client)
        channel = SimpleNamespace(guild=SimpleNamespace(id=1))
        vc = LavalinkVoiceClient(client, channel)
        vc._destroy = AsyncMock()
        await vc.on_voice_state_update({"channel_id": None})
        vc._destroy.assert_awaited()

    async def test_voice_state_update_connected(self):
        player = FakePlayer()
        lavalink_client = FakeLavalinkClient(player)
        client = DummyBot(lavalink_client=lavalink_client)
        channel = SimpleNamespace(guild=SimpleNamespace(id=1))
        vc = LavalinkVoiceClient(client, channel)
        client.get_channel = MagicMock(return_value=SimpleNamespace(id=2))
        await vc.on_voice_state_update({"channel_id": "2"})
        self.assertEqual(lavalink_client.last_voice_update["t"], "VOICE_STATE_UPDATE")

    async def test_connect_disconnect_destroy(self):
        player = FakePlayer()
        lavalink_client = FakeLavalinkClient(player)
        client = DummyBot(lavalink_client=lavalink_client)
        guild = DummyGuild(guild_id=1)
        channel = SimpleNamespace(guild=guild)
        vc = LavalinkVoiceClient(client, channel)
        vc.cleanup = MagicMock()
        await vc.connect(timeout=1, reconnect=False)
        guild.change_voice_state.assert_awaited()

        player.is_connected = False
        await vc.disconnect(force=False)

        player.is_connected = True
        await vc.disconnect(force=True)
        guild.change_voice_state.assert_awaited()

    async def test_destroy_idempotent_and_error(self):
        player = FakePlayer()
        lavalink_client = FakeLavalinkClient(player)
        client = DummyBot(lavalink_client=lavalink_client)
        channel = SimpleNamespace(guild=SimpleNamespace(id=1))
        vc = LavalinkVoiceClient(client, channel)
        vc.cleanup = MagicMock()
        with patch("cogs.music.ClientError", Exception):
            lavalink_client.player_manager.destroy = AsyncMock(side_effect=Exception("x"))
            await vc._destroy()
        vc._destroyed = True
        await vc._destroy()

    async def test_music_init_without_lavalink(self):
        player = FakePlayer()
        with patch("cogs.music.lavalink.Client", return_value=FakeLavalinkClient(player)):
            bot = DummyBotNoLavalink()
            cog = Music(bot)
        self.assertIsNotNone(cog.lavalink)

    async def test_cog_unload(self):
        player = FakePlayer()
        bot = DummyBot(lavalink_client=FakeLavalinkClient(player))
        cog = Music(bot)
        cog.cog_unload()
        self.assertEqual(cog.lavalink._event_hooks, [])

    async def test_cog_command_error(self):
        player = FakePlayer()
        bot = DummyBot(lavalink_client=FakeLavalinkClient(player))
        cog = Music(bot)
        ctx = DummyContext()
        err = commands.CommandInvokeError(Exception("boom"))
        await cog.cog_command_error(ctx, err)
        ctx.send.assert_awaited()

        await cog.cog_command_error(ctx, Exception("other"))

    async def test_create_player_guild_none(self):
        player = FakePlayer()
        bot = DummyBot(lavalink_client=FakeLavalinkClient(player))
        ctx = DummyContext(bot=bot, guild=None, command_name="play")
        with self.assertRaises(commands.NoPrivateMessage):
            await Music.create_player(ctx)

    async def test_create_player_no_voice(self):
        player = FakePlayer()
        bot = DummyBot(lavalink_client=FakeLavalinkClient(player))
        ctx = DummyContext(bot=bot, guild=DummyGuild(), command_name="play")
        ctx.author.voice = None
        ctx.voice_client = None
        with self.assertRaises(commands.CommandInvokeError):
            await Music.create_player(ctx)

    async def test_create_player_no_voice_with_client(self):
        player = FakePlayer()
        bot = DummyBot(lavalink_client=FakeLavalinkClient(player))
        guild = DummyGuild()
        ctx = DummyContext(bot=bot, guild=guild, command_name="play")
        ctx.author.voice = None
        ctx.voice_client = DummyVoiceClient(SimpleNamespace(id=1))
        with self.assertRaises(commands.CommandInvokeError):
            await Music.create_player(ctx)

    async def test_create_player_not_playing(self):
        player = FakePlayer()
        bot = DummyBot(lavalink_client=FakeLavalinkClient(player))
        guild = DummyGuild()
        ctx = DummyContext(bot=bot, guild=guild, command_name="pause")
        ctx.author.voice = DummyVoice(DummyVoiceChannel(guild))
        ctx.voice_client = None
        with self.assertRaises(commands.CommandInvokeError):
            await Music.create_player(ctx)

    async def test_create_player_missing_permissions(self):
        player = FakePlayer()
        bot = DummyBot(lavalink_client=FakeLavalinkClient(player))
        guild = DummyGuild()
        voice_channel = DummyVoiceChannel(guild, connect=False, speak=False)
        ctx = DummyContext(bot=bot, guild=guild, command_name="play")
        ctx.author.voice = DummyVoice(voice_channel)
        ctx.voice_client = None
        with self.assertRaises(commands.CommandInvokeError):
            await Music.create_player(ctx)

    async def test_create_player_full_channel(self):
        player = FakePlayer()
        bot = DummyBot(lavalink_client=FakeLavalinkClient(player))
        guild = DummyGuild()
        members = [DummyMember(), DummyMember()]
        voice_channel = DummyVoiceChannel(guild, members=members, limit=1)
        ctx = DummyContext(bot=bot, guild=guild, command_name="play")
        ctx.author.voice = DummyVoice(voice_channel)
        ctx.voice_client = None
        with self.assertRaises(commands.CommandInvokeError):
            await Music.create_player(ctx)

    async def test_create_player_full_channel_with_move(self):
        player = FakePlayer()
        bot = DummyBot(lavalink_client=FakeLavalinkClient(player))
        guild = DummyGuild()
        members = [DummyMember(), DummyMember()]
        voice_channel = DummyVoiceChannel(guild, members=members, limit=1)
        ctx = DummyContext(bot=bot, guild=guild, command_name="play")
        ctx.author.voice = DummyVoice(voice_channel)
        ctx.voice_client = None
        ctx.me.guild_permissions.move_members = True
        await Music.create_player(ctx)

    async def test_create_player_success(self):
        player = FakePlayer()
        bot = DummyBot(lavalink_client=FakeLavalinkClient(player))
        guild = DummyGuild(guild_id=1)
        voice_channel = DummyVoiceChannel(guild)
        ctx = DummyContext(bot=bot, guild=guild, command_name="play")
        ctx.author.voice = DummyVoice(voice_channel)
        ctx.voice_client = None
        await Music.create_player(ctx)

        ctx.voice_client = DummyVoiceClient(voice_channel)
        await Music.create_player(ctx)

    async def test_create_player_wrong_channel(self):
        player = FakePlayer()
        bot = DummyBot(lavalink_client=FakeLavalinkClient(player))
        guild = DummyGuild()
        voice_channel = DummyVoiceChannel(guild)
        ctx = DummyContext(bot=bot, guild=guild, command_name="play")
        ctx.author.voice = DummyVoice(voice_channel)
        ctx.voice_client = DummyVoiceClient(SimpleNamespace(id=2))
        with self.assertRaises(commands.CommandInvokeError):
            await Music.create_player(ctx)

    async def test_play_empty(self):
        player = FakePlayer()
        player.node = FakeNode(FakeResults(LoadType.EMPTY, []))
        bot = DummyBot(lavalink_client=FakeLavalinkClient(player))
        cog = Music(bot)
        ctx = DummyContext(bot=bot, guild=DummyGuild())
        await cog.play.callback(cog, ctx, query="x")
        ctx.send.assert_awaited()

    async def test_play_playlist(self):
        player = FakePlayer()
        player.node = FakeNode(FakeResults(LoadType.PLAYLIST, [FakeTrack(), FakeTrack()], "pl"))
        bot = DummyBot(lavalink_client=FakeLavalinkClient(player))
        cog = Music(bot)
        ctx = DummyContext(bot=bot, guild=DummyGuild())
        await cog.play.callback(cog, ctx, query="x")
        ctx.send.assert_awaited()

    async def test_play_track(self):
        player = FakePlayer()
        player.node = FakeNode(FakeResults(LoadType.SEARCH, [FakeTrack()]))
        bot = DummyBot(lavalink_client=FakeLavalinkClient(player))
        cog = Music(bot)
        ctx = DummyContext(bot=bot, guild=DummyGuild())
        await cog.play.callback(cog, ctx, query="x")
        ctx.send.assert_awaited()

        player.is_playing = True
        await cog.play.callback(cog, ctx, query="x")

    async def test_play_url(self):
        player = FakePlayer()
        player.node = FakeNode(FakeResults(LoadType.SEARCH, [FakeTrack()]))
        bot = DummyBot(lavalink_client=FakeLavalinkClient(player))
        cog = Music(bot)
        ctx = DummyContext(bot=bot, guild=DummyGuild())
        await cog.play.callback(cog, ctx, query="https://example.com")
        ctx.send.assert_awaited()

    async def test_lowpass_disable(self):
        player = FakePlayer()
        bot = DummyBot(lavalink_client=FakeLavalinkClient(player))
        cog = Music(bot)
        ctx = DummyContext(bot=bot, guild=DummyGuild())
        await cog.lowpass.callback(cog, ctx, strength=-1)
        self.assertEqual(player.filter_removed, "lowpass")

    async def test_lowpass_enable_boundary(self):
        player = FakePlayer()
        bot = DummyBot(lavalink_client=FakeLavalinkClient(player))
        cog = Music(bot)
        ctx = DummyContext(bot=bot, guild=DummyGuild())
        await cog.lowpass.callback(cog, ctx, strength=1000)
        ctx.send.assert_awaited()

    async def test_disconnect_skip_pause_resume(self):
        player = FakePlayer()
        bot = DummyBot(lavalink_client=FakeLavalinkClient(player))
        cog = Music(bot)
        ctx = DummyContext(bot=bot, guild=DummyGuild())
        ctx.voice_client = DummyVoiceClient(SimpleNamespace(id=1))
        await cog.disconnect.callback(cog, ctx)
        await cog.skip.callback(cog, ctx)
        await cog.pause.callback(cog, ctx)
        player.is_playing = True
        player.paused = False
        await cog.pause.callback(cog, ctx)
        player.paused = True
        await cog.pause.callback(cog, ctx)
        player.paused = True
        await cog.resume.callback(cog, ctx)
        player.paused = False
        await cog.resume.callback(cog, ctx)
        player.is_playing = False
        await cog.resume.callback(cog, ctx)

    async def test_queue_clear_connect(self):
        player = FakePlayer()
        player.queue = [FakeTrack() for _ in range(6)]
        bot = DummyBot(lavalink_client=FakeLavalinkClient(player))
        cog = Music(bot)
        ctx = DummyContext(bot=bot, guild=DummyGuild())
        ctx.voice_client = DummyVoiceClient(SimpleNamespace(id=1))
        await cog.queue.callback(cog, ctx)
        await cog.clear.callback(cog, ctx)
        await cog.connect.callback(cog, ctx)

    async def test_queue_empty(self):
        player = FakePlayer()
        player.queue = []
        bot = DummyBot(lavalink_client=FakeLavalinkClient(player))
        cog = Music(bot)
        ctx = DummyContext(bot=bot, guild=DummyGuild())
        await cog.queue.callback(cog, ctx)

    async def test_loop_loopqueue_shuffle(self):
        player = FakePlayer()
        bot = DummyBot(lavalink_client=FakeLavalinkClient(player))
        cog = Music(bot)
        ctx = DummyContext(bot=bot, guild=DummyGuild())
        await cog.loop.callback(cog, ctx)
        player.is_playing = True
        await cog.loop.callback(cog, ctx)

        await cog.loopqueue.callback(cog, ctx)
        player.queue = [FakeTrack()]
        await cog.loopqueue.callback(cog, ctx)

        player.queue = []
        await cog.shuffle.callback(cog, ctx)
        player.queue = [FakeTrack(), FakeTrack()]
        await cog.shuffle.callback(cog, ctx)

    async def test_playlist_commands(self):
        player = FakePlayer()
        bot = DummyBot(lavalink_client=FakeLavalinkClient(player))
        cog = Music(bot)
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
        player = FakePlayer()
        player.queue = [FakeTrack()]
        bot = DummyBot(lavalink_client=FakeLavalinkClient(player))
        cog = Music(bot)
        ctx = DummyContext(bot=bot, guild=DummyGuild())
        ctx.author.voice = SimpleNamespace(channel=DummyVoiceChannel(ctx.guild))
        ctx.voice_client = DummyVoiceClient(ctx.author.voice.channel)
        with patch.object(cog, "play", new=AsyncMock()):
            with patch.object(cog, "shuffle", new=AsyncMock()):
                with patch.object(cog, "skip", new=AsyncMock()):
                    await cog.horror.callback(cog, ctx)
                    await cog.fight.callback(cog, ctx)
                    await cog.travel.callback(cog, ctx)
                    await cog.tavern.callback(cog, ctx)

    async def test_track_events(self):
        player = FakePlayer()
        bot = DummyBot(lavalink_client=FakeLavalinkClient(player))
        cog = Music(bot)
        channel = DummyChannel(channel_id=10)
        guild = DummyGuild(guild_id=1, channels=[channel])
        player.store("channel", channel.id)
        event = SimpleNamespace(player=SimpleNamespace(guild_id=guild.id, fetch=player.fetch), track=FakeTrack())
        bot.get_guild = MagicMock(return_value=guild)
        await cog.on_track_start(event)
        end_event = SimpleNamespace(player=SimpleNamespace(guild_id=guild.id))
        await cog.on_queue_end(end_event)

        guild_no_channel = DummyGuild(guild_id=1, channels=[])
        bot.get_guild = MagicMock(return_value=guild_no_channel)
        event = SimpleNamespace(player=SimpleNamespace(guild_id=guild_no_channel.id, fetch=lambda key: 999), track=FakeTrack())
        await cog.on_track_start(event)

    async def test_track_events_missing_guild(self):
        player = FakePlayer()
        lavalink_client = FakeLavalinkClient(player)
        lavalink_client.player_manager.destroy = AsyncMock()
        bot = DummyBot(lavalink_client=lavalink_client)
        cog = Music(bot)
        bot.get_guild = MagicMock(return_value=None)
        event = SimpleNamespace(player=SimpleNamespace(guild_id=999, fetch=lambda key: None), track=FakeTrack())
        await cog.on_track_start(event)
        end_event = SimpleNamespace(player=SimpleNamespace(guild_id=999))
        await cog.on_queue_end(end_event)

    async def test_setup(self):
        bot = DummyBot(lavalink_client=FakeLavalinkClient(FakePlayer()))
        bot.add_cog = AsyncMock()
        await __import__("cogs.music").music.setup(bot)
        bot.add_cog.assert_awaited()
