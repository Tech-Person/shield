from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from starlette.middleware.cors import CORSMiddleware
import os, logging, jwt
from datetime import datetime, timezone

from deps import db, client, hash_password, verify_password, JWT_SECRET, JWT_ALGORITHM, logger
from models import Permissions
from websocket_manager import manager
from storage_utils import init_storage

from routes.auth import router as auth_router
from routes.users import router as users_router
from routes.friends import router as friends_router
from routes.keys import router as keys_router
from routes.dm import router as dm_router
from routes.servers import router as servers_router
from routes.channels import router as channels_router
from routes.roles import router as roles_router
from routes.files import router as files_router
from routes.emojis import router as emojis_router
from routes.admin import router as admin_router

app = FastAPI(title="Shield API")

# Include all routers under /api prefix
for r in [
    auth_router, users_router, friends_router, keys_router, dm_router,
    servers_router, channels_router, roles_router, files_router,
    emojis_router, admin_router,
]:
    app.include_router(r, prefix="/api")

# ─── WEBSOCKET (not under /api, direct on app) ───
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
                u_doc = await db.users.find_one({"id": user_id}, {"_id": 0, "username": 1, "display_name": 1})
                joined_name = (u_doc or {}).get("display_name") or (u_doc or {}).get("username", "Unknown")
                await manager.broadcast_channel(data["channel_id"], {
                    "type": "voice_state_update",
                    "channel_id": data["channel_id"],
                    "participants": participants,
                    "user_joined": user_id,
                    "user_joined_name": joined_name
                })
            elif msg_type == "leave_voice":
                u_doc2 = await db.users.find_one({"id": user_id}, {"_id": 0, "username": 1, "display_name": 1})
                left_name = (u_doc2 or {}).get("display_name") or (u_doc2 or {}).get("username", "Unknown")
                manager.leave_voice(user_id, data["channel_id"])
                participants = list(manager.get_voice_participants(data["channel_id"]))
                await manager.broadcast_channel(data["channel_id"], {
                    "type": "voice_state_update",
                    "channel_id": data["channel_id"],
                    "participants": participants,
                    "user_left": user_id,
                    "user_left_name": left_name
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
        manager.disconnect(user_id, websocket)
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
    await db.login_attempts.delete_many({})
    # Safely recreate read_receipts indexes (drop old conflicting ones first)
    try:
        await db.read_receipts.drop_index("channel_id_1_user_id_1")
    except Exception:
        pass
    try:
        await db.read_receipts.drop_index("conversation_id_1_user_id_1")
    except Exception:
        pass
    await db.read_receipts.create_index([("channel_id", 1), ("user_id", 1)], unique=True, partialFilterExpression={"channel_id": {"$type": "string"}}, name="channel_id_1_user_id_1")
    await db.read_receipts.create_index([("conversation_id", 1), ("user_id", 1)], unique=True, partialFilterExpression={"conversation_id": {"$type": "string"}}, name="conversation_id_1_user_id_1")
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
    await db.device_keys.create_index([("user_id", 1), ("device_id", 1)], unique=True)
    await db.device_keys.create_index("user_id")
    await db.key_backups.create_index("user_id", unique=True)

    admin_email = os.environ.get("ADMIN_EMAIL", "admin@shield.local")
    admin_password = os.environ.get("ADMIN_PASSWORD", "SecureAdmin2024!")
    existing = await db.users.find_one({"email": admin_email})
    if not existing:
        existing_admin = await db.users.find_one({"username_lower": "admin", "role": "admin"})
        if existing_admin:
            await db.users.update_one({"username_lower": "admin", "role": "admin"}, {"$set": {"email": admin_email, "password_hash": hash_password(admin_password)}})
            logger.info(f"Admin user email updated to: {admin_email}")
        else:
            import uuid
            admin_id = str(uuid.uuid4())
            await db.users.insert_one({
                "id": admin_id, "username": "admin", "username_lower": "admin",
                "email": admin_email, "password_hash": hash_password(admin_password),
                "display_name": "Admin", "avatar_url": None, "about": "System Administrator",
                "status": "online", "status_message": None, "status_message_expires": None,
                "totp_enabled": False, "totp_secret": None, "role": "admin",
                "friends": [], "blocked": [], "friend_requests_sent": [], "friend_requests_received": [],
                "storage_used_bytes": 0, "storage_limit_bytes": 5 * 1024 * 1024 * 1024,
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
    servers_cursor = db.servers.find({"roles.name": "@everyone"}, {"_id": 0, "id": 1, "roles": 1})
    async for srv in servers_cursor:
        for role in srv.get("roles", []):
            if role["name"] == "@everyone" and role["permissions"] < (1 << 16):
                await db.servers.update_one(
                    {"id": srv["id"], "roles.name": "@everyone"},
                    {"$set": {"roles.$.permissions": Permissions.DEFAULT}}
                )
                break
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

# ─── CORS ───
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
