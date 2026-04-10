from fastapi import APIRouter, Request, HTTPException
from deps import db, get_current_user, has_permission, compute_member_permissions
from models import RoleCreate, RoleUpdate, Permissions
from websocket_manager import manager
from datetime import datetime, timezone
import uuid

router = APIRouter()

@router.post("/servers/{server_id}/roles")
async def create_role(server_id: str, data: RoleCreate, request: Request):
    user = await get_current_user(request)
    server = await db.servers.find_one({"id": server_id}, {"_id": 0})
    if not server or server["owner_id"] != user["id"]:
        raise HTTPException(403, "No permission")
    role_id = str(uuid.uuid4())
    role = {"id": role_id, "name": data.name, "color": data.color or "#99AAB5", "permissions": data.permissions, "position": len(server.get("roles", []))}
    await db.servers.update_one({"id": server_id}, {"$push": {"roles": role}})
    return role

@router.put("/servers/{server_id}/roles/{role_id}")
async def update_role(server_id: str, role_id: str, data: RoleUpdate, request: Request):
    user = await get_current_user(request)
    server = await db.servers.find_one({"id": server_id}, {"_id": 0})
    if not server or server["owner_id"] != user["id"]:
        raise HTTPException(403, "No permission")
    updates = {}
    if data.name is not None:
        updates["roles.$.name"] = data.name
    if data.color is not None:
        updates["roles.$.color"] = data.color
    if data.permissions is not None:
        updates["roles.$.permissions"] = data.permissions
    if updates:
        await db.servers.update_one({"id": server_id, "roles.id": role_id}, {"$set": updates})
    return {"message": "Role updated"}

@router.delete("/servers/{server_id}/roles/{role_id}")
async def delete_role(server_id: str, role_id: str, request: Request):
    user = await get_current_user(request)
    server = await db.servers.find_one({"id": server_id}, {"_id": 0})
    if not server or server["owner_id"] != user["id"]:
        raise HTTPException(403, "No permission")
    role = next((r for r in server.get("roles", []) if r["id"] == role_id), None)
    if not role:
        raise HTTPException(404, "Role not found")
    if role["name"] == "@everyone":
        raise HTTPException(400, "Cannot delete the @everyone role")
    await db.servers.update_one({"id": server_id}, {"$pull": {"roles": {"id": role_id}}})
    await db.server_members.update_many({"server_id": server_id}, {"$pull": {"roles": role_id}})
    return {"message": "Role deleted"}

@router.get("/permissions/map")
async def get_permissions_map(request: Request):
    await get_current_user(request)
    return {"permissions": Permissions.PERMISSION_MAP, "default": Permissions.DEFAULT}

@router.post("/servers/{server_id}/members/{user_id}/roles/{role_id}")
async def assign_role(server_id: str, user_id: str, role_id: str, request: Request):
    user = await get_current_user(request)
    server = await db.servers.find_one({"id": server_id}, {"_id": 0})
    if not server or server["owner_id"] != user["id"]:
        raise HTTPException(403, "No permission")
    await db.server_members.update_one({"server_id": server_id, "user_id": user_id}, {"$addToSet": {"roles": role_id}})
    return {"message": "Role assigned"}

@router.delete("/servers/{server_id}/members/{user_id}/roles/{role_id}")
async def remove_role(server_id: str, user_id: str, role_id: str, request: Request):
    user = await get_current_user(request)
    server = await db.servers.find_one({"id": server_id}, {"_id": 0})
    if not server or server["owner_id"] != user["id"]:
        raise HTTPException(403, "No permission")
    await db.server_members.update_one({"server_id": server_id, "user_id": user_id}, {"$pull": {"roles": role_id}})
    return {"message": "Role removed"}

# ─── MEMBER MANAGEMENT ───
@router.post("/servers/{server_id}/kick/{user_id}")
async def kick_member(server_id: str, user_id: str, request: Request):
    user = await get_current_user(request)
    server = await db.servers.find_one({"id": server_id}, {"_id": 0})
    if not server:
        raise HTTPException(404, "Server not found")
    member = await db.server_members.find_one({"server_id": server_id, "user_id": user["id"]}, {"_id": 0})
    if not member:
        raise HTTPException(403, "Not a member")
    member_perms = compute_member_permissions(server, member)
    if not has_permission(member_perms, Permissions.KICK_MEMBERS):
        raise HTTPException(403, "No permission to kick members")
    if user_id == server["owner_id"]:
        raise HTTPException(400, "Cannot kick the owner")
    await db.server_members.delete_one({"server_id": server_id, "user_id": user_id})
    await manager.send_personal(user_id, {"type": "kicked", "server_id": server_id})
    return {"message": "Member kicked"}

@router.post("/servers/{server_id}/ban/{user_id}")
async def ban_member(server_id: str, user_id: str, request: Request):
    user = await get_current_user(request)
    server = await db.servers.find_one({"id": server_id}, {"_id": 0})
    if not server:
        raise HTTPException(404, "Server not found")
    member = await db.server_members.find_one({"server_id": server_id, "user_id": user["id"]}, {"_id": 0})
    if not member:
        raise HTTPException(403, "Not a member")
    member_perms = compute_member_permissions(server, member)
    if not has_permission(member_perms, Permissions.BAN_MEMBERS):
        raise HTTPException(403, "No permission to ban members")
    if user_id == server["owner_id"]:
        raise HTTPException(400, "Cannot ban the owner")
    await db.server_members.delete_one({"server_id": server_id, "user_id": user_id})
    await db.server_bans.insert_one({"server_id": server_id, "user_id": user_id, "banned_at": datetime.now(timezone.utc).isoformat()})
    return {"message": "Member banned"}
