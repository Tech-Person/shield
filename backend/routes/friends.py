from fastapi import APIRouter, Request, HTTPException
from deps import db, get_current_user
from models import FriendRequest
from websocket_manager import manager
from datetime import datetime, timezone

router = APIRouter()

@router.post("/friends/request")
async def send_friend_request(data: FriendRequest, request: Request):
    user = await get_current_user(request)
    target = await db.users.find_one({"username_lower": data.username.lower()}, {"_id": 0})
    if not target:
        raise HTTPException(404, "User not found")
    if target["id"] == user["id"]:
        raise HTTPException(400, "Cannot friend yourself")
    me = await db.users.find_one({"id": user["id"]}, {"_id": 0})
    if target["id"] in me.get("friends", []):
        raise HTTPException(400, "Already friends")
    if target["id"] in me.get("blocked", []) or user["id"] in target.get("blocked", []):
        raise HTTPException(400, "Cannot send friend request")
    if target["id"] in me.get("friend_requests_sent", []):
        raise HTTPException(400, "Request already sent")
    if target["id"] in me.get("friend_requests_received", []):
        await db.users.update_one({"id": user["id"]}, {"$addToSet": {"friends": target["id"]}, "$pull": {"friend_requests_received": target["id"]}})
        await db.users.update_one({"id": target["id"]}, {"$addToSet": {"friends": user["id"]}, "$pull": {"friend_requests_sent": user["id"]}})
        await manager.send_personal(target["id"], {"type": "friend_accepted", "user_id": user["id"], "username": user["username"]})
        return {"message": "Friend request accepted (mutual)"}
    await db.users.update_one({"id": user["id"]}, {"$addToSet": {"friend_requests_sent": target["id"]}})
    await db.users.update_one({"id": target["id"]}, {"$addToSet": {"friend_requests_received": user["id"]}})
    await manager.send_personal(target["id"], {"type": "friend_request", "from_user": {"id": user["id"], "username": user["username"], "display_name": user.get("display_name"), "avatar_url": user.get("avatar_url")}})
    return {"message": "Friend request sent"}

@router.post("/friends/accept/{user_id}")
async def accept_friend(user_id: str, request: Request):
    user = await get_current_user(request)
    me = await db.users.find_one({"id": user["id"]}, {"_id": 0})
    if user_id not in me.get("friend_requests_received", []):
        raise HTTPException(400, "No pending request from this user")
    await db.users.update_one({"id": user["id"]}, {"$addToSet": {"friends": user_id}, "$pull": {"friend_requests_received": user_id}})
    await db.users.update_one({"id": user_id}, {"$addToSet": {"friends": user["id"]}, "$pull": {"friend_requests_sent": user["id"]}})
    await manager.send_personal(user_id, {"type": "friend_accepted", "user_id": user["id"], "username": user["username"]})
    return {"message": "Friend request accepted"}

@router.post("/friends/reject/{user_id}")
async def reject_friend(user_id: str, request: Request):
    user = await get_current_user(request)
    await db.users.update_one({"id": user["id"]}, {"$pull": {"friend_requests_received": user_id}})
    await db.users.update_one({"id": user_id}, {"$pull": {"friend_requests_sent": user["id"]}})
    return {"message": "Friend request rejected"}

@router.delete("/friends/{user_id}")
async def remove_friend(user_id: str, request: Request):
    user = await get_current_user(request)
    await db.users.update_one({"id": user["id"]}, {"$pull": {"friends": user_id}})
    await db.users.update_one({"id": user_id}, {"$pull": {"friends": user["id"]}})
    return {"message": "Friend removed"}

@router.post("/friends/block/{user_id}")
async def block_user(user_id: str, request: Request):
    user = await get_current_user(request)
    await db.users.update_one({"id": user["id"]}, {
        "$addToSet": {"blocked": user_id},
        "$pull": {"friends": user_id, "friend_requests_sent": user_id, "friend_requests_received": user_id}
    })
    await db.users.update_one({"id": user_id}, {"$pull": {"friends": user["id"], "friend_requests_sent": user["id"], "friend_requests_received": user["id"]}})
    return {"message": "User blocked"}

@router.post("/friends/unblock/{user_id}")
async def unblock_user(user_id: str, request: Request):
    user = await get_current_user(request)
    await db.users.update_one({"id": user["id"]}, {"$pull": {"blocked": user_id}})
    return {"message": "User unblocked"}

@router.get("/friends")
async def get_friends(request: Request):
    user = await get_current_user(request)
    me = await db.users.find_one({"id": user["id"]}, {"_id": 0})
    friends = []
    for fid in me.get("friends", []):
        f = await db.users.find_one({"id": fid}, {"_id": 0, "password_hash": 0, "totp_secret": 0})
        if f:
            friends.append(f)
    pending_in = []
    for pid in me.get("friend_requests_received", []):
        p = await db.users.find_one({"id": pid}, {"_id": 0, "password_hash": 0, "totp_secret": 0})
        if p:
            pending_in.append(p)
    pending_out = []
    for pid in me.get("friend_requests_sent", []):
        p = await db.users.find_one({"id": pid}, {"_id": 0, "password_hash": 0, "totp_secret": 0})
        if p:
            pending_out.append(p)
    blocked = []
    for bid in me.get("blocked", []):
        b = await db.users.find_one({"id": bid}, {"_id": 0, "password_hash": 0, "totp_secret": 0})
        if b:
            blocked.append(b)
    return {"friends": friends, "pending_incoming": pending_in, "pending_outgoing": pending_out, "blocked": blocked}
