import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock


class DummyAvatar:
    def __init__(self, url="http://example.com/avatar.png"):
        self.url = url


class DummyUser:
    def __init__(self, name="User", user_id=123, bot=False):
        self.name = name
        self.id = user_id
        self.bot = bot
        self.mention = f"<@{user_id}>"
        self.display_avatar = DummyAvatar()


class DummyRole:
    def __init__(self, role_id=1, name="role"):
        self.id = role_id
        self.name = name


class DummyMember:
    def __init__(self, name="Member", user_id=123, roles=None, guild=None):
        self.name = name
        self.id = user_id
        self.roles = roles or []
        self.guild = guild
        self.mention = f"<@{user_id}>"
        self.voice = None
        self.add_roles = AsyncMock()
        self.remove_roles = AsyncMock()


class DummyChannel:
    def __init__(self, channel_id=1, name="channel"):
        self.id = channel_id
        self.name = name
        self.send = AsyncMock()
        self.purge = AsyncMock()
        self._history_messages = []

    def set_history(self, messages):
        self._history_messages = messages

    async def history(self, limit=None, before=None):
        for message in self._history_messages[: limit or None]:
            yield message


class DummyMessage:
    def __init__(self, author, content="", attachments=None, channel=None, message_id=1):
        self.author = author
        self.content = content
        self.clean_content = content
        self.attachments = attachments or []
        self.channel = channel or DummyChannel()
        self.id = message_id
        self.created_at = SimpleNamespace(strftime=lambda fmt: "01.01.2024 00:00:00")


class DummyGuild:
    def __init__(
        self,
        guild_id=1,
        name="guild",
        roles=None,
        members=None,
        channels=None,
        system_channel=None,
        icon=None,
    ):
        self.id = guild_id
        self.name = name
        self.roles = roles or []
        self.members = members or []
        self.channels = channels or []
        self.system_channel = system_channel
        self.icon = icon
        self.member_count = len(self.members)
        self.created_at = "2024-01-01"
        self.voice_client = SimpleNamespace(disconnect=AsyncMock())
        self.change_voice_state = AsyncMock()

    def get_role(self, role_id):
        for role in self.roles:
            if role.id == role_id:
                return role
        return None

    def get_member(self, user_id):
        for member in self.members:
            if member.id == user_id:
                return member
        return None

    def get_channel(self, channel_id):
        for channel in self.channels:
            if channel.id == channel_id:
                return channel
        return None


class DummyInteraction:
    def __init__(self, user=None):
        self.user = user or DummyUser()
        self.response = SimpleNamespace(
            send_message=AsyncMock(),
            edit_message=AsyncMock(),
            send_modal=AsyncMock(),
        )


class DummyContext:
    def __init__(
        self,
        author=None,
        channel=None,
        guild=None,
        message=None,
        bot=None,
        command_name="",
    ):
        self.author = author or DummyMember()
        self.channel = channel or DummyChannel()
        self.guild = guild
        self.message = message or DummyMessage(self.author)
        self.bot = bot
        self.command = SimpleNamespace(qualified_name=command_name, name=command_name)
        self.me = SimpleNamespace(guild_permissions=SimpleNamespace(move_members=False))
        self.voice_client = None
        self.send = AsyncMock()
        self.invoke = AsyncMock()


def async_return(value=None):
    async def _runner(*args, **kwargs):
        return value

    return _runner


def make_permissions(connect=True, speak=True):
    return SimpleNamespace(connect=connect, speak=speak)
