from fastapi import APIRouter, Request, HTTPException
from deps import db, get_current_user, has_permission, compute_member_permissions
from models import ChannelCreate, ChannelUpdate, MessageCreate, ReactionAdd, ThreadReply, MessageEdit, Permissions
from encryption import encrypt_text, decrypt_text
from websocket_manager import manager
from datetime import datetime, timezone
from typing import Optional
import uuid, os, httpx

router = APIRouter()

@router.post("/servers/{server_id}/channels")
async def create_channel(server_id: str, data: ChannelCreate, request: Request):
    user = await get_current_user(request)
    server = await db.servers.find_one({"id": server_id}, {"_id": 0})
    if not server:
        raise HTTPException(404, "Server not found")
    member = await db.server_members.find_one({"server_id": server_id, "user_id": user["id"]}, {"_id": 0})
    if not member:
        raise HTTPException(403, "Not a member")
    perms = compute_member_permissions(server, member)
    if not has_permission(perms, Permissions.MANAGE_CHANNELS):
        raise HTTPException(403, "No permission to manage channels")
    channel_id = str(uuid.uuid4())
    channel = {
        "id": channel_id, "server_id": server_id, "name": data.name,
        "channel_type": data.channel_type, "category": data.category or "General",
        "slowmode_seconds": data.slowmode_seconds, "topic": None,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.channels.insert_one(channel)
    channel.pop("_id", None)
    return channel

@router.put("/servers/{server_id}/channels/{channel_id}")
async def update_channel(server_id: str, channel_id: str, data: ChannelUpdate, request: Request):
    user = await get_current_user(request)
    server = await db.servers.find_one({"id": server_id}, {"_id": 0})
    member = await db.server_members.find_one({"server_id": server_id, "user_id": user["id"]}, {"_id": 0})
    if not member or not server:
        raise HTTPException(403, "Not a member")
    perms = compute_member_permissions(server, member)
    if not has_permission(perms, Permissions.MANAGE_CHANNELS):
        raise HTTPException(403, "No permission")
    updates = {k: v for k, v in data.dict(exclude_unset=True).items() if v is not None}
    if updates:
        await db.channels.update_one({"id": channel_id, "server_id": server_id}, {"$set": updates})
    return {"message": "Channel updated"}

@router.delete("/servers/{server_id}/channels/{channel_id}")
async def delete_channel(server_id: str, channel_id: str, request: Request):
    user = await get_current_user(request)
    server = await db.servers.find_one({"id": server_id}, {"_id": 0})
    member = await db.server_members.find_one({"server_id": server_id, "user_id": user["id"]}, {"_id": 0})
    if not member or not server:
        raise HTTPException(403, "Not a member")
    perms = compute_member_permissions(server, member)
    if not has_permission(perms, Permissions.MANAGE_CHANNELS):
        raise HTTPException(403, "No permission")
    await db.channels.delete_one({"id": channel_id, "server_id": server_id})
    await db.channel_messages.delete_many({"channel_id": channel_id})
    return {"message": "Channel deleted"}

# ─── CHANNEL MESSAGES ───
@router.post("/channels/{channel_id}/messages")
async def send_channel_message(channel_id: str, data: MessageCreate, request: Request):
    user = await get_current_user(request)
    channel = await db.channels.find_one({"id": channel_id}, {"_id": 0})
    if not channel:
        raise HTTPException(404, "Channel not found")
    member = await db.server_members.find_one({"server_id": channel["server_id"], "user_id": user["id"]}, {"_id": 0})
    if not member:
        raise HTTPException(403, "Not a member of this server")
    server = await db.servers.find_one({"id": channel["server_id"]}, {"_id": 0})
    member_perms = compute_member_permissions(server, member) if server else 0
    if not has_permission(member_perms, Permissions.SEND_MESSAGES):
        raise HTTPException(403, "No permission to send messages")
    if channel.get("slowmode_seconds", 0) > 0 and not has_permission(member_perms, Permissions.BYPASS_SLOWMODE):
        last_msg = await db.channel_messages.find_one({"channel_id": channel_id, "sender_id": user["id"]}, {"_id": 0}, sort=[("created_at", -1)])
        if last_msg:
            last_time = datetime.fromisoformat(last_msg["created_at"])
            diff = (datetime.now(timezone.utc) - last_time).total_seconds()
            if diff < channel["slowmode_seconds"]:
                raise HTTPException(429, f"Slowmode active. Wait {int(channel['slowmode_seconds'] - diff)}s")
    msg_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    if data.e2e and data.encrypted_content:
        msg = {"id": msg_id, "channel_id": channel_id, "server_id": channel["server_id"], "sender_id": user["id"], "sender_username": user["username"], "sender_avatar": user.get("avatar_url"), "e2e": True, "encrypted_content": data.encrypted_content, "iv": data.iv, "encrypted_keys": data.encrypted_keys or {}, "attachments": data.attachments or [], "edited": False, "created_at": now}
    else:
        encrypted_content = encrypt_text(data.content)
        msg = {"id": msg_id, "channel_id": channel_id, "server_id": channel["server_id"], "sender_id": user["id"], "sender_username": user["username"], "sender_avatar": user.get("avatar_url"), "content_encrypted": encrypted_content, "attachments": data.attachments or [], "edited": False, "created_at": now}
    await db.channel_messages.insert_one(msg)
    broadcast_msg = {"type": "channel_message", "message": {"id": msg_id, "channel_id": channel_id, "server_id": channel["server_id"], "sender_id": user["id"], "sender_username": user["username"], "sender_avatar": user.get("avatar_url"), "attachments": data.attachments or [], "edited": False, "created_at": now}}
    if data.e2e:
        broadcast_msg["message"].update({"e2e": True, "encrypted_content": data.encrypted_content, "iv": data.iv, "encrypted_keys": data.encrypted_keys or {}})
    else:
        broadcast_msg["message"]["content"] = data.content
    await manager.broadcast_channel(channel_id, broadcast_msg, exclude=user["id"])
    await db.stats.update_one({"key": "global"}, {"$inc": {"messages_sent": 1}}, upsert=True)
    return broadcast_msg["message"].copy()

@router.get("/channels/{channel_id}/messages")
async def get_channel_messages(channel_id: str, request: Request, before: Optional[str] = None, limit: int = 50):
    user = await get_current_user(request)
    channel = await db.channels.find_one({"id": channel_id}, {"_id": 0})
    if not channel:
        raise HTTPException(404, "Channel not found")
    member = await db.server_members.find_one({"server_id": channel["server_id"], "user_id": user["id"]})
    if not member:
        raise HTTPException(403, "Not a member")
    query = {"channel_id": channel_id}
    if before:
        query["created_at"] = {"$lt": before}
    messages = await db.channel_messages.find(query, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(limit)
    for msg in messages:
        if msg.get("e2e"):
            pass
        elif msg.get("content_encrypted"):
            msg["content"] = decrypt_text(msg["content_encrypted"])
        msg.pop("content_encrypted", None)
        msg["reactions"] = await db.reactions.find({"message_id": msg["id"]}, {"_id": 0}).to_list(50)
        msg["thread_count"] = msg.get("thread_count", 0)
    messages.reverse()
    return messages

# ─── READ RECEIPTS ───
@router.post("/channels/{channel_id}/read")
async def mark_channel_read(channel_id: str, request: Request):
    user = await get_current_user(request)
    body = await request.json()
    last_message_id = body.get("last_message_id")
    if not last_message_id:
        raise HTTPException(400, "last_message_id required")
    channel = await db.channels.find_one({"id": channel_id}, {"_id": 0})
    if not channel:
        raise HTTPException(404, "Channel not found")
    now = datetime.now(timezone.utc).isoformat()
    await db.read_receipts.update_one(
        {"channel_id": channel_id, "user_id": user["id"]},
        {"$set": {"last_message_id": last_message_id, "read_at": now, "user_id": user["id"], "username": user["username"], "channel_id": channel_id}},
        upsert=True
    )
    await manager.broadcast_channel(channel_id, {"type": "read_receipt", "channel_id": channel_id, "user_id": user["id"], "username": user["username"], "last_message_id": last_message_id, "read_at": now}, exclude=user["id"])
    return {"message": "Marked as read"}

@router.get("/channels/{channel_id}/read-receipts")
async def get_channel_read_receipts(channel_id: str, request: Request):
    await get_current_user(request)
    receipts = await db.read_receipts.find({"channel_id": channel_id}, {"_id": 0}).to_list(200)
    return receipts

# ─── CHANNEL REACTIONS ───
@router.post("/channel-messages/{message_id}/reactions")
async def add_channel_reaction(message_id: str, data: ReactionAdd, request: Request):
    user = await get_current_user(request)
    msg = await db.channel_messages.find_one({"id": message_id}, {"_id": 0})
    if not msg:
        raise HTTPException(404, "Message not found")
    member = await db.server_members.find_one({"server_id": msg["server_id"], "user_id": user["id"]})
    if not member:
        raise HTTPException(403, "Not a member")
    server = await db.servers.find_one({"id": msg["server_id"]}, {"_id": 0})
    member_perms = compute_member_permissions(server, member) if server else 0
    if not has_permission(member_perms, Permissions.ADD_REACTIONS):
        raise HTTPException(403, "No permission to add reactions")
    await db.reactions.update_one(
        {"message_id": message_id, "emoji": data.emoji, "user_id": user["id"]},
        {"$setOnInsert": {"id": str(uuid.uuid4()), "message_id": message_id, "emoji": data.emoji, "user_id": user["id"], "username": user["username"], "created_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True
    )
    reactions = await db.reactions.find({"message_id": message_id}, {"_id": 0}).to_list(100)
    await manager.broadcast_channel(msg["channel_id"], {"type": "reaction_update", "message_id": message_id, "reactions": reactions})
    return {"message": "Reaction added"}

@router.delete("/channel-messages/{message_id}/reactions/{emoji}")
async def remove_channel_reaction(message_id: str, emoji: str, request: Request):
    user = await get_current_user(request)
    await db.reactions.delete_one({"message_id": message_id, "emoji": emoji, "user_id": user["id"]})
    reactions = await db.reactions.find({"message_id": message_id}, {"_id": 0}).to_list(100)
    msg = await db.channel_messages.find_one({"id": message_id}, {"_id": 0})
    if msg:
        await manager.broadcast_channel(msg["channel_id"], {"type": "reaction_update", "message_id": message_id, "reactions": reactions})
    return {"message": "Reaction removed"}

# ─── CHANNEL THREADS ───
@router.post("/channel-messages/{message_id}/thread")
async def reply_channel_thread(message_id: str, data: ThreadReply, request: Request):
    user = await get_current_user(request)
    parent = await db.channel_messages.find_one({"id": message_id}, {"_id": 0})
    if not parent:
        raise HTTPException(404, "Message not found")
    member = await db.server_members.find_one({"server_id": parent["server_id"], "user_id": user["id"]})
    if not member:
        raise HTTPException(403, "Not a member")
    server = await db.servers.find_one({"id": parent["server_id"]}, {"_id": 0})
    member_perms = compute_member_permissions(server, member) if server else 0
    if not has_permission(member_perms, Permissions.SEND_MESSAGES_IN_THREADS):
        raise HTTPException(403, "No permission to send messages in threads")
    reply_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    if data.e2e and data.encrypted_content:
        reply = {"id": reply_id, "parent_message_id": message_id, "channel_id": parent["channel_id"], "server_id": parent["server_id"], "sender_id": user["id"], "sender_username": user["username"], "sender_avatar": user.get("avatar_url"), "e2e": True, "encrypted_content": data.encrypted_content, "iv": data.iv, "encrypted_keys": data.encrypted_keys or {}, "attachments": data.attachments or [], "created_at": now}
    else:
        reply = {"id": reply_id, "parent_message_id": message_id, "channel_id": parent["channel_id"], "server_id": parent["server_id"], "sender_id": user["id"], "sender_username": user["username"], "sender_avatar": user.get("avatar_url"), "content_encrypted": encrypt_text(data.content), "attachments": data.attachments or [], "created_at": now}
    await db.thread_replies.insert_one(reply)
    await db.channel_messages.update_one({"id": message_id}, {"$inc": {"thread_count": 1}})
    broadcast_reply = {"id": reply_id, "parent_message_id": message_id, "sender_id": user["id"], "sender_username": user["username"], "attachments": data.attachments or [], "created_at": now}
    if data.e2e:
        broadcast_reply.update({"e2e": True, "encrypted_content": data.encrypted_content, "iv": data.iv, "encrypted_keys": data.encrypted_keys or {}})
    else:
        broadcast_reply["content"] = data.content
    await manager.broadcast_channel(parent["channel_id"], {"type": "thread_reply", "parent_message_id": message_id, "reply": broadcast_reply})
    return broadcast_reply

@router.get("/channel-messages/{message_id}/thread")
async def get_channel_thread(message_id: str, request: Request):
    await get_current_user(request)
    replies = await db.thread_replies.find({"parent_message_id": message_id}, {"_id": 0}).sort("created_at", 1).to_list(200)
    for r in replies:
        if r.get("e2e"):
            pass
        elif r.get("content_encrypted"):
            r["content"] = decrypt_text(r["content_encrypted"])
        r.pop("content_encrypted", None)
    return replies

# ─── CHANNEL EDIT / DELETE ───
@router.put("/channel-messages/{message_id}")
async def edit_channel_message(message_id: str, data: MessageEdit, request: Request):
    user = await get_current_user(request)
    msg = await db.channel_messages.find_one({"id": message_id, "sender_id": user["id"]}, {"_id": 0})
    if not msg:
        raise HTTPException(404, "Message not found or not yours")
    if data.e2e and data.encrypted_content:
        await db.channel_messages.update_one({"id": message_id}, {"$set": {"e2e": True, "encrypted_content": data.encrypted_content, "iv": data.iv, "encrypted_keys": data.encrypted_keys or {}, "edited": True}, "$unset": {"content_encrypted": ""}})
        broadcast = {"type": "message_edited", "message_id": message_id, "edited": True, "e2e": True, "encrypted_content": data.encrypted_content, "iv": data.iv, "encrypted_keys": data.encrypted_keys or {}}
    else:
        encrypted = encrypt_text(data.content)
        await db.channel_messages.update_one({"id": message_id}, {"$set": {"content_encrypted": encrypted, "edited": True}})
        broadcast = {"type": "message_edited", "message_id": message_id, "content": data.content, "edited": True}
    await manager.broadcast_channel(msg["channel_id"], broadcast)
    return {"message": "Edited"}

@router.delete("/channel-messages/{message_id}")
async def delete_channel_message(message_id: str, request: Request):
    user = await get_current_user(request)
    msg = await db.channel_messages.find_one({"id": message_id, "sender_id": user["id"]}, {"_id": 0})
    if not msg:
        raise HTTPException(404, "Message not found or not yours")
    await db.channel_messages.delete_one({"id": message_id})
    await db.reactions.delete_many({"message_id": message_id})
    await db.thread_replies.delete_many({"parent_message_id": message_id})
    await manager.broadcast_channel(msg["channel_id"], {"type": "message_deleted", "message_id": message_id})
    return {"message": "Deleted"}

# ─── VOICE CHANNEL INFO ───
@router.get("/channels/{channel_id}/voice-participants")
async def get_voice_participants(channel_id: str, request: Request):
    await get_current_user(request)
    participants = list(manager.get_voice_participants(channel_id))
    users = []
    for uid in participants:
        u = await db.users.find_one({"id": uid}, {"_id": 0, "password_hash": 0, "totp_secret": 0})
        if u:
            users.append({"id": u["id"], "username": u["username"], "display_name": u.get("display_name"), "avatar_url": u.get("avatar_url")})
    return users

# ─── UPDATE CHECK ───
@router.get("/system/update-check")
async def system_update_check(request: Request):
    return {"current_version": "1.0.0", "latest_version": "1.0.0", "update_available": False, "release_url": "https://github.com/shield/shield/releases", "changelog": "Initial release with encrypted messaging, servers, channels, voice/video, and share drives."}

# ─── GIF SEARCH (GIPHY PROXY) ───
def _format_gif(g):
    images = g.get("images", {})
    return {
        "id": g.get("id"), "title": g.get("title", ""),
        "url": images.get("original", {}).get("url", ""),
        "preview": images.get("fixed_height_small", {}).get("url", "") or images.get("preview_gif", {}).get("url", ""),
        "width": images.get("fixed_height_small", {}).get("width", "200"),
        "height": images.get("fixed_height_small", {}).get("height", "150"),
        "original_width": images.get("original", {}).get("width", "480"),
        "original_height": images.get("original", {}).get("height", "360"),
    }

@router.get("/gifs/trending")
async def gif_trending(request: Request, limit: int = 20, offset: int = 0):
    await get_current_user(request)
    giphy_key = os.environ.get("GIPHY_API_KEY", "")
    if not giphy_key:
        raise HTTPException(503, "GIF service not configured")
    async with httpx.AsyncClient() as client:
        resp = await client.get("https://api.giphy.com/v1/gifs/trending", params={"api_key": giphy_key, "limit": min(limit, 50), "offset": offset, "rating": "pg-13"}, timeout=10)
        if resp.status_code != 200:
            raise HTTPException(502, "GIF service error")
        data = resp.json()
    return {"gifs": [_format_gif(g) for g in data.get("data", [])], "pagination": data.get("pagination", {})}

@router.get("/gifs/search")
async def gif_search(request: Request, q: str, limit: int = 20, offset: int = 0):
    await get_current_user(request)
    giphy_key = os.environ.get("GIPHY_API_KEY", "")
    if not giphy_key:
        raise HTTPException(503, "GIF service not configured")
    async with httpx.AsyncClient() as client:
        resp = await client.get("https://api.giphy.com/v1/gifs/search", params={"api_key": giphy_key, "q": q, "limit": min(limit, 50), "offset": offset, "rating": "pg-13"}, timeout=10)
        if resp.status_code != 200:
            raise HTTPException(502, "GIF service error")
        data = resp.json()
    return {"gifs": [_format_gif(g) for g in data.get("data", [])], "pagination": data.get("pagination", {})}
