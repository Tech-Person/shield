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

# Permission flags
class Permissions:
    ADMINISTRATOR = 1 << 0
    MANAGE_SERVER = 1 << 1
    MANAGE_CHANNELS = 1 << 2
    MANAGE_ROLES = 1 << 3
    MANAGE_MESSAGES = 1 << 4
    KICK_MEMBERS = 1 << 5
    BAN_MEMBERS = 1 << 6
    SEND_MESSAGES = 1 << 7
    READ_MESSAGES = 1 << 8
    ATTACH_FILES = 1 << 9
    CONNECT_VOICE = 1 << 10
    SPEAK = 1 << 11
    STREAM = 1 << 12
    MANAGE_DRIVE = 1 << 13

    ALL = (1 << 14) - 1
    DEFAULT = SEND_MESSAGES | READ_MESSAGES | ATTACH_FILES | CONNECT_VOICE | SPEAK
