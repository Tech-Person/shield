from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

from fastapi import FastAPI, APIRouter, Request, Response, HTTPException, WebSocket, WebSocketDisconnect, UploadFile, File, Query, Depends
from fastapi.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
import os
import logging
import uuid
import json
import bcrypt
import jwt
import pyotp
import qrcode
import io
import base64
import subprocess
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional, List

from models import (
    UserCreate, UserLogin, TwoFactorVerify, UserUpdate, StatusUpdate,
    FriendRequest, ServerCreate, ServerUpdate, ChannelCreate, ChannelUpdate,
    RoleCreate, RoleUpdate, MessageCreate, DMCreate, GroupDMCreate,
    SearchQuery, InviteCreate, Permissions, ReactionAdd, ThreadReply, MessageEdit
)
from encryption import encrypt_text, decrypt_text
from websocket_manager import manager
from storage_utils import init_storage, put_object, get_object, generate_storage_path

# MongoDB
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

app = FastAPI(title="Shield API")
api_router = APIRouter(prefix="/api")

JWT_SECRET = os.environ['JWT_SECRET']
JWT_ALGORITHM = "HS256"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ─── Helpers ───
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))

def create_access_token(user_id: str, username: str) -> str:
    payload = {"sub": user_id, "username": username, "exp": datetime.now(timezone.utc) + timedelta(hours=24), "type": "access"}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def create_refresh_token(user_id: str) -> str:
    payload = {"sub": user_id, "exp": datetime.now(timezone.utc) + timedelta(days=7), "type": "refresh"}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def set_auth_cookies(response: Response, access_token: str, refresh_token: str):
    is_https = os.environ.get("FRONTEND_URL", "").startswith("https")
    response.set_cookie(key="access_token", value=access_token, httponly=True, secure=is_https, samesite="lax", max_age=86400, path="/")
    response.set_cookie(key="refresh_token", value=refresh_token, httponly=True, secure=is_https, samesite="lax", max_age=604800, path="/")

async def get_current_user(request: Request) -> dict:
    token = request.cookies.get("access_token")
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")
        user = await db.users.find_one({"id": payload["sub"]})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        user.pop("_id", None)
        user.pop("password_hash", None)
        user.pop("totp_secret", None)
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

def sanitize_user(user: dict) -> dict:
    u = {k: v for k, v in user.items() if k not in ("_id", "password_hash", "totp_secret")}
    return u

def has_permission(member_permissions: int, required: int) -> bool:
    if member_permissions & Permissions.ADMINISTRATOR:
        return True
    return (member_permissions & required) == required

def compute_member_permissions(server: dict, member: dict) -> int:
    """Compute effective permissions for a member by OR-ing all their role permissions."""
    if server["owner_id"] == member.get("user_id"):
        return Permissions.ALL
    perms = 0
    for role in server.get("roles", []):
        if role["id"] in member.get("roles", []):
            perms |= role["permissions"]
    return perms

