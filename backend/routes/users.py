from fastapi import APIRouter, Request, HTTPException
from deps import db, get_current_user, sanitize_user
from models import UserUpdate, StatusUpdate
from websocket_manager import manager
from datetime import datetime, timezone

router = APIRouter()

@router.get("/users/me")
async def get_user_profile(request: Request):
    user = await get_current_user(request)
    return sanitize_user(user)

@router.put("/users/me")
async def update_profile(data: UserUpdate, request: Request):
    user = await get_current_user(request)
    updates = {}
    if data.display_name is not None:
        updates["display_name"] = data.display_name
    if data.avatar_url is not None:
        updates["avatar_url"] = data.avatar_url
    if data.about is not None:
        updates["about"] = data.about
    if updates:
        await db.users.update_one({"id": user["id"]}, {"$set": updates})
    updated = await db.users.find_one({"id": user["id"]}, {"_id": 0, "password_hash": 0, "totp_secret": 0})
    return updated

@router.put("/users/me/status")
async def update_status(data: StatusUpdate, request: Request):
    user = await get_current_user(request)
    updates = {"status": data.status}
    if data.status_message is not None:
        updates["status_message"] = data.status_message
    if data.status_expires_minutes:
        from datetime import timedelta
        updates["status_message_expires"] = (datetime.now(timezone.utc) + timedelta(minutes=data.status_expires_minutes)).isoformat()
    else:
        updates["status_message_expires"] = None
    await db.users.update_one({"id": user["id"]}, {"$set": updates})

    # Broadcast to server members
    servers = await db.server_members.find({"user_id": user["id"]}, {"server_id": 1}).to_list(100)
    notified = set()
    for s in servers:
        members = await db.server_members.find({"server_id": s["server_id"]}, {"user_id": 1}).to_list(500)
        for m in members:
            mid = m["user_id"]
            if mid != user["id"] and mid not in notified:
                notified.add(mid)
                await manager.send_personal(mid, {
                    "type": "status_update", "user_id": user["id"],
                    "status": data.status, "status_message": data.status_message
                })
    return {"message": "Status updated"}

@router.get("/users/search")
async def search_users(q: str, request: Request):
    await get_current_user(request)
    users = await db.users.find(
        {"username_lower": {"$regex": q.lower()}},
        {"_id": 0, "password_hash": 0, "totp_secret": 0}
    ).limit(20).to_list(20)
    return users

@router.get("/users/{user_id}")
async def get_user(user_id: str, request: Request):
    await get_current_user(request)
    user = await db.users.find_one({"id": user_id}, {"_id": 0, "password_hash": 0, "totp_secret": 0})
    if not user:
        raise HTTPException(404, "User not found")
    mutual_servers = []
    their_servers = await db.server_members.find({"user_id": user_id}, {"server_id": 1}).to_list(100)
    for s in their_servers:
        server = await db.servers.find_one({"id": s["server_id"]}, {"_id": 0, "id": 1, "name": 1, "icon_url": 1})
        if server:
            mutual_servers.append(server)
    user["mutual_servers"] = mutual_servers
    return user
