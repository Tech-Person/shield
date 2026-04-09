from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime, timezone
import uuid


class UserCreate(BaseModel):
    username: str
    email: str
    password: str

class UserLogin(BaseModel):
    email: str
    password: str

class TwoFactorSetup(BaseModel):
    pass

class TwoFactorVerify(BaseModel):
    code: str

class UserUpdate(BaseModel):
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    about: Optional[str] = None

class StatusUpdate(BaseModel):
    status: str  # online, away, busy, invisible
    status_message: Optional[str] = None
    status_expires_minutes: Optional[int] = None

class FriendRequest(BaseModel):
    username: str

class ServerCreate(BaseModel):
    name: str
    description: Optional[str] = ""
    icon_url: Optional[str] = None

class ServerUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    icon_url: Optional[str] = None
    storage_limit_gb: Optional[float] = None

class ChannelCreate(BaseModel):
    name: str
    channel_type: str = "text"  # text, voice
    category: Optional[str] = "General"
    slowmode_seconds: int = 0

class ChannelUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    slowmode_seconds: Optional[int] = None
    topic: Optional[str] = None

class RoleCreate(BaseModel):
    name: str
    color: Optional[str] = "#99AAB5"
    permissions: int = 0

class RoleUpdate(BaseModel):
    name: Optional[str] = None
    color: Optional[str] = None
    permissions: Optional[int] = None

class MessageCreate(BaseModel):
    content: str
    attachments: Optional[List[str]] = []

class DMCreate(BaseModel):
    recipient_id: str
    content: str

class GroupDMCreate(BaseModel):
    name: Optional[str] = None
    member_ids: List[str]

class SearchQuery(BaseModel):
    query: str
    conversation_id: Optional[str] = None
    limit: int = 50

class InviteCreate(BaseModel):
    max_uses: Optional[int] = None
    expires_hours: Optional[int] = 24

class ReactionAdd(BaseModel):
    emoji: str

class ThreadReply(BaseModel):
    content: str
    attachments: Optional[List[str]] = []

class MessageEdit(BaseModel):
    content: str