# ─── AUTH ROUTES ───
@api_router.post("/auth/register")
async def register(data: UserCreate, response: Response):
    email = data.email.lower().strip()
    username = data.username.strip()
    if len(username) < 3:
        raise HTTPException(400, "Username must be at least 3 characters")
    if len(data.password) < 6:
        raise HTTPException(400, "Password must be at least 6 characters")
    if await db.users.find_one({"email": email}):
        raise HTTPException(400, "Email already registered")
    if await db.users.find_one({"username_lower": username.lower()}):
        raise HTTPException(400, "Username already taken")

    user_id = str(uuid.uuid4())
    user_doc = {
        "id": user_id,
        "username": username,
        "username_lower": username.lower(),
        "email": email,
        "password_hash": hash_password(data.password),
        "display_name": username,
        "avatar_url": None,
        "about": "",
        "status": "online",
        "status_message": None,
        "status_message_expires": None,
        "totp_enabled": False,
        "totp_secret": None,
        "role": "user",
        "friends": [],
        "blocked": [],
        "friend_requests_sent": [],
        "friend_requests_received": [],
        "storage_used_bytes": 0,
        "storage_limit_bytes": 5 * 1024 * 1024 * 1024,
        "last_active": datetime.now(timezone.utc).isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.users.insert_one(user_doc)
    access = create_access_token(user_id, username)
    refresh = create_refresh_token(user_id)
    set_auth_cookies(response, access, refresh)
    return {"user": sanitize_user(user_doc), "access_token": access}

@api_router.post("/auth/login")
async def login(data: UserLogin, request: Request, response: Response):
    email = data.email.lower().strip()
    # Use real client IP from reverse proxy header
    ip = request.headers.get("x-real-ip") or request.headers.get("x-forwarded-for", "").split(",")[0].strip() or (request.client.host if request.client else "unknown")
    identifier = f"{ip}:{email}"

    attempt = await db.login_attempts.find_one({"identifier": identifier}, {"_id": 0})
    if attempt and attempt.get("count", 0) >= 10:
        locked_until = attempt.get("locked_until")
        if locked_until and datetime.fromisoformat(locked_until) > datetime.now(timezone.utc):
            raise HTTPException(429, "Too many attempts. Try again in 15 minutes.")
        else:
            await db.login_attempts.delete_one({"identifier": identifier})

    user = await db.users.find_one({"email": email})
    if not user or not verify_password(data.password, user["password_hash"]):
        await db.login_attempts.update_one(
            {"identifier": identifier},
            {"$inc": {"count": 1}, "$set": {"locked_until": (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()}},
            upsert=True
        )
        raise HTTPException(401, "Invalid email or password")

    await db.login_attempts.delete_one({"identifier": identifier})

    if user.get("totp_enabled"):
        temp_token = jwt.encode(
            {"sub": user["id"], "type": "2fa_pending", "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
            JWT_SECRET, algorithm=JWT_ALGORITHM
        )
        return {"requires_2fa": True, "temp_token": temp_token}

    await db.users.update_one({"id": user["id"]}, {"$set": {"status": "online", "last_active": datetime.now(timezone.utc).isoformat()}})
    access = create_access_token(user["id"], user["username"])
    refresh = create_refresh_token(user["id"])
    set_auth_cookies(response, access, refresh)
    return {"user": sanitize_user(user), "access_token": access}

@api_router.post("/auth/verify-2fa")
async def verify_2fa(data: TwoFactorVerify, request: Request, response: Response, temp_token: str = Query(...)):
    try:
        payload = jwt.decode(temp_token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "2fa_pending":
            raise HTTPException(401, "Invalid token")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid or expired token")

    user = await db.users.find_one({"id": payload["sub"]})
    if not user or not user.get("totp_secret"):
        raise HTTPException(400, "2FA not configured")

    totp = pyotp.TOTP(user["totp_secret"])
    if not totp.verify(data.code, valid_window=1):
        raise HTTPException(401, "Invalid 2FA code")

    await db.users.update_one({"id": user["id"]}, {"$set": {"status": "online", "last_active": datetime.now(timezone.utc).isoformat()}})
    access = create_access_token(user["id"], user["username"])
    refresh = create_refresh_token(user["id"])
    set_auth_cookies(response, access, refresh)
    return {"user": sanitize_user(user), "access_token": access}

@api_router.post("/auth/setup-2fa")
async def setup_2fa(request: Request):
    user = await get_current_user(request)
    secret = pyotp.random_base32()
    totp = pyotp.TOTP(secret)
    uri = totp.provisioning_uri(name=user["email"], issuer_name="Shield")
    qr = qrcode.make(uri)
    buf = io.BytesIO()
    qr.save(buf, format="PNG")
    qr_b64 = base64.b64encode(buf.getvalue()).decode()
    await db.users.update_one({"id": user["id"]}, {"$set": {"totp_secret": secret}})
    return {"secret": secret, "qr_code": f"data:image/png;base64,{qr_b64}", "uri": uri}

@api_router.post("/auth/confirm-2fa")
async def confirm_2fa(data: TwoFactorVerify, request: Request):
    user = await get_current_user(request)
    full_user = await db.users.find_one({"id": user["id"]})
    if not full_user or not full_user.get("totp_secret"):
        raise HTTPException(400, "Setup 2FA first")
    totp = pyotp.TOTP(full_user["totp_secret"])
    if not totp.verify(data.code, valid_window=1):
        raise HTTPException(400, "Invalid code")
    await db.users.update_one({"id": user["id"]}, {"$set": {"totp_enabled": True}})
    return {"message": "2FA enabled successfully"}

@api_router.post("/auth/disable-2fa")
async def disable_2fa(data: TwoFactorVerify, request: Request):
    user = await get_current_user(request)
    full_user = await db.users.find_one({"id": user["id"]})
    if not full_user or not full_user.get("totp_enabled"):
        raise HTTPException(400, "2FA not enabled")
    totp = pyotp.TOTP(full_user["totp_secret"])
    if not totp.verify(data.code, valid_window=1):
        raise HTTPException(400, "Invalid code")
    await db.users.update_one({"id": user["id"]}, {"$set": {"totp_enabled": False, "totp_secret": None}})
    return {"message": "2FA disabled"}

@api_router.get("/auth/me")
async def get_me(request: Request):
    user = await get_current_user(request)
    return {"user": user}

@api_router.post("/auth/logout")
async def logout(request: Request, response: Response):
    try:
        user = await get_current_user(request)
        await db.users.update_one({"id": user["id"]}, {"$set": {"last_active": datetime.now(timezone.utc).isoformat()}})
    except Exception:
        pass
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")
    return {"message": "Logged out"}

@api_router.post("/auth/refresh")
async def refresh_token(request: Request, response: Response):
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(401, "No refresh token")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(401, "Invalid token type")
        user = await db.users.find_one({"id": payload["sub"]})
        if not user:
            raise HTTPException(401, "User not found")
        access = create_access_token(user["id"], user["username"])
        is_https = os.environ.get("FRONTEND_URL", "").startswith("https")
        response.set_cookie(key="access_token", value=access, httponly=True, secure=is_https, samesite="lax", max_age=86400, path="/")
        return {"access_token": access}
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid refresh token")

# ─── USER ROUTES ───
@api_router.get("/users/me")
async def get_user_profile(request: Request):
    user = await get_current_user(request)
    return user

@api_router.put("/users/me")
async def update_profile(data: UserUpdate, request: Request):
    user = await get_current_user(request)
    updates = {k: v for k, v in data.model_dump(exclude_unset=True).items()}
    if updates:
        await db.users.update_one({"id": user["id"]}, {"$set": updates})
    updated = await db.users.find_one({"id": user["id"]}, {"_id": 0, "password_hash": 0, "totp_secret": 0})
    return updated

@api_router.put("/users/me/status")
async def update_status(data: StatusUpdate, request: Request):
    user = await get_current_user(request)
    if data.status not in ("online", "away", "busy", "invisible"):
        raise HTTPException(400, "Invalid status")
    updates = {"status": data.status, "last_active": datetime.now(timezone.utc).isoformat()}
    if data.status_message is not None:
        updates["status_message"] = data.status_message
        if data.status_expires_minutes:
            updates["status_message_expires"] = (datetime.now(timezone.utc) + timedelta(minutes=data.status_expires_minutes)).isoformat()
        else:
            updates["status_message_expires"] = None
    await db.users.update_one({"id": user["id"]}, {"$set": updates})
    await manager.broadcast_to_users(
        user.get("friends", []),
        {"type": "status_update", "user_id": user["id"], "status": data.status, "status_message": data.status_message}
    )
    return {"message": "Status updated"}

@api_router.get("/users/search")
async def search_users(q: str, request: Request):
    await get_current_user(request)
    users = await db.users.find(
        {"username_lower": {"$regex": q.lower(), "$options": "i"}},
        {"_id": 0, "password_hash": 0, "totp_secret": 0, "email": 0}
    ).limit(20).to_list(20)
    return users

@api_router.get("/users/{user_id}")
async def get_user(user_id: str, request: Request):
    await get_current_user(request)
    user = await db.users.find_one({"id": user_id}, {"_id": 0, "password_hash": 0, "totp_secret": 0, "email": 0})
    if not user:
        raise HTTPException(404, "User not found")
    online = manager.is_online(user_id)
    user["is_online"] = online if user.get("status") != "invisible" else False
    if user.get("status_message_expires"):
        exp = datetime.fromisoformat(user["status_message_expires"])
        if exp < datetime.now(timezone.utc):
            user["status_message"] = None
    return user

# ─── FRIENDS ROUTES ───
@api_router.post("/friends/request")
async def send_friend_request(data: FriendRequest, request: Request):
    user = await get_current_user(request)
    target = await db.users.find_one({"username_lower": data.username.lower()}, {"_id": 0})
    if not target:
        raise HTTPException(404, "User not found")
    if target["id"] == user["id"]:
        raise HTTPException(400, "Cannot friend yourself")
    if target["id"] in user.get("friends", []):
        raise HTTPException(400, "Already friends")
    if target["id"] in user.get("blocked", []):
        raise HTTPException(400, "User is blocked")
    if user["id"] in target.get("blocked", []):
        raise HTTPException(400, "You are blocked by this user")
    if target["id"] in user.get("friend_requests_sent", []):
        raise HTTPException(400, "Request already sent")

    if user["id"] in target.get("friend_requests_sent", []):
        await db.users.update_one({"id": user["id"]}, {
            "$addToSet": {"friends": target["id"]},
            "$pull": {"friend_requests_received": target["id"]}
        })
        await db.users.update_one({"id": target["id"]}, {
            "$addToSet": {"friends": user["id"]},
            "$pull": {"friend_requests_sent": user["id"]}
        })
        await manager.send_personal(target["id"], {"type": "friend_accepted", "user": sanitize_user(user)})
        return {"message": "Friend added (mutual request)"}

    await db.users.update_one({"id": user["id"]}, {"$addToSet": {"friend_requests_sent": target["id"]}})
    await db.users.update_one({"id": target["id"]}, {"$addToSet": {"friend_requests_received": user["id"]}})
    await manager.send_personal(target["id"], {"type": "friend_request", "user": sanitize_user(user)})
    return {"message": "Friend request sent"}

@api_router.post("/friends/accept/{user_id}")
async def accept_friend(user_id: str, request: Request):
    user = await get_current_user(request)
    if user_id not in user.get("friend_requests_received", []):
        raise HTTPException(400, "No pending request from this user")
    await db.users.update_one({"id": user["id"]}, {
        "$addToSet": {"friends": user_id},
        "$pull": {"friend_requests_received": user_id}
    })
    await db.users.update_one({"id": user_id}, {
        "$addToSet": {"friends": user["id"]},
        "$pull": {"friend_requests_sent": user["id"]}
    })
    await manager.send_personal(user_id, {"type": "friend_accepted", "user": sanitize_user(user)})
    return {"message": "Friend request accepted"}

@api_router.post("/friends/reject/{user_id}")
async def reject_friend(user_id: str, request: Request):
    user = await get_current_user(request)
    await db.users.update_one({"id": user["id"]}, {"$pull": {"friend_requests_received": user_id}})
    await db.users.update_one({"id": user_id}, {"$pull": {"friend_requests_sent": user["id"]}})
    return {"message": "Friend request rejected"}

@api_router.delete("/friends/{user_id}")
async def remove_friend(user_id: str, request: Request):
    user = await get_current_user(request)
    await db.users.update_one({"id": user["id"]}, {"$pull": {"friends": user_id}})
    await db.users.update_one({"id": user_id}, {"$pull": {"friends": user["id"]}})
    return {"message": "Friend removed"}

@api_router.post("/friends/block/{user_id}")
async def block_user(user_id: str, request: Request):
    user = await get_current_user(request)
    await db.users.update_one({"id": user["id"]}, {
        "$addToSet": {"blocked": user_id},
        "$pull": {"friends": user_id, "friend_requests_received": user_id, "friend_requests_sent": user_id}
    })
    await db.users.update_one({"id": user_id}, {"$pull": {"friends": user["id"]}})
    return {"message": "User blocked"}

@api_router.post("/friends/unblock/{user_id}")
async def unblock_user(user_id: str, request: Request):
    user = await get_current_user(request)
    await db.users.update_one({"id": user["id"]}, {"$pull": {"blocked": user_id}})
    return {"message": "User unblocked"}

@api_router.get("/friends")
async def get_friends(request: Request):
    user = await get_current_user(request)
    full_user = await db.users.find_one({"id": user["id"]}, {"_id": 0})
    friends = []
    for fid in full_user.get("friends", []):
        f = await db.users.find_one({"id": fid}, {"_id": 0, "password_hash": 0, "totp_secret": 0, "email": 0})
        if f:
            f["is_online"] = manager.is_online(fid) if f.get("status") != "invisible" else False
            friends.append(f)
    pending_in = []
    for pid in full_user.get("friend_requests_received", []):
        p = await db.users.find_one({"id": pid}, {"_id": 0, "password_hash": 0, "totp_secret": 0, "email": 0})
        if p:
            pending_in.append(p)
    pending_out = []
    for pid in full_user.get("friend_requests_sent", []):
        p = await db.users.find_one({"id": pid}, {"_id": 0, "password_hash": 0, "totp_secret": 0, "email": 0})
        if p:
            pending_out.append(p)
    return {"friends": friends, "pending_incoming": pending_in, "pending_outgoing": pending_out, "blocked": full_user.get("blocked", [])}

# ─── DM ROUTES ───
@api_router.post("/dm/create")
async def create_dm(data: DMCreate, request: Request):
    user = await get_current_user(request)
    existing = await db.conversations.find_one({
        "type": "dm",
        "participants": {"$all": [user["id"], data.recipient_id], "$size": 2}
    }, {"_id": 0})
    if existing:
        return existing

    conv_id = str(uuid.uuid4())
    conv = {
        "id": conv_id,
        "type": "dm",
        "participants": [user["id"], data.recipient_id],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "last_message_at": datetime.now(timezone.utc).isoformat()
    }
    await db.conversations.insert_one(conv)
    conv.pop("_id", None)
    return conv

@api_router.post("/dm/group")
async def create_group_dm(data: GroupDMCreate, request: Request):
    user = await get_current_user(request)
    all_members = list(set([user["id"]] + data.member_ids))
    conv_id = str(uuid.uuid4())
    conv = {
        "id": conv_id,
        "type": "group_dm",
        "name": data.name or "Group Chat",
        "participants": all_members,
        "owner_id": user["id"],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "last_message_at": datetime.now(timezone.utc).isoformat()
    }
    await db.conversations.insert_one(conv)
    conv.pop("_id", None)
    return conv

@api_router.get("/dm/conversations")
async def get_conversations(request: Request):
    user = await get_current_user(request)
    convos = await db.conversations.find(
        {"participants": user["id"]},
        {"_id": 0}
    ).sort("last_message_at", -1).to_list(100)
    for conv in convos:
        if conv["type"] == "dm":
            other_id = [p for p in conv["participants"] if p != user["id"]]
            if other_id:
                other = await db.users.find_one({"id": other_id[0]}, {"_id": 0, "password_hash": 0, "totp_secret": 0})
                if other:
                    other["is_online"] = manager.is_online(other_id[0]) if other.get("status") != "invisible" else False
                    conv["other_user"] = other
        last_msg = await db.messages.find_one(
            {"conversation_id": conv["id"]}, {"_id": 0}, sort=[("created_at", -1)]
        )
        if last_msg and last_msg.get("content_encrypted"):
            last_msg["content"] = decrypt_text(last_msg["content_encrypted"])
            last_msg.pop("content_encrypted", None)
            last_msg.pop("search_index", None)
        conv["last_message"] = last_msg
    return convos

@api_router.post("/dm/{conversation_id}/messages")
async def send_dm_message(conversation_id: str, data: MessageCreate, request: Request):
    user = await get_current_user(request)
    conv = await db.conversations.find_one({"id": conversation_id, "participants": user["id"]}, {"_id": 0})
    if not conv:
        raise HTTPException(404, "Conversation not found")

    msg_id = str(uuid.uuid4())
    encrypted_content = encrypt_text(data.content)
    search_tokens = " ".join(data.content.lower().split())

    msg = {
        "id": msg_id,
        "conversation_id": conversation_id,
        "sender_id": user["id"],
        "sender_username": user["username"],
        "sender_avatar": user.get("avatar_url"),
        "content_encrypted": encrypted_content,
        "search_index": encrypt_text(search_tokens),
        "attachments": data.attachments or [],
        "edited": False,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.messages.insert_one(msg)
    await db.conversations.update_one({"id": conversation_id}, {"$set": {"last_message_at": datetime.now(timezone.utc).isoformat()}})

    broadcast_msg = {
        "type": "new_message",
        "message": {
            "id": msg_id,
            "conversation_id": conversation_id,
            "sender_id": user["id"],
            "sender_username": user["username"],
            "sender_avatar": user.get("avatar_url"),
            "content": data.content,
            "attachments": data.attachments or [],
            "edited": False,
            "created_at": msg["created_at"]
        }
    }
    for pid in conv["participants"]:
        if pid != user["id"]:
            await manager.send_personal(pid, broadcast_msg)
    await manager.broadcast_dm(conversation_id, broadcast_msg, exclude=user["id"])

    await db.stats.update_one({"key": "global"}, {"$inc": {"messages_sent": 1}}, upsert=True)

    resp = broadcast_msg["message"].copy()
    resp.pop("_id", None)
    return resp

@api_router.get("/dm/{conversation_id}/messages")
async def get_dm_messages(conversation_id: str, request: Request, before: Optional[str] = None, limit: int = 50):
    user = await get_current_user(request)
    conv = await db.conversations.find_one({"id": conversation_id, "participants": user["id"]}, {"_id": 0})
    if not conv:
        raise HTTPException(404, "Conversation not found")

    query = {"conversation_id": conversation_id}
    if before:
        query["created_at"] = {"$lt": before}

    messages = await db.messages.find(query, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(limit)
    for msg in messages:
        if msg.get("content_encrypted"):
            msg["content"] = decrypt_text(msg["content_encrypted"])
        msg.pop("content_encrypted", None)
        msg.pop("search_index", None)
        msg["reactions"] = await db.reactions.find({"message_id": msg["id"]}, {"_id": 0}).to_list(50)
        msg["thread_count"] = msg.get("thread_count", 0)
    messages.reverse()
    return messages

@api_router.post("/dm/search")
async def search_messages(data: SearchQuery, request: Request):
    user = await get_current_user(request)
    query_lower = data.query.lower()
    if data.conversation_id:
        conv = await db.conversations.find_one({"id": data.conversation_id, "participants": user["id"]}, {"_id": 0})
        if not conv:
            raise HTTPException(404, "Conversation not found")
        messages = await db.messages.find({"conversation_id": data.conversation_id}, {"_id": 0}).sort("created_at", -1).limit(500).to_list(500)
    else:
        user_convos = await db.conversations.find({"participants": user["id"]}, {"_id": 0, "id": 1}).to_list(100)
        conv_ids = [c["id"] for c in user_convos]
        messages = await db.messages.find({"conversation_id": {"$in": conv_ids}}, {"_id": 0}).sort("created_at", -1).limit(500).to_list(500)

    results = []
    for msg in messages:
        content = decrypt_text(msg.get("content_encrypted", ""))
        if query_lower in content.lower():
            msg["content"] = content
            msg.pop("content_encrypted", None)
            msg.pop("search_index", None)
            results.append(msg)
            if len(results) >= data.limit:
                break
    return results

# ─── SERVER ROUTES ───
@api_router.post("/servers")
async def create_server(data: ServerCreate, request: Request):
    user = await get_current_user(request)
    server_id = str(uuid.uuid4())
    default_role_id = str(uuid.uuid4())

    server = {
        "id": server_id,
        "name": data.name,
        "description": data.description or "",
        "icon_url": data.icon_url,
        "owner_id": user["id"],
        "roles": [{
            "id": default_role_id,
            "name": "@everyone",
            "color": "#99AAB5",
            "permissions": Permissions.DEFAULT,
            "position": 0
        }],
        "channels": [],
        "storage_used_bytes": 0,
        "storage_limit_bytes": 25 * 1024 * 1024 * 1024,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.servers.insert_one(server)

    general_channel_id = str(uuid.uuid4())
    general_voice_id = str(uuid.uuid4())
    channels = [
        {"id": general_channel_id, "server_id": server_id, "name": "general", "channel_type": "text", "category": "Text Channels", "topic": "", "slowmode_seconds": 0, "created_at": datetime.now(timezone.utc).isoformat()},
        {"id": general_voice_id, "server_id": server_id, "name": "General", "channel_type": "voice", "category": "Voice Channels", "topic": "", "slowmode_seconds": 0, "created_at": datetime.now(timezone.utc).isoformat()}
    ]
    await db.channels.insert_many(channels)

    member = {
        "id": str(uuid.uuid4()),
        "server_id": server_id,
        "user_id": user["id"],
        "username": user["username"],
        "display_name": user.get("display_name", user["username"]),
        "avatar_url": user.get("avatar_url"),
        "roles": [default_role_id],
        "is_owner": True,
        "joined_at": datetime.now(timezone.utc).isoformat()
    }
    await db.server_members.insert_one(member)

    invite_code = str(uuid.uuid4())[:8]
    await db.invites.insert_one({
        "id": str(uuid.uuid4()),
        "code": invite_code,
        "server_id": server_id,
        "creator_id": user["id"],
        "max_uses": None,
        "uses": 0,
        "expires_at": None,
        "created_at": datetime.now(timezone.utc).isoformat()
    })

    await db.stats.update_one({"key": "global"}, {"$inc": {"total_servers": 1}}, upsert=True)
    server.pop("_id", None)
    server["invite_code"] = invite_code
    return server

@api_router.get("/servers")
async def get_user_servers(request: Request):
    user = await get_current_user(request)
    memberships = await db.server_members.find({"user_id": user["id"]}, {"_id": 0}).to_list(100)
    server_ids = [m["server_id"] for m in memberships]
    servers = await db.servers.find({"id": {"$in": server_ids}}, {"_id": 0}).to_list(100)
    return servers

@api_router.get("/servers/{server_id}")
async def get_server(server_id: str, request: Request):
    user = await get_current_user(request)
    member = await db.server_members.find_one({"server_id": server_id, "user_id": user["id"]}, {"_id": 0})
    if not member:
        raise HTTPException(403, "Not a member of this server")
    server = await db.servers.find_one({"id": server_id}, {"_id": 0})
    if not server:
        raise HTTPException(404, "Server not found")
    channels = await db.channels.find({"server_id": server_id}, {"_id": 0}).to_list(100)
    members = await db.server_members.find({"server_id": server_id}, {"_id": 0}).to_list(1000)
    for m in members:
        m["is_online"] = manager.is_online(m["user_id"])
    server["channels"] = channels
    server["members"] = members
    server["member_count"] = len(members)
    return server

@api_router.put("/servers/{server_id}")
async def update_server(server_id: str, data: ServerUpdate, request: Request):
    user = await get_current_user(request)
    server = await db.servers.find_one({"id": server_id}, {"_id": 0})
    if not server:
        raise HTTPException(404, "Server not found")
    if server["owner_id"] != user["id"]:
        raise HTTPException(403, "Only the owner can update server settings")
    updates = {k: v for k, v in data.model_dump(exclude_unset=True).items()}
    if "storage_limit_gb" in updates:
        new_limit = int(updates.pop("storage_limit_gb") * 1024 * 1024 * 1024)
        admin_approved = server.get("admin_approved_limit_bytes", server.get("storage_limit_bytes", 25 * 1024**3))
        if new_limit > admin_approved:
            raise HTTPException(400, f"Cannot exceed admin-approved limit of {admin_approved / (1024**3):.1f} GB. Request more via storage requests.")
        updates["storage_limit_bytes"] = new_limit
    if updates:
        await db.servers.update_one({"id": server_id}, {"$set": updates})
    return {"message": "Server updated"}

@api_router.delete("/servers/{server_id}")
async def delete_server(server_id: str, request: Request):
    user = await get_current_user(request)
    server = await db.servers.find_one({"id": server_id}, {"_id": 0})
    if not server or server["owner_id"] != user["id"]:
        raise HTTPException(403, "Only the owner can delete a server")
    await db.servers.delete_one({"id": server_id})
    await db.channels.delete_many({"server_id": server_id})
    await db.server_members.delete_many({"server_id": server_id})
    await db.channel_messages.delete_many({"server_id": server_id})
    await db.invites.delete_many({"server_id": server_id})
    await db.stats.update_one({"key": "global"}, {"$inc": {"total_servers": -1}}, upsert=True)
    return {"message": "Server deleted"}

# ─── INVITE / JOIN ───
@api_router.post("/servers/{server_id}/invites")
async def create_invite(server_id: str, data: InviteCreate, request: Request):
    user = await get_current_user(request)
    member = await db.server_members.find_one({"server_id": server_id, "user_id": user["id"]}, {"_id": 0})
    if not member:
        raise HTTPException(403, "Not a member")
    code = str(uuid.uuid4())[:8]
    invite = {
        "id": str(uuid.uuid4()),
        "code": code,
        "server_id": server_id,
        "creator_id": user["id"],
        "max_uses": data.max_uses,
        "uses": 0,
        "expires_at": (datetime.now(timezone.utc) + timedelta(hours=data.expires_hours)).isoformat() if data.expires_hours else None,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.invites.insert_one(invite)
    invite.pop("_id", None)
    return invite

@api_router.post("/invites/{code}/join")
async def join_server(code: str, request: Request):
    user = await get_current_user(request)
    invite = await db.invites.find_one({"code": code}, {"_id": 0})
    if not invite:
        raise HTTPException(404, "Invalid invite code")
    if invite.get("expires_at"):
        exp = datetime.fromisoformat(invite["expires_at"])
        if exp < datetime.now(timezone.utc):
            raise HTTPException(400, "Invite expired")
    if invite.get("max_uses") and invite["uses"] >= invite["max_uses"]:
        raise HTTPException(400, "Invite max uses reached")

    existing = await db.server_members.find_one({"server_id": invite["server_id"], "user_id": user["id"]})
    if existing:
        raise HTTPException(400, "Already a member")

    server = await db.servers.find_one({"id": invite["server_id"]}, {"_id": 0})
    if not server:
        raise HTTPException(404, "Server not found")

    default_role = next((r for r in server.get("roles", []) if r["name"] == "@everyone"), None)
    member = {
        "id": str(uuid.uuid4()),
        "server_id": invite["server_id"],
        "user_id": user["id"],
        "username": user["username"],
        "display_name": user.get("display_name", user["username"]),
        "avatar_url": user.get("avatar_url"),
        "roles": [default_role["id"]] if default_role else [],
        "is_owner": False,
        "joined_at": datetime.now(timezone.utc).isoformat()
    }
    await db.server_members.insert_one(member)
    await db.invites.update_one({"code": code}, {"$inc": {"uses": 1}})
    return {"message": "Joined server", "server": server}

# ─── CHANNEL ROUTES ───
@api_router.post("/servers/{server_id}/channels")
async def create_channel(server_id: str, data: ChannelCreate, request: Request):
    user = await get_current_user(request)
    server = await db.servers.find_one({"id": server_id}, {"_id": 0})
    if not server:
        raise HTTPException(404, "Server not found")
    member = await db.server_members.find_one({"server_id": server_id, "user_id": user["id"]}, {"_id": 0})
    if not member:
        raise HTTPException(403, "Not a member")
    member_perms = compute_member_permissions(server, member)
    if not has_permission(member_perms, Permissions.MANAGE_CHANNELS):
        raise HTTPException(403, "No permission to manage channels")

    channel_id = str(uuid.uuid4())
    channel = {
        "id": channel_id,
        "server_id": server_id,
        "name": data.name.lower().replace(" ", "-"),
        "channel_type": data.channel_type,
        "category": data.category or "General",
        "topic": "",
        "slowmode_seconds": data.slowmode_seconds,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.channels.insert_one(channel)
    channel.pop("_id", None)
    return channel

@api_router.put("/servers/{server_id}/channels/{channel_id}")
async def update_channel(server_id: str, channel_id: str, data: ChannelUpdate, request: Request):
    user = await get_current_user(request)
    server = await db.servers.find_one({"id": server_id}, {"_id": 0})
    if not server or server["owner_id"] != user["id"]:
        raise HTTPException(403, "No permission")
    updates = {k: v for k, v in data.model_dump(exclude_unset=True).items()}
    if updates:
        await db.channels.update_one({"id": channel_id, "server_id": server_id}, {"$set": updates})
    return {"message": "Channel updated"}

@api_router.delete("/servers/{server_id}/channels/{channel_id}")
async def delete_channel(server_id: str, channel_id: str, request: Request):
    user = await get_current_user(request)
    server = await db.servers.find_one({"id": server_id}, {"_id": 0})
    if not server or server["owner_id"] != user["id"]:
        raise HTTPException(403, "No permission")
    await db.channels.delete_one({"id": channel_id, "server_id": server_id})
    await db.channel_messages.delete_many({"channel_id": channel_id})
    return {"message": "Channel deleted"}

# ─── CHANNEL MESSAGES ───
@api_router.post("/channels/{channel_id}/messages")
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
        last_msg = await db.channel_messages.find_one(
            {"channel_id": channel_id, "sender_id": user["id"]},
            {"_id": 0}, sort=[("created_at", -1)]
        )
        if last_msg:
            last_time = datetime.fromisoformat(last_msg["created_at"])
            diff = (datetime.now(timezone.utc) - last_time).total_seconds()
            if diff < channel["slowmode_seconds"]:
                raise HTTPException(429, f"Slowmode active. Wait {int(channel['slowmode_seconds'] - diff)}s")

    msg_id = str(uuid.uuid4())
    encrypted_content = encrypt_text(data.content)
    msg = {
        "id": msg_id,
        "channel_id": channel_id,
        "server_id": channel["server_id"],
        "sender_id": user["id"],
        "sender_username": user["username"],
        "sender_avatar": user.get("avatar_url"),
        "content_encrypted": encrypted_content,
        "attachments": data.attachments or [],
        "edited": False,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.channel_messages.insert_one(msg)

    broadcast_msg = {
        "type": "channel_message",
        "message": {
            "id": msg_id,
            "channel_id": channel_id,
            "server_id": channel["server_id"],
            "sender_id": user["id"],
            "sender_username": user["username"],
            "sender_avatar": user.get("avatar_url"),
            "content": data.content,
            "attachments": data.attachments or [],
            "edited": False,
            "created_at": msg["created_at"]
        }
    }
    await manager.broadcast_channel(channel_id, broadcast_msg, exclude=user["id"])
    await db.stats.update_one({"key": "global"}, {"$inc": {"messages_sent": 1}}, upsert=True)

    resp = broadcast_msg["message"].copy()
    return resp

@api_router.get("/channels/{channel_id}/messages")
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
        if msg.get("content_encrypted"):
            msg["content"] = decrypt_text(msg["content_encrypted"])
        msg.pop("content_encrypted", None)
        msg["reactions"] = await db.reactions.find({"message_id": msg["id"]}, {"_id": 0}).to_list(50)
        msg["thread_count"] = msg.get("thread_count", 0)
    messages.reverse()
    return messages

# ─── REACTIONS (DM & Channel) ───
@api_router.post("/messages/{message_id}/reactions")
async def add_dm_reaction(message_id: str, data: ReactionAdd, request: Request):
    user = await get_current_user(request)
    msg = await db.messages.find_one({"id": message_id}, {"_id": 0})
    if not msg:
        raise HTTPException(404, "Message not found")
    conv = await db.conversations.find_one({"id": msg["conversation_id"], "participants": user["id"]}, {"_id": 0})
    if not conv:
        raise HTTPException(403, "Not a participant")
    await db.reactions.update_one(
        {"message_id": message_id, "emoji": data.emoji, "user_id": user["id"]},
        {"$setOnInsert": {"id": str(uuid.uuid4()), "message_id": message_id, "emoji": data.emoji, "user_id": user["id"], "username": user["username"], "created_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True
    )
    reactions = await db.reactions.find({"message_id": message_id}, {"_id": 0}).to_list(100)
    for pid in conv["participants"]:
        await manager.send_personal(pid, {"type": "reaction_update", "message_id": message_id, "reactions": reactions})
    return {"message": "Reaction added"}

@api_router.delete("/messages/{message_id}/reactions/{emoji}")
async def remove_dm_reaction(message_id: str, emoji: str, request: Request):
    user = await get_current_user(request)
    await db.reactions.delete_one({"message_id": message_id, "emoji": emoji, "user_id": user["id"]})
    reactions = await db.reactions.find({"message_id": message_id}, {"_id": 0}).to_list(100)
    msg = await db.messages.find_one({"id": message_id}, {"_id": 0})
    if msg:
        conv = await db.conversations.find_one({"id": msg["conversation_id"]}, {"_id": 0})
        if conv:
            for pid in conv["participants"]:
                await manager.send_personal(pid, {"type": "reaction_update", "message_id": message_id, "reactions": reactions})
    return {"message": "Reaction removed"}

@api_router.get("/messages/{message_id}/reactions")
async def get_dm_reactions(message_id: str, request: Request):
    await get_current_user(request)
    reactions = await db.reactions.find({"message_id": message_id}, {"_id": 0}).to_list(100)
    return reactions

@api_router.post("/channel-messages/{message_id}/reactions")
async def add_channel_reaction(message_id: str, data: ReactionAdd, request: Request):
    user = await get_current_user(request)
    msg = await db.channel_messages.find_one({"id": message_id}, {"_id": 0})
    if not msg:
        raise HTTPException(404, "Message not found")
    member = await db.server_members.find_one({"server_id": msg["server_id"], "user_id": user["id"]})
    if not member:
        raise HTTPException(403, "Not a member")
    await db.reactions.update_one(
        {"message_id": message_id, "emoji": data.emoji, "user_id": user["id"]},
        {"$setOnInsert": {"id": str(uuid.uuid4()), "message_id": message_id, "emoji": data.emoji, "user_id": user["id"], "username": user["username"], "created_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True
    )
    reactions = await db.reactions.find({"message_id": message_id}, {"_id": 0}).to_list(100)
    await manager.broadcast_channel(msg["channel_id"], {"type": "reaction_update", "message_id": message_id, "reactions": reactions})
    return {"message": "Reaction added"}

@api_router.delete("/channel-messages/{message_id}/reactions/{emoji}")
async def remove_channel_reaction(message_id: str, emoji: str, request: Request):
    user = await get_current_user(request)
    await db.reactions.delete_one({"message_id": message_id, "emoji": emoji, "user_id": user["id"]})
    reactions = await db.reactions.find({"message_id": message_id}, {"_id": 0}).to_list(100)
    msg = await db.channel_messages.find_one({"id": message_id}, {"_id": 0})
    if msg:
        await manager.broadcast_channel(msg["channel_id"], {"type": "reaction_update", "message_id": message_id, "reactions": reactions})
    return {"message": "Reaction removed"}

# ─── THREADS ───
@api_router.post("/messages/{message_id}/thread")
async def reply_dm_thread(message_id: str, data: ThreadReply, request: Request):
    user = await get_current_user(request)
    parent = await db.messages.find_one({"id": message_id}, {"_id": 0})
    if not parent:
        raise HTTPException(404, "Message not found")
    conv = await db.conversations.find_one({"id": parent["conversation_id"], "participants": user["id"]}, {"_id": 0})
    if not conv:
        raise HTTPException(403, "Not a participant")
    reply_id = str(uuid.uuid4())
    encrypted_content = encrypt_text(data.content)
    reply = {
        "id": reply_id,
        "parent_message_id": message_id,
        "conversation_id": parent["conversation_id"],
        "sender_id": user["id"],
        "sender_username": user["username"],
        "sender_avatar": user.get("avatar_url"),
        "content_encrypted": encrypted_content,
        "attachments": data.attachments or [],
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.thread_replies.insert_one(reply)
    await db.messages.update_one({"id": message_id}, {"$inc": {"thread_count": 1}})
    broadcast = {"type": "thread_reply", "parent_message_id": message_id, "reply": {
        "id": reply_id, "parent_message_id": message_id, "sender_id": user["id"],
        "sender_username": user["username"], "content": data.content,
        "attachments": data.attachments or [], "created_at": reply["created_at"]
    }}
    for pid in conv["participants"]:
        await manager.send_personal(pid, broadcast)
    return broadcast["reply"]

@api_router.get("/messages/{message_id}/thread")
async def get_dm_thread(message_id: str, request: Request):
    await get_current_user(request)
    replies = await db.thread_replies.find({"parent_message_id": message_id}, {"_id": 0}).sort("created_at", 1).to_list(200)
    for r in replies:
        if r.get("content_encrypted"):
            r["content"] = decrypt_text(r["content_encrypted"])
        r.pop("content_encrypted", None)
    return replies

@api_router.post("/channel-messages/{message_id}/thread")
async def reply_channel_thread(message_id: str, data: ThreadReply, request: Request):
    user = await get_current_user(request)
    parent = await db.channel_messages.find_one({"id": message_id}, {"_id": 0})
    if not parent:
        raise HTTPException(404, "Message not found")
    member = await db.server_members.find_one({"server_id": parent["server_id"], "user_id": user["id"]})
    if not member:
        raise HTTPException(403, "Not a member")
    reply_id = str(uuid.uuid4())
    encrypted_content = encrypt_text(data.content)
    reply = {
        "id": reply_id,
        "parent_message_id": message_id,
        "channel_id": parent["channel_id"],
        "server_id": parent["server_id"],
        "sender_id": user["id"],
        "sender_username": user["username"],
        "sender_avatar": user.get("avatar_url"),
        "content_encrypted": encrypted_content,
        "attachments": data.attachments or [],
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.thread_replies.insert_one(reply)
    await db.channel_messages.update_one({"id": message_id}, {"$inc": {"thread_count": 1}})
    broadcast = {"type": "thread_reply", "parent_message_id": message_id, "reply": {
        "id": reply_id, "parent_message_id": message_id, "sender_id": user["id"],
        "sender_username": user["username"], "content": data.content,
        "attachments": data.attachments or [], "created_at": reply["created_at"]
    }}
    await manager.broadcast_channel(parent["channel_id"], broadcast)
    return broadcast["reply"]

@api_router.get("/channel-messages/{message_id}/thread")
async def get_channel_thread(message_id: str, request: Request):
    await get_current_user(request)
    replies = await db.thread_replies.find({"parent_message_id": message_id}, {"_id": 0}).sort("created_at", 1).to_list(200)
    for r in replies:
        if r.get("content_encrypted"):
            r["content"] = decrypt_text(r["content_encrypted"])
        r.pop("content_encrypted", None)
    return replies

# ─── MESSAGE EDIT / DELETE ───
@api_router.put("/messages/{message_id}")
async def edit_dm_message(message_id: str, data: MessageEdit, request: Request):
    user = await get_current_user(request)
    msg = await db.messages.find_one({"id": message_id, "sender_id": user["id"]}, {"_id": 0})
    if not msg:
        raise HTTPException(404, "Message not found or not yours")
    encrypted = encrypt_text(data.content)
    await db.messages.update_one({"id": message_id}, {"$set": {"content_encrypted": encrypted, "edited": True}})
    conv = await db.conversations.find_one({"id": msg["conversation_id"]}, {"_id": 0})
    if conv:
        for pid in conv["participants"]:
            await manager.send_personal(pid, {"type": "message_edited", "message_id": message_id, "content": data.content, "edited": True})
    return {"message": "Edited"}

@api_router.delete("/messages/{message_id}")
async def delete_dm_message(message_id: str, request: Request):
    user = await get_current_user(request)
    msg = await db.messages.find_one({"id": message_id, "sender_id": user["id"]}, {"_id": 0})
    if not msg:
        raise HTTPException(404, "Message not found or not yours")
    await db.messages.delete_one({"id": message_id})
    await db.reactions.delete_many({"message_id": message_id})
    await db.thread_replies.delete_many({"parent_message_id": message_id})
    conv = await db.conversations.find_one({"id": msg["conversation_id"]}, {"_id": 0})
    if conv:
        for pid in conv["participants"]:
            await manager.send_personal(pid, {"type": "message_deleted", "message_id": message_id})
    return {"message": "Deleted"}

@api_router.put("/channel-messages/{message_id}")
async def edit_channel_message(message_id: str, data: MessageEdit, request: Request):
    user = await get_current_user(request)
    msg = await db.channel_messages.find_one({"id": message_id, "sender_id": user["id"]}, {"_id": 0})
    if not msg:
        raise HTTPException(404, "Message not found or not yours")
    encrypted = encrypt_text(data.content)
    await db.channel_messages.update_one({"id": message_id}, {"$set": {"content_encrypted": encrypted, "edited": True}})
    await manager.broadcast_channel(msg["channel_id"], {"type": "message_edited", "message_id": message_id, "content": data.content, "edited": True})
    return {"message": "Edited"}

@api_router.delete("/channel-messages/{message_id}")
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
@api_router.get("/channels/{channel_id}/voice-participants")
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
@api_router.get("/system/update-check")
async def check_for_updates(request: Request):
    return {
        "current_version": "1.0.0",
        "latest_version": "1.0.0",
        "update_available": False,
        "release_url": "https://github.com/shield/shield/releases",
        "changelog": "Initial release with encrypted messaging, servers, channels, voice/video, and share drives."
    }

# ─── GIF SEARCH (GIPHY PROXY) ───
import httpx

@api_router.get("/gifs/trending")
async def gif_trending(request: Request, limit: int = 20, offset: int = 0):
    await get_current_user(request)
    giphy_key = os.environ.get("GIPHY_API_KEY", "")
    if not giphy_key:
        raise HTTPException(503, "GIF service not configured")
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "https://api.giphy.com/v1/gifs/trending",
            params={"api_key": giphy_key, "limit": min(limit, 50), "offset": offset, "rating": "pg-13"},
            timeout=10
        )
        if resp.status_code != 200:
            raise HTTPException(502, "GIF service error")
        data = resp.json()
    return {"gifs": [_format_gif(g) for g in data.get("data", [])], "pagination": data.get("pagination", {})}

@api_router.get("/gifs/search")
async def gif_search(request: Request, q: str, limit: int = 20, offset: int = 0):
    await get_current_user(request)
    giphy_key = os.environ.get("GIPHY_API_KEY", "")
    if not giphy_key:
        raise HTTPException(503, "GIF service not configured")
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "https://api.giphy.com/v1/gifs/search",
            params={"api_key": giphy_key, "q": q, "limit": min(limit, 50), "offset": offset, "rating": "pg-13"},
            timeout=10
        )
        if resp.status_code != 200:
            raise HTTPException(502, "GIF service error")
        data = resp.json()
    return {"gifs": [_format_gif(g) for g in data.get("data", [])], "pagination": data.get("pagination", {})}

def _format_gif(g):
    images = g.get("images", {})
    return {
        "id": g.get("id"),
        "title": g.get("title", ""),
        "url": images.get("original", {}).get("url", ""),
        "preview": images.get("fixed_height_small", {}).get("url", "") or images.get("preview_gif", {}).get("url", ""),
        "width": images.get("fixed_height_small", {}).get("width", "200"),
        "height": images.get("fixed_height_small", {}).get("height", "150"),
        "original_width": images.get("original", {}).get("width", "480"),
        "original_height": images.get("original", {}).get("height", "360"),
    }

# ─── PASSKEY / WEBAUTHN ───
from webauthn import generate_registration_options, verify_registration_response, generate_authentication_options, verify_authentication_response
from webauthn.helpers.structs import AuthenticatorSelectionCriteria, UserVerificationRequirement, ResidentKeyRequirement, PublicKeyCredentialDescriptor
from webauthn.helpers import bytes_to_base64url, base64url_to_bytes

WEBAUTHN_RP_ID = os.environ.get("WEBAUTHN_RP_ID", "localhost")
WEBAUTHN_RP_NAME = "Shield"
WEBAUTHN_ORIGIN = os.environ.get("WEBAUTHN_ORIGIN", "http://localhost:3000")

@api_router.post("/auth/passkey/register/begin")
async def begin_passkey_registration(request: Request):
    user = await get_current_user(request)
    existing_creds = await db.passkey_credentials.find({"user_id": user["id"]}, {"_id": 0}).to_list(20)
    exclude = []
    for cred in existing_creds:
        exclude.append(PublicKeyCredentialDescriptor(id=base64url_to_bytes(cred["credential_id"])))

    options = generate_registration_options(
        rp_id=WEBAUTHN_RP_ID,
        rp_name=WEBAUTHN_RP_NAME,
        user_id=user["id"].encode(),
        user_name=user["username"],
        user_display_name=user.get("display_name", user["username"]),
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.PREFERRED,
            user_verification=UserVerificationRequirement.PREFERRED,
        ),
        exclude_credentials=exclude,
        timeout=60000,
    )
    challenge_b64 = bytes_to_base64url(options.challenge)
    await db.passkey_challenges.insert_one({
        "user_id": user["id"],
        "challenge": challenge_b64,
        "type": "registration",
        "created_at": datetime.now(timezone.utc).isoformat()
    })
    return {
        "challenge": challenge_b64,
        "rp": {"id": options.rp.id, "name": options.rp.name},
        "user": {"id": bytes_to_base64url(options.user.id), "name": options.user.name, "displayName": options.user.display_name},
        "pubKeyCredParams": [{"type": "public-key", "alg": p.alg} for p in options.pub_key_cred_params],
        "timeout": options.timeout,
        "attestation": options.attestation,
        "excludeCredentials": [{"type": "public-key", "id": bytes_to_base64url(e.id)} for e in exclude],
        "authenticatorSelection": {"residentKey": "preferred", "userVerification": "preferred"}
    }

@api_router.post("/auth/passkey/register/complete")
async def complete_passkey_registration(request: Request):
    user = await get_current_user(request)
    body = await request.json()
    challenge_doc = await db.passkey_challenges.find_one({"user_id": user["id"], "type": "registration"}, {"_id": 0})
    if not challenge_doc:
        raise HTTPException(400, "No registration challenge found")
    await db.passkey_challenges.delete_many({"user_id": user["id"], "type": "registration"})

    try:
        verification = verify_registration_response(
            credential=body["credential"],
            expected_challenge=base64url_to_bytes(challenge_doc["challenge"]),
            expected_origin=WEBAUTHN_ORIGIN,
            expected_rp_id=WEBAUTHN_RP_ID,
        )
    except Exception as e:
        raise HTTPException(400, f"Verification failed: {str(e)}")

    cred_id_b64 = bytes_to_base64url(verification.credential_id)
    pub_key_b64 = bytes_to_base64url(verification.credential_public_key)
    await db.passkey_credentials.insert_one({
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "credential_id": cred_id_b64,
        "public_key": pub_key_b64,
        "sign_count": verification.sign_count,
        "name": body.get("name", "Passkey"),
        "created_at": datetime.now(timezone.utc).isoformat()
    })
    return {"message": "Passkey registered successfully"}

@api_router.post("/auth/passkey/authenticate/begin")
async def begin_passkey_auth(request: Request):
    body = await request.json()
    username = body.get("username")
    user = await db.users.find_one({"username_lower": username.lower()}, {"_id": 0}) if username else None
    creds = []
    allow_creds = []
    if user:
        creds = await db.passkey_credentials.find({"user_id": user["id"]}, {"_id": 0}).to_list(20)
        allow_creds = [PublicKeyCredentialDescriptor(id=base64url_to_bytes(c["credential_id"])) for c in creds]
    if user and not creds:
        raise HTTPException(404, "No passkeys registered for this user")

    options = generate_authentication_options(
        rp_id=WEBAUTHN_RP_ID,
        allow_credentials=allow_creds,
        user_verification=UserVerificationRequirement.PREFERRED,
        timeout=120000,
    )
    challenge_b64 = bytes_to_base64url(options.challenge)
    if user:
        await db.passkey_challenges.insert_one({
            "user_id": user["id"],
            "challenge": challenge_b64,
            "type": "authentication",
            "created_at": datetime.now(timezone.utc).isoformat()
        })
    return {
        "challenge": challenge_b64,
        "timeout": options.timeout,
        "rpId": options.rp_id,
        "userVerification": "preferred",
        "allowCredentials": [{"type": "public-key", "id": bytes_to_base64url(c.id), "transports": ["internal"]} for c in allow_creds]
    }

@api_router.post("/auth/passkey/authenticate/complete")
async def complete_passkey_auth(request: Request, response: Response):
    body = await request.json()
    username = body.get("username")
    credential = body.get("credential")
    user = await db.users.find_one({"username_lower": username.lower()}, {"_id": 0})
    if not user:
        raise HTTPException(401, "Invalid credentials")

    challenge_doc = await db.passkey_challenges.find_one({"user_id": user["id"], "type": "authentication"}, {"_id": 0})
    if not challenge_doc:
        raise HTTPException(400, "No authentication challenge found")
    await db.passkey_challenges.delete_many({"user_id": user["id"], "type": "authentication"})

    cred_id = credential.get("id")
    stored_cred = await db.passkey_credentials.find_one({"user_id": user["id"], "credential_id": cred_id}, {"_id": 0})
    if not stored_cred:
        raise HTTPException(401, "Credential not found")

    try:
        verification = verify_authentication_response(
            credential=credential,
            expected_challenge=base64url_to_bytes(challenge_doc["challenge"]),
            expected_origin=WEBAUTHN_ORIGIN,
            expected_rp_id=WEBAUTHN_RP_ID,
            credential_public_key=base64url_to_bytes(stored_cred["public_key"]),
            credential_current_sign_count=stored_cred["sign_count"],
        )
    except Exception as e:
        raise HTTPException(401, f"Authentication failed: {str(e)}")

    await db.passkey_credentials.update_one(
        {"user_id": user["id"], "credential_id": cred_id},
        {"$set": {"sign_count": verification.new_sign_count}}
    )
    await db.users.update_one({"id": user["id"]}, {"$set": {"status": "online", "last_active": datetime.now(timezone.utc).isoformat()}})
    access = create_access_token(user["id"], user["username"])
    refresh = create_refresh_token(user["id"])
    set_auth_cookies(response, access, refresh)
    return {"user": sanitize_user(user), "access_token": access}

@api_router.get("/auth/passkeys")
async def list_passkeys(request: Request):
    user = await get_current_user(request)
    creds = await db.passkey_credentials.find({"user_id": user["id"]}, {"_id": 0}).to_list(20)
    return creds

@api_router.delete("/auth/passkeys/{credential_id}")
async def delete_passkey(credential_id: str, request: Request):
    user = await get_current_user(request)
    await db.passkey_credentials.delete_one({"user_id": user["id"], "credential_id": credential_id})
    return {"message": "Passkey removed"}

@api_router.post("/servers/{server_id}/roles")
async def create_role(server_id: str, data: RoleCreate, request: Request):
    user = await get_current_user(request)
    server = await db.servers.find_one({"id": server_id}, {"_id": 0})
    if not server or server["owner_id"] != user["id"]:
        raise HTTPException(403, "No permission")
    role_id = str(uuid.uuid4())
    role = {"id": role_id, "name": data.name, "color": data.color or "#99AAB5", "permissions": data.permissions, "position": len(server.get("roles", []))}
    await db.servers.update_one({"id": server_id}, {"$push": {"roles": role}})
    return role

@api_router.put("/servers/{server_id}/roles/{role_id}")
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

@api_router.delete("/servers/{server_id}/roles/{role_id}")
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

@api_router.get("/permissions/map")
async def get_permissions_map(request: Request):
    await get_current_user(request)
    return {"permissions": Permissions.PERMISSION_MAP, "default": Permissions.DEFAULT}

@api_router.post("/servers/{server_id}/members/{user_id}/roles/{role_id}")
async def assign_role(server_id: str, user_id: str, role_id: str, request: Request):
    user = await get_current_user(request)
    server = await db.servers.find_one({"id": server_id}, {"_id": 0})
    if not server or server["owner_id"] != user["id"]:
        raise HTTPException(403, "No permission")
    await db.server_members.update_one(
        {"server_id": server_id, "user_id": user_id},
        {"$addToSet": {"roles": role_id}}
    )
    return {"message": "Role assigned"}

@api_router.delete("/servers/{server_id}/members/{user_id}/roles/{role_id}")
async def remove_role(server_id: str, user_id: str, role_id: str, request: Request):
    user = await get_current_user(request)
    server = await db.servers.find_one({"id": server_id}, {"_id": 0})
    if not server or server["owner_id"] != user["id"]:
        raise HTTPException(403, "No permission")
    await db.server_members.update_one(
        {"server_id": server_id, "user_id": user_id},
        {"$pull": {"roles": role_id}}
    )
    return {"message": "Role removed"}

# ─── MEMBER MANAGEMENT ───
@api_router.post("/servers/{server_id}/kick/{user_id}")
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

@api_router.post("/servers/{server_id}/ban/{user_id}")
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

# ─── FILE UPLOAD ───
@api_router.post("/upload")
async def upload_file(request: Request, file: UploadFile = File(...), context: str = Query("message")):
    user = await get_current_user(request)
    data = await file.read()
    size = len(data)

    full_user = await db.users.find_one({"id": user["id"]}, {"_id": 0})
    if full_user["storage_used_bytes"] + size > full_user["storage_limit_bytes"]:
        raise HTTPException(400, "Storage limit exceeded")

    path = generate_storage_path(user["id"], file.filename, context)
    result = put_object(path, data, file.content_type or "application/octet-stream")

    file_doc = {
        "id": str(uuid.uuid4()),
        "storage_path": result["path"],
        "original_filename": file.filename,
        "content_type": file.content_type,
        "size": size,
        "uploader_id": user["id"],
        "context": context,
        "is_deleted": False,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.files.insert_one(file_doc)
    await db.users.update_one({"id": user["id"]}, {"$inc": {"storage_used_bytes": size}})
    file_doc.pop("_id", None)
    return file_doc

@api_router.get("/files/{file_id}/download")
async def download_file(file_id: str, request: Request):
    await get_current_user(request)
    record = await db.files.find_one({"id": file_id, "is_deleted": False}, {"_id": 0})
    if not record:
        # Also check drive files
        record = await db.drive_files.find_one({"id": file_id, "is_deleted": False}, {"_id": 0})
    if not record:
        raise HTTPException(404, "File not found")
    if record.get("is_text_file"):
        content = decrypt_text(record.get("content_encrypted", ""))
        return Response(content=content.encode("utf-8"), media_type="text/plain", headers={"Content-Disposition": f"attachment; filename=\"{record['original_filename']}\""})
    data, content_type = get_object(record["storage_path"])
    return Response(content=data, media_type=record.get("content_type", content_type))

# ─── SHARE DRIVE ───
@api_router.post("/servers/{server_id}/drive/upload")
async def upload_drive_file(server_id: str, request: Request, file: UploadFile = File(...)):
    user = await get_current_user(request)
    member = await db.server_members.find_one({"server_id": server_id, "user_id": user["id"]})
    if not member:
        raise HTTPException(403, "Not a member")
    server = await db.servers.find_one({"id": server_id}, {"_id": 0})
    if not server:
        raise HTTPException(404, "Server not found")

    data = await file.read()
    size = len(data)
    if server["storage_used_bytes"] + size > server["storage_limit_bytes"]:
        raise HTTPException(400, "Server storage limit exceeded")

    path = generate_storage_path(server_id, file.filename, "drive")
    result = put_object(path, data, file.content_type or "application/octet-stream")

    file_doc = {
        "id": str(uuid.uuid4()),
        "server_id": server_id,
        "storage_path": result["path"],
        "original_filename": file.filename,
        "content_type": file.content_type,
        "size": size,
        "uploader_id": user["id"],
        "uploader_username": user["username"],
        "is_deleted": False,
        "is_text_file": False,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.drive_files.insert_one(file_doc)
    await db.servers.update_one({"id": server_id}, {"$inc": {"storage_used_bytes": size}})
    file_doc.pop("_id", None)
    return file_doc

@api_router.get("/servers/{server_id}/drive")
async def list_drive_files(server_id: str, request: Request):
    user = await get_current_user(request)
    member = await db.server_members.find_one({"server_id": server_id, "user_id": user["id"]})
    if not member:
        raise HTTPException(403, "Not a member")
    files = await db.drive_files.find({"server_id": server_id, "is_deleted": False}, {"_id": 0}).sort("created_at", -1).to_list(1000)
    return files

@api_router.delete("/servers/{server_id}/drive/{file_id}")
async def delete_drive_file(server_id: str, file_id: str, request: Request):
    user = await get_current_user(request)
    member = await db.server_members.find_one({"server_id": server_id, "user_id": user["id"]})
    if not member:
        raise HTTPException(403, "Not a member")
    file_doc = await db.drive_files.find_one({"id": file_id, "server_id": server_id, "is_deleted": False}, {"_id": 0})
    if not file_doc:
        raise HTTPException(404, "File not found")
    await db.drive_files.update_one({"id": file_id}, {"$set": {"is_deleted": True}})
    await db.servers.update_one({"id": server_id}, {"$inc": {"storage_used_bytes": -file_doc["size"]}})
    return {"message": "File deleted"}

# ─── SHARE DRIVE TEXT FILES ───
from pydantic import BaseModel as PydanticBaseModel

class TextFileCreate(PydanticBaseModel):
    filename: str
    content: str

class TextFileUpdate(PydanticBaseModel):
    content: str

@api_router.post("/servers/{server_id}/drive/text")
async def create_text_file(server_id: str, data: TextFileCreate, request: Request):
    user = await get_current_user(request)
    member = await db.server_members.find_one({"server_id": server_id, "user_id": user["id"]})
    if not member:
        raise HTTPException(403, "Not a member")
    server = await db.servers.find_one({"id": server_id}, {"_id": 0})
    if not server:
        raise HTTPException(404, "Server not found")
    content_bytes = data.content.encode("utf-8")
    size = len(content_bytes)
    if server["storage_used_bytes"] + size > server["storage_limit_bytes"]:
        raise HTTPException(400, "Server storage limit exceeded")
    encrypted_content = encrypt_text(data.content)
    file_id = str(uuid.uuid4())
    file_doc = {
        "id": file_id,
        "server_id": server_id,
        "original_filename": data.filename if data.filename.endswith(".txt") else data.filename + ".txt",
        "content_type": "text/plain",
        "content_encrypted": encrypted_content,
        "size": size,
        "uploader_id": user["id"],
        "uploader_username": user["username"],
        "is_deleted": False,
        "is_text_file": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    await db.drive_files.insert_one(file_doc)
    await db.servers.update_one({"id": server_id}, {"$inc": {"storage_used_bytes": size}})
    file_doc.pop("_id", None)
    file_doc["content"] = data.content
    file_doc.pop("content_encrypted", None)
    return file_doc

@api_router.get("/servers/{server_id}/drive/{file_id}/content")
async def get_text_file_content(server_id: str, file_id: str, request: Request):
    user = await get_current_user(request)
    member = await db.server_members.find_one({"server_id": server_id, "user_id": user["id"]})
    if not member:
        raise HTTPException(403, "Not a member")
    f = await db.drive_files.find_one({"id": file_id, "server_id": server_id, "is_deleted": False, "is_text_file": True}, {"_id": 0})
    if not f:
        raise HTTPException(404, "File not found")
    content = decrypt_text(f.get("content_encrypted", ""))
    return {"id": f["id"], "filename": f["original_filename"], "content": content, "updated_at": f.get("updated_at")}

@api_router.put("/servers/{server_id}/drive/{file_id}/content")
async def update_text_file(server_id: str, file_id: str, data: TextFileUpdate, request: Request):
    user = await get_current_user(request)
    member = await db.server_members.find_one({"server_id": server_id, "user_id": user["id"]})
    if not member:
        raise HTTPException(403, "Not a member")
    f = await db.drive_files.find_one({"id": file_id, "server_id": server_id, "is_deleted": False, "is_text_file": True}, {"_id": 0})
    if not f:
        raise HTTPException(404, "File not found")
    old_size = f["size"]
    new_size = len(data.content.encode("utf-8"))
    encrypted = encrypt_text(data.content)
    await db.drive_files.update_one({"id": file_id}, {"$set": {"content_encrypted": encrypted, "size": new_size, "updated_at": datetime.now(timezone.utc).isoformat()}})
    await db.servers.update_one({"id": server_id}, {"$inc": {"storage_used_bytes": new_size - old_size}})
    return {"message": "File updated"}

@api_router.get("/servers/{server_id}/drive/{file_id}/link")
async def get_drive_file_link(server_id: str, file_id: str, request: Request):
    user = await get_current_user(request)
    member = await db.server_members.find_one({"server_id": server_id, "user_id": user["id"]})
    if not member:
        raise HTTPException(403, "Not a member")
    f = await db.drive_files.find_one({"id": file_id, "server_id": server_id, "is_deleted": False}, {"_id": 0})
    if not f:
        raise HTTPException(404, "File not found")
    return {"link": f"/api/files/{file_id}/download", "filename": f["original_filename"]}

# ─── CUSTOM EMOJIS / STICKERS ───
@api_router.post("/emojis/upload")
async def upload_emoji(request: Request, file: UploadFile = File(...), name: str = Query(...), emoji_type: str = Query("emoji")):
    user = await get_current_user(request)
    data = await file.read()
    size = len(data)
    if size > 512 * 1024:
        raise HTTPException(400, "Emoji/sticker must be under 512KB")
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(400, "Must be an image file")
    path = generate_storage_path(user["id"], file.filename, "emojis")
    result = put_object(path, data, file.content_type)
    emoji_id = str(uuid.uuid4())
    doc = {
        "id": emoji_id,
        "name": name.strip().lower().replace(" ", "_"),
        "type": emoji_type,
        "storage_path": result["path"],
        "content_type": file.content_type,
        "size": size,
        "owner_id": user["id"],
        "owner_username": user["username"],
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.custom_emojis.insert_one(doc)
    doc.pop("_id", None)
    return doc

@api_router.get("/emojis/mine")
async def get_my_emojis(request: Request):
    user = await get_current_user(request)
    own = await db.custom_emojis.find({"owner_id": user["id"]}, {"_id": 0}).to_list(200)
    saved = await db.saved_emojis.find({"user_id": user["id"]}, {"_id": 0}).to_list(200)
    saved_ids = [s["emoji_id"] for s in saved]
    saved_emojis = []
    if saved_ids:
        saved_emojis = await db.custom_emojis.find({"id": {"$in": saved_ids}}, {"_id": 0}).to_list(200)
    return {"owned": own, "saved": saved_emojis}

@api_router.get("/emojis/{emoji_id}/image")
async def get_emoji_image(emoji_id: str):
    doc = await db.custom_emojis.find_one({"id": emoji_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Emoji not found")
    data, ct = get_object(doc["storage_path"])
    return Response(content=data, media_type=doc.get("content_type", ct))

@api_router.post("/emojis/{emoji_id}/save")
async def save_emoji(emoji_id: str, request: Request):
    user = await get_current_user(request)
    doc = await db.custom_emojis.find_one({"id": emoji_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Emoji not found")
    await db.saved_emojis.update_one(
        {"user_id": user["id"], "emoji_id": emoji_id},
        {"$setOnInsert": {"id": str(uuid.uuid4()), "user_id": user["id"], "emoji_id": emoji_id, "created_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True
    )
    return {"message": "Emoji saved to your library"}

@api_router.delete("/emojis/{emoji_id}/save")
async def unsave_emoji(emoji_id: str, request: Request):
    user = await get_current_user(request)
    await db.saved_emojis.delete_one({"user_id": user["id"], "emoji_id": emoji_id})
    return {"message": "Emoji removed from library"}

@api_router.delete("/emojis/{emoji_id}")
async def delete_emoji(emoji_id: str, request: Request):
    user = await get_current_user(request)
    doc = await db.custom_emojis.find_one({"id": emoji_id, "owner_id": user["id"]}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Emoji not found or not yours")
    await db.custom_emojis.delete_one({"id": emoji_id})
    await db.saved_emojis.delete_many({"emoji_id": emoji_id})
    return {"message": "Emoji deleted"}

# ─── STORAGE REQUESTS ───
@api_router.post("/servers/{server_id}/storage-request")
async def request_storage(server_id: str, request: Request):
    user = await get_current_user(request)
    server = await db.servers.find_one({"id": server_id}, {"_id": 0})
    if not server or server["owner_id"] != user["id"]:
        raise HTTPException(403, "Only server owner can request storage")
    body = await request.json()
    req_id = str(uuid.uuid4())
    req_doc = {
        "id": req_id,
        "server_id": server_id,
        "server_name": server["name"],
        "requester_id": user["id"],
        "requester_username": user["username"],
        "requested_gb": body.get("requested_gb", 50),
        "current_limit_gb": server["storage_limit_bytes"] / (1024**3),
        "reason": body.get("reason", ""),
        "status": "pending",
        "approved_gb": None,
        "admin_note": None,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.storage_requests.insert_one(req_doc)
    req_doc.pop("_id", None)
    return req_doc

@api_router.get("/servers/{server_id}/storage-request")
async def get_storage_requests(server_id: str, request: Request):
    user = await get_current_user(request)
    server = await db.servers.find_one({"id": server_id}, {"_id": 0})
    if not server or server["owner_id"] != user["id"]:
        raise HTTPException(403, "Not the server owner")
    reqs = await db.storage_requests.find({"server_id": server_id}, {"_id": 0}).sort("created_at", -1).to_list(50)
    return reqs

@api_router.get("/admin/storage-requests")
async def admin_list_storage_requests(request: Request):
    user = await get_current_user(request)
    if user.get("role") != "admin":
        raise HTTPException(403, "Admin access required")
    reqs = await db.storage_requests.find({"status": "pending"}, {"_id": 0}).sort("created_at", -1).to_list(100)
    return reqs

@api_router.post("/admin/storage-requests/{request_id}/approve")
async def admin_approve_storage(request_id: str, request: Request):
    user = await get_current_user(request)
    if user.get("role") != "admin":
        raise HTTPException(403, "Admin access required")
    body = await request.json()
    approved_gb = body.get("approved_gb")
    req_doc = await db.storage_requests.find_one({"id": request_id, "status": "pending"}, {"_id": 0})
    if not req_doc:
        raise HTTPException(404, "Request not found")
    new_limit = int(approved_gb * 1024**3)
    await db.servers.update_one({"id": req_doc["server_id"]}, {"$set": {"storage_limit_bytes": new_limit, "admin_approved_limit_bytes": new_limit}})
    await db.storage_requests.update_one({"id": request_id}, {"$set": {"status": "approved", "approved_gb": approved_gb, "admin_note": body.get("note", "")}})
    return {"message": "Storage request approved"}

@api_router.post("/admin/storage-requests/{request_id}/deny")
async def admin_deny_storage(request_id: str, request: Request):
    user = await get_current_user(request)
    if user.get("role") != "admin":
        raise HTTPException(403, "Admin access required")
    body = await request.json()
    await db.storage_requests.update_one({"id": request_id}, {"$set": {"status": "denied", "admin_note": body.get("note", "")}})
    return {"message": "Storage request denied"}

# ─── ADMIN ROUTES ───
@api_router.get("/admin/stats")
async def get_admin_stats(request: Request):
    user = await get_current_user(request)
    if user.get("role") != "admin":
        raise HTTPException(403, "Admin access required")

    total_users = await db.users.count_documents({})
    online_users = len(manager.get_online_users())
    total_servers = await db.servers.count_documents({})
    total_messages = await db.messages.count_documents({}) + await db.channel_messages.count_documents({})
    total_files = await db.files.count_documents({"is_deleted": False})
    total_drive_files = await db.drive_files.count_documents({"is_deleted": False})

    pipeline = [{"$match": {"is_deleted": False}}, {"$group": {"_id": None, "total": {"$sum": "$size"}}}]
    msg_storage = await db.files.aggregate(pipeline).to_list(1)
    drive_storage = await db.drive_files.aggregate(pipeline).to_list(1)

    voice_channels_active = sum(1 for v in manager.voice_participants.values() if len(v) > 0)

    now = datetime.now(timezone.utc)
    day_ago = (now - timedelta(days=1)).isoformat()
    week_ago = (now - timedelta(weeks=1)).isoformat()
    month_ago = (now - timedelta(days=30)).isoformat()

    msgs_today = await db.messages.count_documents({"created_at": {"$gte": day_ago}}) + await db.channel_messages.count_documents({"created_at": {"$gte": day_ago}})
    msgs_week = await db.messages.count_documents({"created_at": {"$gte": week_ago}}) + await db.channel_messages.count_documents({"created_at": {"$gte": week_ago}})
    msgs_month = await db.messages.count_documents({"created_at": {"$gte": month_ago}}) + await db.channel_messages.count_documents({"created_at": {"$gte": month_ago}})

    return {
        "users_registered": total_users,
        "users_online": online_users,
        "voice_chats_active": voice_channels_active,
        "total_servers": total_servers,
        "total_messages": total_messages,
        "messages_today": msgs_today,
        "messages_this_week": msgs_week,
        "messages_this_month": msgs_month,
        "total_files": total_files,
        "total_drive_files": total_drive_files,
        "message_attachment_storage_bytes": msg_storage[0]["total"] if msg_storage else 0,
        "drive_storage_bytes": drive_storage[0]["total"] if drive_storage else 0,
        "relay_streams": []
    }

@api_router.get("/admin/servers")
async def admin_list_servers(request: Request):
    user = await get_current_user(request)
    if user.get("role") != "admin":
        raise HTTPException(403, "Admin access required")
    servers = await db.servers.find({}, {"_id": 0}).to_list(1000)
    for s in servers:
        s["member_count"] = await db.server_members.count_documents({"server_id": s["id"]})
        drive_pipe = [{"$match": {"server_id": s["id"], "is_deleted": False}}, {"$group": {"_id": None, "total": {"$sum": "$size"}}}]
        drive_s = await db.drive_files.aggregate(drive_pipe).to_list(1)
        s["drive_storage_used"] = drive_s[0]["total"] if drive_s else 0
    return servers

# ─── UPDATE SYSTEM ───
DEFAULT_REPO_URL = "https://github.com/Tech-Person/shield"
INSTALL_DIR = os.environ.get("SHIELD_DIR", "/opt/shield")
update_lock = asyncio.Lock()

@api_router.get("/admin/update/config")
async def get_update_config(request: Request):
    user = await get_current_user(request)
    if user.get("role") != "admin":
        raise HTTPException(403, "Admin access required")
    config = await db.update_config.find_one({"key": "update"}, {"_id": 0})
    if not config:
        config = {"key": "update", "repo_url": DEFAULT_REPO_URL, "last_check": None, "last_update": None}
        await db.update_config.insert_one(config)
    return {
        "repo_url": config.get("repo_url", DEFAULT_REPO_URL),
        "last_check": config.get("last_check"),
        "last_update": config.get("last_update"),
        "last_update_status": config.get("last_update_status"),
        "current_commit": config.get("current_commit"),
        "current_commit_message": config.get("current_commit_message"),
    }

@api_router.put("/admin/update/config")
async def set_update_config(request: Request):
    user = await get_current_user(request)
    if user.get("role") != "admin":
        raise HTTPException(403, "Admin access required")
    body = await request.json()
    repo_url = body.get("repo_url", "").strip()
    if not repo_url:
        raise HTTPException(400, "repo_url required")
    await db.update_config.update_one(
        {"key": "update"},
        {"$set": {"repo_url": repo_url}},
        upsert=True
    )
    return {"message": "Config updated"}

@api_router.post("/admin/update/check")
async def check_for_updates(request: Request):
    user = await get_current_user(request)
    if user.get("role") != "admin":
        raise HTTPException(403, "Admin access required")

    config = await db.update_config.find_one({"key": "update"}, {"_id": 0})
    repo_url = (config or {}).get("repo_url", DEFAULT_REPO_URL)

    try:
        import httpx
        api_url = repo_url.replace("github.com", "api.github.com/repos") + "/commits?per_page=5"
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(api_url, headers={"Accept": "application/vnd.github.v3+json"})
            resp.raise_for_status()
            commits = resp.json()

        # Get local commit if git repo exists
        local_commit = None
        local_message = None
        try:
            result = subprocess.run(["git", "log", "-1", "--format=%H|||%s"], capture_output=True, text=True, cwd=INSTALL_DIR)
            if result.returncode == 0 and "|||" in result.stdout.strip():
                parts = result.stdout.strip().split("|||", 1)
                local_commit = parts[0][:7]
                local_message = parts[1]
        except Exception:
            pass

        remote_commits = []
        for c in commits[:5]:
            remote_commits.append({
                "sha": c["sha"][:7],
                "message": c["commit"]["message"].split("\n")[0][:80],
                "author": c["commit"]["author"]["name"],
                "date": c["commit"]["author"]["date"],
            })

        remote_latest = remote_commits[0]["sha"] if remote_commits else None
        has_updates = local_commit != remote_latest if local_commit and remote_latest else True

        now = datetime.now(timezone.utc).isoformat()
        await db.update_config.update_one(
            {"key": "update"},
            {"$set": {
                "last_check": now,
                "current_commit": local_commit,
                "current_commit_message": local_message,
                "remote_latest": remote_latest,
            }},
            upsert=True
        )

        return {
            "has_updates": has_updates,
            "local_commit": local_commit,
            "local_message": local_message,
            "remote_latest": remote_latest,
            "remote_commits": remote_commits,
            "checked_at": now,
        }
    except Exception as e:
        raise HTTPException(500, f"Failed to check for updates: {str(e)}")

@api_router.post("/admin/update/apply")
async def apply_update(request: Request):
    user = await get_current_user(request)
    if user.get("role") != "admin":
        raise HTTPException(403, "Admin access required")

    if update_lock.locked():
        raise HTTPException(409, "An update is already in progress")

    config = await db.update_config.find_one({"key": "update"}, {"_id": 0})
    repo_url = (config or {}).get("repo_url", DEFAULT_REPO_URL)

    # Mark update as in-progress
    now = datetime.now(timezone.utc).isoformat()
    await db.update_config.update_one(
        {"key": "update"},
        {"$set": {"last_update_status": "in_progress", "last_update": now}},
        upsert=True
    )

    # Run update in background
    asyncio.create_task(_run_update(repo_url))
    return {"message": "Update started", "status": "in_progress"}

@api_router.get("/admin/update/status")
async def get_update_status(request: Request):
    user = await get_current_user(request)
    if user.get("role") != "admin":
        raise HTTPException(403, "Admin access required")
    config = await db.update_config.find_one({"key": "update"}, {"_id": 0})
    return {
        "status": (config or {}).get("last_update_status", "idle"),
        "log": (config or {}).get("update_log", ""),
        "last_update": (config or {}).get("last_update"),
        "current_commit": (config or {}).get("current_commit"),
    }

async def _run_update(repo_url: str):
    async with update_lock:
        log_lines = []
        def log(msg):
            log_lines.append(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] {msg}")

        try:
            log("Starting update...")

            # Step 1: Check if install dir is a git repo
            is_git = os.path.isdir(os.path.join(INSTALL_DIR, ".git"))

            if is_git:
                log("Git repo found. Pulling latest changes...")

                # Backup .env files before git operations
                env_backups = {}
                for env_path in [
                    os.path.join(INSTALL_DIR, "backend", ".env"),
                    os.path.join(INSTALL_DIR, "frontend", ".env"),
                ]:
                    if os.path.exists(env_path):
                        with open(env_path) as f:
                            env_backups[env_path] = f.read()

                proc = await asyncio.create_subprocess_exec(
                    "git", "fetch", "--all",
                    cwd=INSTALL_DIR, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await proc.communicate()
                log(f"git fetch: {stdout.decode().strip() or stderr.decode().strip() or 'ok'}")

                proc = await asyncio.create_subprocess_exec(
                    "git", "reset", "--hard", "origin/main",
                    cwd=INSTALL_DIR, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await proc.communicate()
                if proc.returncode != 0:
                    proc = await asyncio.create_subprocess_exec(
                        "git", "reset", "--hard", "origin/master",
                        cwd=INSTALL_DIR, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                    )
                    stdout, stderr = await proc.communicate()
                log(f"git reset: {stdout.decode().strip() or stderr.decode().strip() or 'ok'}")

                # Restore .env files
                for env_path, content in env_backups.items():
                    with open(env_path, "w") as f:
                        f.write(content)
                    log(f"Restored {env_path}")
            else:
                log("Not a git repo. Initializing from remote...")
                # Clone to temp, then move files
                tmp_dir = f"/tmp/shield-update-{uuid.uuid4().hex[:8]}"
                proc = await asyncio.create_subprocess_exec(
                    "git", "clone", "--depth=1", repo_url, tmp_dir,
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await proc.communicate()
                if proc.returncode != 0:
                    log(f"git clone failed: {stderr.decode()}")
                    raise Exception("git clone failed")
                log("Clone complete. Syncing files...")

                # Preserve .env files and venv
                for item in ["backend", "frontend", "deploy"]:
                    src = os.path.join(tmp_dir, item)
                    dst = os.path.join(INSTALL_DIR, item)
                    if os.path.isdir(src):
                        # Backup .env
                        env_backup = None
                        env_path = os.path.join(dst, ".env")
                        if os.path.exists(env_path):
                            with open(env_path) as f:
                                env_backup = f.read()
                        # Backup venv path
                        venv_path = os.path.join(dst, "venv")
                        has_venv = os.path.isdir(venv_path)

                        # Sync (exclude venv, node_modules, .env, build)
                        proc = await asyncio.create_subprocess_exec(
                            "rsync", "-a", "--delete",
                            "--exclude=venv", "--exclude=node_modules",
                            "--exclude=.env", "--exclude=build",
                            f"{src}/", f"{dst}/",
                            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                        )
                        await proc.communicate()
                        log(f"Synced {item}/")

                        # Restore .env
                        if env_backup:
                            with open(env_path, "w") as f:
                                f.write(env_backup)

                # Move .git so future updates use git pull
                proc = await asyncio.create_subprocess_exec(
                    "rsync", "-a", f"{tmp_dir}/.git/", f"{INSTALL_DIR}/.git/",
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                )
                await proc.communicate()

                # Cleanup
                proc = await asyncio.create_subprocess_exec("rm", "-rf", tmp_dir)
                await proc.communicate()
                log("Git initialized for future updates.")

            # Step 2: Update backend dependencies
            log("Installing backend dependencies...")
            venv_pip = os.path.join(INSTALL_DIR, "backend", "venv", "bin", "pip")
            req_file = os.path.join(INSTALL_DIR, "backend", "requirements.txt")
            if os.path.exists(venv_pip) and os.path.exists(req_file):
                proc = await asyncio.create_subprocess_exec(
                    venv_pip, "install", "-r", req_file,
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await proc.communicate()
                log(f"pip install: {'ok' if proc.returncode == 0 else stderr.decode()[:200]}")
            else:
                log("Skipping pip (no venv or requirements.txt)")

            # Step 3: Rebuild frontend
            log("Rebuilding frontend...")
            frontend_dir = os.path.join(INSTALL_DIR, "frontend")
            if os.path.exists(os.path.join(frontend_dir, "package.json")):
                proc = await asyncio.create_subprocess_exec(
                    "yarn", "install", "--frozen-lockfile",
                    cwd=frontend_dir, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await proc.communicate()
                log(f"yarn install: {'ok' if proc.returncode == 0 else 'failed (trying without lockfile)'}")
                if proc.returncode != 0:
                    proc = await asyncio.create_subprocess_exec(
                        "yarn", "install",
                        cwd=frontend_dir, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                    )
                    await proc.communicate()

                proc = await asyncio.create_subprocess_exec(
                    "yarn", "build",
                    cwd=frontend_dir, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await proc.communicate()
                log(f"yarn build: {'ok' if proc.returncode == 0 else stderr.decode()[:200]}")
            else:
                log("Skipping frontend (no package.json)")

            # Step 4: Restart backend service
            log("Restarting backend service...")
            proc = await asyncio.create_subprocess_exec(
                "systemctl", "restart", "shield-backend",
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            log(f"Service restart: {'ok' if proc.returncode == 0 else stderr.decode()[:200]}")

            # Step 5: Reload nginx
            log("Reloading nginx...")
            proc = await asyncio.create_subprocess_exec(
                "systemctl", "reload", "nginx",
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            await proc.communicate()

            # Get current commit
            current_commit = None
            current_message = None
            try:
                proc = await asyncio.create_subprocess_exec(
                    "git", "log", "-1", "--format=%H|||%s",
                    cwd=INSTALL_DIR, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                )
                stdout, _ = await proc.communicate()
                if "|||" in stdout.decode():
                    parts = stdout.decode().strip().split("|||", 1)
                    current_commit = parts[0][:7]
                    current_message = parts[1]
            except Exception:
                pass

            log("Update complete!")

            await db.update_config.update_one(
                {"key": "update"},
                {"$set": {
                    "last_update_status": "success",
                    "update_log": "\n".join(log_lines),
                    "current_commit": current_commit,
                    "current_commit_message": current_message,
                }},
                upsert=True
            )
        except Exception as e:
            log(f"Update failed: {str(e)}")
            await db.update_config.update_one(
                {"key": "update"},
                {"$set": {
                    "last_update_status": "failed",
                    "update_log": "\n".join(log_lines),
                }},
                upsert=True
            )

# ─── WEBSOCKET ───
@app.websocket("/ws/{token}")
async def websocket_endpoint(websocket: WebSocket, token: str):
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = payload["sub"]
    except jwt.InvalidTokenError:
        await websocket.close(code=4001)
        return

    await manager.connect(user_id, websocket)
    await db.users.update_one({"id": user_id}, {"$set": {"status": "online", "last_active": datetime.now(timezone.utc).isoformat()}})

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")

            if msg_type == "subscribe_channel":
                manager.subscribe_channel(user_id, data["channel_id"])
            elif msg_type == "unsubscribe_channel":
                manager.unsubscribe_channel(user_id, data["channel_id"])
            elif msg_type == "subscribe_dm":
                manager.subscribe_dm(user_id, data["conversation_id"])
            elif msg_type == "join_voice":
                manager.join_voice(user_id, data["channel_id"])
                participants = list(manager.get_voice_participants(data["channel_id"]))
                await manager.broadcast_channel(data["channel_id"], {
                    "type": "voice_state_update",
                    "channel_id": data["channel_id"],
                    "participants": participants,
                    "user_joined": user_id
                })
            elif msg_type == "leave_voice":
                manager.leave_voice(user_id, data["channel_id"])
                participants = list(manager.get_voice_participants(data["channel_id"]))
                await manager.broadcast_channel(data["channel_id"], {
                    "type": "voice_state_update",
                    "channel_id": data["channel_id"],
                    "participants": participants,
                    "user_left": user_id
                })
            elif msg_type == "webrtc_signal":
                await manager.send_personal(data["target_user_id"], {
                    "type": "webrtc_signal",
                    "signal": data["signal"],
                    "from_user_id": user_id
                })
            elif msg_type == "typing":
                target = data.get("conversation_id") or data.get("channel_id")
                if data.get("conversation_id"):
                    await manager.broadcast_dm(target, {"type": "typing", "user_id": user_id, "conversation_id": target}, exclude=user_id)
                else:
                    await manager.broadcast_channel(target, {"type": "typing", "user_id": user_id, "channel_id": target}, exclude=user_id)
            elif msg_type == "heartbeat":
                await db.users.update_one({"id": user_id}, {"$set": {"last_active": datetime.now(timezone.utc).isoformat()}})
                await websocket.send_json({"type": "heartbeat_ack"})

    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(user_id)
        await db.users.update_one({"id": user_id}, {"$set": {"last_active": datetime.now(timezone.utc).isoformat()}})

# ─── STARTUP ───
@app.on_event("startup")
async def startup():
    await db.users.create_index("email", unique=True)
    await db.users.create_index("username_lower", unique=True)
    await db.users.create_index("id", unique=True)
    await db.conversations.create_index("id", unique=True)
    await db.conversations.create_index("participants")
    await db.messages.create_index("conversation_id")
    await db.messages.create_index("created_at")
    await db.messages.create_index("id", unique=True)
    await db.servers.create_index("id", unique=True)
    await db.channels.create_index("id", unique=True)
    await db.channels.create_index("server_id")
    await db.channel_messages.create_index("channel_id")
    await db.channel_messages.create_index("created_at")
    await db.server_members.create_index([("server_id", 1), ("user_id", 1)], unique=True)
    await db.invites.create_index("code", unique=True)
    await db.files.create_index("id", unique=True)
    await db.drive_files.create_index("id", unique=True)
    await db.drive_files.create_index("server_id")
    await db.login_attempts.create_index("identifier")
    # Clear any stale login lockouts on restart
    await db.login_attempts.delete_many({})
    await db.reactions.create_index("message_id")
    await db.reactions.create_index([("message_id", 1), ("emoji", 1), ("user_id", 1)], unique=True)
    await db.thread_replies.create_index("parent_message_id")
    await db.passkey_credentials.create_index([("user_id", 1), ("credential_id", 1)], unique=True)
    await db.passkey_challenges.create_index("user_id")
    await db.custom_emojis.create_index("owner_id")
    await db.custom_emojis.create_index("id", unique=True)
    await db.saved_emojis.create_index([("user_id", 1), ("emoji_id", 1)], unique=True)
    await db.storage_requests.create_index("server_id")
    await db.storage_requests.create_index("status")

    admin_email = os.environ.get("ADMIN_EMAIL", "admin@shield.local")
    admin_password = os.environ.get("ADMIN_PASSWORD", "SecureAdmin2024!")
    existing = await db.users.find_one({"email": admin_email})
    if not existing:
        # Check if an admin user exists with old email or same username
        existing_admin = await db.users.find_one({"username_lower": "admin", "role": "admin"})
        if existing_admin:
            # Update existing admin's email to the new one
            await db.users.update_one({"username_lower": "admin", "role": "admin"}, {"$set": {"email": admin_email, "password_hash": hash_password(admin_password)}})
            logger.info(f"Admin user email updated to: {admin_email}")
        else:
            admin_id = str(uuid.uuid4())
            await db.users.insert_one({
                "id": admin_id,
                "username": "admin",
                "username_lower": "admin",
                "email": admin_email,
                "password_hash": hash_password(admin_password),
                "display_name": "Admin",
                "avatar_url": None,
                "about": "System Administrator",
                "status": "online",
                "status_message": None,
                "status_message_expires": None,
                "totp_enabled": False,
                "totp_secret": None,
                "role": "admin",
                "friends": [],
                "blocked": [],
                "friend_requests_sent": [],
                "friend_requests_received": [],
                "storage_used_bytes": 0,
                "storage_limit_bytes": 5 * 1024 * 1024 * 1024,
                "last_active": datetime.now(timezone.utc).isoformat(),
                "created_at": datetime.now(timezone.utc).isoformat()
            })
            logger.info(f"Admin user created: {admin_email}")
    elif not verify_password(admin_password, existing["password_hash"]):
        await db.users.update_one({"email": admin_email}, {"$set": {"password_hash": hash_password(admin_password)}})

    try:
        init_storage()
    except Exception as e:
        logger.warning(f"Storage init failed: {e}")

    await db.stats.update_one({"key": "global"}, {"$setOnInsert": {"messages_sent": 0, "total_servers": 0}}, upsert=True)

    # Migrate @everyone roles to new expanded permission defaults
    old_default = 0b11110000000  # Old DEFAULT was much smaller
    servers_cursor = db.servers.find({"roles.name": "@everyone"}, {"_id": 0, "id": 1, "roles": 1})
    async for srv in servers_cursor:
        for role in srv.get("roles", []):
            if role["name"] == "@everyone" and role["permissions"] < (1 << 16):
                await db.servers.update_one(
                    {"id": srv["id"], "roles.name": "@everyone"},
                    {"$set": {"roles.$.permissions": Permissions.DEFAULT}}
                )
                break
        # Ensure all members have the @everyone role id
        everyone_role = next((r for r in srv.get("roles", []) if r["name"] == "@everyone"), None)
        if everyone_role:
            await db.server_members.update_many(
                {"server_id": srv["id"], "roles": {"$nin": [everyone_role["id"]]}},
                {"$addToSet": {"roles": everyone_role["id"]}}
            )

    logger.info("Shield API started successfully")

@app.on_event("shutdown")
async def shutdown():
    client.close()

app.include_router(api_router)

_frontend_url = os.environ.get('FRONTEND_URL', '')
_cors_origins = os.environ.get('CORS_ORIGINS', '').split(',')
_cors_origins = [o.strip() for o in _cors_origins if o.strip()]
if _frontend_url and _frontend_url not in _cors_origins:
    _cors_origins.append(_frontend_url)
if not _cors_origins:
    _cors_origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
