from fastapi import APIRouter, Request, HTTPException
from deps import db, get_current_user, has_permission, compute_member_permissions
from models import ServerCreate, ServerUpdate, InviteCreate, Permissions
from websocket_manager import manager
from datetime import datetime, timezone, timedelta
import uuid

router = APIRouter()

@router.post("/servers")
async def create_server(data: ServerCreate, request: Request):
    user = await get_current_user(request)
    server_id = str(uuid.uuid4())
    everyone_role_id = str(uuid.uuid4())
    general_channel_id = str(uuid.uuid4())
    voice_channel_id = str(uuid.uuid4())
    server = {
        "id": server_id, "name": data.name, "description": data.description or "",
        "icon_url": data.icon_url, "owner_id": user["id"],
        "roles": [{"id": everyone_role_id, "name": "@everyone", "color": "#99AAB5", "permissions": Permissions.DEFAULT, "position": 0}],
        "categories": ["Text Channels", "Voice Channels"],
        "storage_used_bytes": 0, "storage_limit_bytes": 5 * 1024 * 1024 * 1024,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.servers.insert_one(server)
    await db.channels.insert_one({"id": general_channel_id, "server_id": server_id, "name": "general", "channel_type": "text", "category": "Text Channels", "slowmode_seconds": 0, "topic": None, "created_at": datetime.now(timezone.utc).isoformat()})
    await db.channels.insert_one({"id": voice_channel_id, "server_id": server_id, "name": "General Voice", "channel_type": "voice", "category": "Voice Channels", "created_at": datetime.now(timezone.utc).isoformat()})
    await db.server_members.insert_one({"server_id": server_id, "user_id": user["id"], "roles": [everyone_role_id], "joined_at": datetime.now(timezone.utc).isoformat()})
    server.pop("_id", None)
    server["channels"] = [
        {"id": general_channel_id, "name": "general", "channel_type": "text", "category": "Text Channels"},
        {"id": voice_channel_id, "name": "General Voice", "channel_type": "voice", "category": "Voice Channels"}
    ]
    server["members"] = [{"user_id": user["id"], "username": user["username"], "display_name": user.get("display_name"), "avatar_url": user.get("avatar_url"), "status": user.get("status", "online"), "roles": [everyone_role_id]}]
    return server

@router.get("/servers")
async def get_user_servers(request: Request):
    user = await get_current_user(request)
    memberships = await db.server_members.find({"user_id": user["id"]}, {"_id": 0}).to_list(100)
    server_ids = [m["server_id"] for m in memberships]
    servers = await db.servers.find({"id": {"$in": server_ids}}, {"_id": 0}).to_list(100)
    return servers

@router.get("/servers/{server_id}")
async def get_server(server_id: str, request: Request):
    user = await get_current_user(request)
    server = await db.servers.find_one({"id": server_id}, {"_id": 0})
    if not server:
        raise HTTPException(404, "Server not found")
    member = await db.server_members.find_one({"server_id": server_id, "user_id": user["id"]}, {"_id": 0})
    if not member:
        raise HTTPException(403, "Not a member")
    channels = await db.channels.find({"server_id": server_id}, {"_id": 0}).to_list(100)
    members = await db.server_members.find({"server_id": server_id}, {"_id": 0}).to_list(500)
    member_data = []
    for m in members:
        u = await db.users.find_one({"id": m["user_id"]}, {"_id": 0, "password_hash": 0, "totp_secret": 0})
        if u:
            member_data.append({"user_id": u["id"], "username": u["username"], "display_name": u.get("display_name"), "avatar_url": u.get("avatar_url"), "status": u.get("status", "offline"), "roles": m.get("roles", [])})
    server["channels"] = channels
    server["members"] = member_data
    server["my_permissions"] = compute_member_permissions(server, member)
    return server

@router.put("/servers/{server_id}")
async def update_server(server_id: str, data: ServerUpdate, request: Request):
    user = await get_current_user(request)
    server = await db.servers.find_one({"id": server_id}, {"_id": 0})
    if not server:
        raise HTTPException(404, "Server not found")
    member = await db.server_members.find_one({"server_id": server_id, "user_id": user["id"]}, {"_id": 0})
    if not member:
        raise HTTPException(403, "Not a member")
    perms = compute_member_permissions(server, member)
    if not has_permission(perms, Permissions.MANAGE_SERVER):
        raise HTTPException(403, "No permission to manage server")
    updates = {}
    if data.name is not None:
        updates["name"] = data.name
    if data.description is not None:
        updates["description"] = data.description
    if data.icon_url is not None:
        updates["icon_url"] = data.icon_url
    if data.storage_limit_gb is not None and user.get("role") == "admin":
        updates["storage_limit_bytes"] = int(data.storage_limit_gb * 1024 ** 3)
    if updates:
        await db.servers.update_one({"id": server_id}, {"$set": updates})
    return {"message": "Server updated"}

@router.delete("/servers/{server_id}")
async def delete_server(server_id: str, request: Request):
    user = await get_current_user(request)
    server = await db.servers.find_one({"id": server_id}, {"_id": 0})
    if not server or server["owner_id"] != user["id"]:
        raise HTTPException(403, "Only the owner can delete the server")
    await db.servers.delete_one({"id": server_id})
    await db.channels.delete_many({"server_id": server_id})
    await db.server_members.delete_many({"server_id": server_id})
    await db.channel_messages.delete_many({"server_id": server_id})
    await db.drive_files.update_many({"server_id": server_id}, {"$set": {"is_deleted": True}})
    return {"message": "Server deleted"}

# ─── INVITE / JOIN ───
@router.post("/servers/{server_id}/invites")
async def create_invite(server_id: str, data: InviteCreate, request: Request):
    user = await get_current_user(request)
    server = await db.servers.find_one({"id": server_id}, {"_id": 0})
    if not server:
        raise HTTPException(404, "Server not found")
    member = await db.server_members.find_one({"server_id": server_id, "user_id": user["id"]}, {"_id": 0})
    if not member:
        raise HTTPException(403, "Not a member")
    perms = compute_member_permissions(server, member)
    if not has_permission(perms, Permissions.CREATE_INVITE):
        raise HTTPException(403, "No permission to create invites")
    import random, string
    code = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
    invite = {
        "code": code, "server_id": server_id, "creator_id": user["id"],
        "max_uses": data.max_uses, "uses": 0,
        "expires_at": (datetime.now(timezone.utc) + timedelta(hours=data.expires_hours)).isoformat() if data.expires_hours else None,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.invites.insert_one(invite)
    invite.pop("_id", None)
    return invite

@router.get("/servers/{server_id}/invites")
async def get_server_invites(server_id: str, request: Request):
    user = await get_current_user(request)
    member = await db.server_members.find_one({"server_id": server_id, "user_id": user["id"]})
    if not member:
        raise HTTPException(403, "Not a member")
    invites = await db.invites.find({"server_id": server_id}, {"_id": 0}).to_list(100)
    return invites

@router.post("/invites/{code}/join")
async def join_server(code: str, request: Request):
    user = await get_current_user(request)
    invite = await db.invites.find_one({"code": code}, {"_id": 0})
    if not invite:
        raise HTTPException(404, "Invalid invite code")
    if invite.get("expires_at"):
        if datetime.now(timezone.utc) > datetime.fromisoformat(invite["expires_at"]):
            raise HTTPException(400, "Invite expired")
    if invite.get("max_uses") and invite["uses"] >= invite["max_uses"]:
        raise HTTPException(400, "Invite has reached maximum uses")
    existing = await db.server_members.find_one({"server_id": invite["server_id"], "user_id": user["id"]})
    if existing:
        return {"message": "Already a member", "server_id": invite["server_id"]}
    ban = await db.server_bans.find_one({"server_id": invite["server_id"], "user_id": user["id"]})
    if ban:
        raise HTTPException(403, "You are banned from this server")
    server = await db.servers.find_one({"id": invite["server_id"]}, {"_id": 0})
    everyone_role = next((r for r in server.get("roles", []) if r["name"] == "@everyone"), None) if server else None
    roles = [everyone_role["id"]] if everyone_role else []
    await db.server_members.insert_one({"server_id": invite["server_id"], "user_id": user["id"], "roles": roles, "joined_at": datetime.now(timezone.utc).isoformat()})
    await db.invites.update_one({"code": code}, {"$inc": {"uses": 1}})
    return {"message": "Joined server", "server_id": invite["server_id"]}