# Permission flags (bitmask)
class Permissions:
    # Advanced
    ADMINISTRATOR       = 1 << 0

    # General Server
    VIEW_CHANNELS       = 1 << 1
    MANAGE_CHANNELS     = 1 << 2
    MANAGE_ROLES        = 1 << 3
    MANAGE_SERVER       = 1 << 4
    CREATE_EXPRESSIONS  = 1 << 5
    MANAGE_EXPRESSIONS  = 1 << 6
    VIEW_AUDIT_LOG      = 1 << 7
    VIEW_SERVER_INSIGHTS = 1 << 8
    MANAGE_WEBHOOKS     = 1 << 9

    # Membership
    CREATE_INVITE       = 1 << 10
    CHANGE_NICKNAME     = 1 << 11
    MANAGE_NICKNAMES    = 1 << 12
    KICK_MEMBERS        = 1 << 13
    BAN_MEMBERS         = 1 << 14
    TIMEOUT_MEMBERS     = 1 << 15

    # Text Channel
    SEND_MESSAGES       = 1 << 16
    SEND_MESSAGES_IN_THREADS = 1 << 17
    CREATE_PUBLIC_THREADS = 1 << 18
    EMBED_LINKS         = 1 << 19
    ATTACH_FILES        = 1 << 20
    ADD_REACTIONS       = 1 << 21
    USE_EXTERNAL_EMOJI  = 1 << 22
    MENTION_EVERYONE    = 1 << 23
    MANAGE_MESSAGES     = 1 << 24
    PIN_MESSAGES        = 1 << 25
    BYPASS_SLOWMODE     = 1 << 26
    MANAGE_THREADS      = 1 << 27
    READ_MESSAGE_HISTORY = 1 << 28
    SEND_TTS_MESSAGES   = 1 << 29
    SEND_VOICE_MESSAGES = 1 << 30
    CREATE_POLLS        = 1 << 31

    # Voice Channel
    CONNECT             = 1 << 32
    SPEAK               = 1 << 33
    VIDEO               = 1 << 34
    USE_VOICE_ACTIVITY  = 1 << 35
    PRIORITY_SPEAKER    = 1 << 36
    MUTE_MEMBERS        = 1 << 37
    DEAFEN_MEMBERS      = 1 << 38
    MOVE_MEMBERS        = 1 << 39
    SET_VOICE_CHANNEL_STATUS = 1 << 40

    # Apps
    USE_APPLICATION_COMMANDS = 1 << 41
    USE_ACTIVITIES      = 1 << 42
    USE_EXTERNAL_APPS   = 1 << 43

    # Stage
    REQUEST_TO_SPEAK    = 1 << 44

    # Events
    CREATE_EVENTS       = 1 << 45
    MANAGE_EVENTS       = 1 << 46

    ALL = (1 << 47) - 1

    # Default @everyone permissions
    DEFAULT = (
        VIEW_CHANNELS | CREATE_INVITE | CHANGE_NICKNAME |
        SEND_MESSAGES | SEND_MESSAGES_IN_THREADS | CREATE_PUBLIC_THREADS |
        EMBED_LINKS | ATTACH_FILES | ADD_REACTIONS | USE_EXTERNAL_EMOJI |
        MENTION_EVERYONE | READ_MESSAGE_HISTORY | SEND_TTS_MESSAGES |
        CONNECT | SPEAK | VIDEO | USE_VOICE_ACTIVITY |
        USE_APPLICATION_COMMANDS | REQUEST_TO_SPEAK
    )

    # Map of all permissions for the frontend
    PERMISSION_MAP = {
        "general_server": [
            {"key": "VIEW_CHANNELS", "bit": 1 << 1, "name": "View Channels", "description": "Allows members to view channels by default (excluding private channels)."},
            {"key": "MANAGE_CHANNELS", "bit": 1 << 2, "name": "Manage Channels", "description": "Allows members to create, edit, or delete channels."},
            {"key": "MANAGE_ROLES", "bit": 1 << 3, "name": "Manage Roles", "description": "Allows members to create new roles and edit or delete roles lower than their highest role."},
            {"key": "CREATE_EXPRESSIONS", "bit": 1 << 5, "name": "Create Expressions", "description": "Allows members to add custom emoji and stickers in this server."},
            {"key": "MANAGE_EXPRESSIONS", "bit": 1 << 6, "name": "Manage Expressions", "description": "Allows members to edit or remove custom emoji and stickers in this server."},
            {"key": "VIEW_AUDIT_LOG", "bit": 1 << 7, "name": "View Audit Log", "description": "Allows members to view a record of who made which changes in this server."},
            {"key": "VIEW_SERVER_INSIGHTS", "bit": 1 << 8, "name": "View Server Insights", "description": "Allows members to view Server Insights, showing data on community growth and engagement."},
            {"key": "MANAGE_WEBHOOKS", "bit": 1 << 9, "name": "Manage Webhooks", "description": "Allows members to create, edit, or delete webhooks."},
            {"key": "MANAGE_SERVER", "bit": 1 << 4, "name": "Manage Server", "description": "Allows members to change this server's name, view all invites, and manage settings."},
        ],
        "membership": [
            {"key": "CREATE_INVITE", "bit": 1 << 10, "name": "Create Invite", "description": "Allows members to invite new people to this server."},
            {"key": "CHANGE_NICKNAME", "bit": 1 << 11, "name": "Change Nickname", "description": "Allows members to change their own nickname for this server."},
            {"key": "MANAGE_NICKNAMES", "bit": 1 << 12, "name": "Manage Nicknames", "description": "Allows members to change the nicknames of other members."},
            {"key": "KICK_MEMBERS", "bit": 1 << 13, "name": "Kick Members", "description": "Kick will remove members from this server. They can rejoin with an invite."},
            {"key": "BAN_MEMBERS", "bit": 1 << 14, "name": "Ban Members", "description": "Allows members to permanently ban other members from this server."},
            {"key": "TIMEOUT_MEMBERS", "bit": 1 << 15, "name": "Timeout Members", "description": "Prevents members from sending messages, reacting, or joining voice when timed out."},
        ],
        "text_channel": [
            {"key": "SEND_MESSAGES", "bit": 1 << 16, "name": "Send Messages", "description": "Allows members to send messages in text channels."},
            {"key": "SEND_MESSAGES_IN_THREADS", "bit": 1 << 17, "name": "Send Messages in Threads", "description": "Allows members to send messages in threads."},
            {"key": "CREATE_PUBLIC_THREADS", "bit": 1 << 18, "name": "Create Public Threads", "description": "Allows members to create threads that everyone in a channel can view."},
            {"key": "EMBED_LINKS", "bit": 1 << 19, "name": "Embed Links", "description": "Allows links that members share to show embedded content in text channels."},
            {"key": "ATTACH_FILES", "bit": 1 << 20, "name": "Attach Files", "description": "Allows members to upload files or media in text channels."},
            {"key": "ADD_REACTIONS", "bit": 1 << 21, "name": "Add Reactions", "description": "Allows members to add emoji reactions to messages."},
            {"key": "USE_EXTERNAL_EMOJI", "bit": 1 << 22, "name": "Use External Emoji", "description": "Allows members to use emoji from other servers."},
            {"key": "MENTION_EVERYONE", "bit": 1 << 23, "name": "Mention @everyone and All Roles", "description": "Allows members to use @everyone, @here, and mention all roles."},
            {"key": "MANAGE_MESSAGES", "bit": 1 << 24, "name": "Manage Messages", "description": "Allows members to delete or remove embeds from messages by other members."},
            {"key": "PIN_MESSAGES", "bit": 1 << 25, "name": "Pin Messages", "description": "Allows members to pin or unpin any message."},
            {"key": "BYPASS_SLOWMODE", "bit": 1 << 26, "name": "Bypass Slowmode", "description": "Allows members to send messages without being affected by slowmode."},
            {"key": "MANAGE_THREADS", "bit": 1 << 27, "name": "Manage Threads", "description": "Allows members to rename, delete, close, and manage threads."},
            {"key": "READ_MESSAGE_HISTORY", "bit": 1 << 28, "name": "Read Message History", "description": "Allows members to read previous messages sent in channels."},
            {"key": "SEND_TTS_MESSAGES", "bit": 1 << 29, "name": "Send Text-to-Speech Messages", "description": "Allows members to send text-to-speech messages."},
            {"key": "SEND_VOICE_MESSAGES", "bit": 1 << 30, "name": "Send Voice Messages", "description": "Allows members to send voice messages."},
            {"key": "CREATE_POLLS", "bit": 1 << 31, "name": "Create Polls", "description": "Allows members to create polls."},
        ],
        "voice_channel": [
            {"key": "CONNECT", "bit": 1 << 32, "name": "Connect", "description": "Allows members to join voice channels and hear others."},
            {"key": "SPEAK", "bit": 1 << 33, "name": "Speak", "description": "Allows members to talk in voice channels."},
            {"key": "VIDEO", "bit": 1 << 34, "name": "Video", "description": "Allows members to share their video or screen in this server."},
            {"key": "USE_VOICE_ACTIVITY", "bit": 1 << 35, "name": "Use Voice Activity", "description": "Allows members to speak by simply talking. If disabled, push-to-talk is required."},
            {"key": "PRIORITY_SPEAKER", "bit": 1 << 36, "name": "Priority Speaker", "description": "Allows members to be more easily heard in voice channels."},
            {"key": "MUTE_MEMBERS", "bit": 1 << 37, "name": "Mute Members", "description": "Allows members to mute other members in voice channels."},
            {"key": "DEAFEN_MEMBERS", "bit": 1 << 38, "name": "Deafen Members", "description": "Allows members to deafen other members in voice channels."},
            {"key": "MOVE_MEMBERS", "bit": 1 << 39, "name": "Move Members", "description": "Allows members to disconnect or move other members between voice channels."},
            {"key": "SET_VOICE_CHANNEL_STATUS", "bit": 1 << 40, "name": "Set Voice Channel Status", "description": "Allows members to create and edit voice channel status."},
        ],
        "apps": [
            {"key": "USE_APPLICATION_COMMANDS", "bit": 1 << 41, "name": "Use Application Commands", "description": "Allows members to use commands from applications."},
            {"key": "USE_ACTIVITIES", "bit": 1 << 42, "name": "Use Activities", "description": "Allows members to use Activities."},
            {"key": "USE_EXTERNAL_APPS", "bit": 1 << 43, "name": "Use External Apps", "description": "Allows apps that members have added to post messages."},
        ],
        "stage": [
            {"key": "REQUEST_TO_SPEAK", "bit": 1 << 44, "name": "Request to Speak", "description": "Allow requests to speak in Stage channels."},
        ],
        "events": [
            {"key": "CREATE_EVENTS", "bit": 1 << 45, "name": "Create Events", "description": "Allows members to create events."},
            {"key": "MANAGE_EVENTS", "bit": 1 << 46, "name": "Manage Events", "description": "Allows members to edit and cancel events."},
        ],
        "advanced": [
            {"key": "ADMINISTRATOR", "bit": 1 << 0, "name": "Administrator", "description": "Members with this permission have every permission and bypass all channel restrictions. This is a dangerous permission to grant."},
        ],
    }
