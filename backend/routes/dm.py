from fastapi import APIRouter, Request, HTTPException
from deps import db, get_current_user
from models import DMCreate, GroupDMCreate, MessageCreate, SearchQuery, ReactionAdd, ThreadReply, MessageEdit
from encryption import encrypt_text, decrypt_text
from websocket_manager import manager
from datetime import datetime, timezone
from typing import Optional
import uuid

router = APIRouter()

@router.post("/dm/create")
async def create_dm(data: DMCreate, request: Request):
    user = await get_current_user(request)
    participants = sorted([user["id"], data.recipient_id])
    existing = await db.conversations.find_one({"type": "dm", "participants": participants}, {"_id": 0})
    if existing:
        return existing
    conv_id = str(uuid.uuid4())
    conv = {"id": conv_id, "type": "dm", "participants": participants, "created_at": datetime.now(timezone.utc).isoformat()}
    await db.conversations.insert_one(conv)
    conv.pop("_id", None)
    return conv

@router.post("/dm/group")
async def create_group_dm(data: GroupDMCreate, request: Request):
    user = await get_current_user(request)
    all_members = list(set([user["id"]] + data.member_ids))
    if len(all_members) < 2:
        raise HTTPException(400, "Group DM needs at least 2 participants")
    conv_id = str(uuid.uuid4())
    name = data.name or f"Group ({len(all_members)})"
    conv = {"id": conv_id, "type": "group", "name": name, "participants": all_members, "owner_id": user["id"], "created_at": datetime.now(timezone.utc).isoformat()}
    await db.conversations.insert_one(conv)
    conv.pop("_id", None)
    for pid in all_members:
        if pid != user["id"]:
            await manager.send_personal(pid, {"type": "new_conversation", "conversation": conv})
    return conv

@router.get("/dm/conversations")
async def get_conversations(request: Request):
    user = await get_current_user(request)
    convs = await db.conversations.find({"participants": user["id"]}, {"_id": 0}).to_list(100)
    result = []
    for conv in convs:
        if conv["type"] == "dm":
            other_id = next((p for p in conv["participants"] if p != user["id"]), None)
            if other_id:
                other = await db.users.find_one({"id": other_id}, {"_id": 0, "password_hash": 0, "totp_secret": 0})
                conv["other_user"] = other
        last_msg = await db.messages.find_one({"conversation_id": conv["id"]}, {"_id": 0}, sort=[("created_at", -1)])
        if last_msg:
            if last_msg.get("e2e"):
                pass
            elif last_msg.get("content_encrypted"):
                last_msg["content"] = decrypt_text(last_msg["content_encrypted"])
            last_msg.pop("content_encrypted", None)
        conv["last_message"] = last_msg
        result.append(conv)
    result.sort(key=lambda c: (c.get("last_message", {}) or {}).get("created_at", c.get("created_at", "")), reverse=True)
    return result

@router.post("/dm/{conversation_id}/messages")
async def send_dm_message(conversation_id: str, data: MessageCreate, request: Request):
    user = await get_current_user(request)
    conv = await db.conversations.find_one({"id": conversation_id, "participants": user["id"]}, {"_id": 0})
    if not conv:
        raise HTTPException(404, "Conversation not found")
    msg_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    if data.e2e and data.encrypted_content:
        msg = {
            "id": msg_id, "conversation_id": conversation_id,
            "sender_id": user["id"], "sender_username": user["username"],
            "sender_avatar": user.get("avatar_url"),
            "e2e": True, "encrypted_content": data.encrypted_content,
            "iv": data.iv, "encrypted_keys": data.encrypted_keys or {},
            "attachments": data.attachments or [], "edited": False, "created_at": now
        }
    else:
        encrypted_content = encrypt_text(data.content)
        msg = {
            "id": msg_id, "conversation_id": conversation_id,
            "sender_id": user["id"], "sender_username": user["username"],
            "sender_avatar": user.get("avatar_url"),
            "content_encrypted": encrypted_content,
            "attachments": data.attachments or [], "edited": False, "created_at": now
        }
    await db.messages.insert_one(msg)

    broadcast_msg = {
        "type": "dm_message", "message": {
            "id": msg_id, "conversation_id": conversation_id,
            "sender_id": user["id"], "sender_username": user["username"],
            "sender_avatar": user.get("avatar_url"),
            "attachments": data.attachments or [], "edited": False, "created_at": now
        }
    }
    if data.e2e:
        broadcast_msg["message"]["e2e"] = True
        broadcast_msg["message"]["encrypted_content"] = data.encrypted_content
        broadcast_msg["message"]["iv"] = data.iv
        broadcast_msg["message"]["encrypted_keys"] = data.encrypted_keys or {}
    else:
        broadcast_msg["message"]["content"] = data.content

    for pid in conv["participants"]:
        if pid != user["id"]:
            await manager.send_personal(pid, broadcast_msg)
    await db.stats.update_one({"key": "global"}, {"$inc": {"messages_sent": 1}}, upsert=True)
    resp = broadcast_msg["message"].copy()
    return resp

# ─── DM CALLS ───
@router.post("/dm/{conversation_id}/call")
async def start_dm_call(conversation_id: str, request: Request):
    user = await get_current_user(request)
    conv = await db.conversations.find_one({"id": conversation_id, "participants": user["id"]}, {"_id": 0})
    if not conv:
        raise HTTPException(404, "Conversation not found")
    call_id = str(uuid.uuid4())
    call = {
        "id": call_id, "conversation_id": conversation_id,
        "initiator_id": user["id"], "initiator_username": user["username"],
        "participants": [user["id"]], "status": "ringing",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.calls.insert_one(call)
    for pid in conv["participants"]:
        if pid != user["id"]:
            await manager.send_personal(pid, {
                "type": "incoming_call", "call_id": call_id,
                "conversation_id": conversation_id,
                "caller_id": user["id"], "caller_username": user["username"]
            })
    call.pop("_id", None)
    return call

@router.post("/dm/call/{call_id}/answer")
async def answer_dm_call(call_id: str, request: Request):
    user = await get_current_user(request)
    call = await db.calls.find_one({"id": call_id}, {"_id": 0})
    if not call:
        raise HTTPException(404, "Call not found")
    conv = await db.conversations.find_one({"id": call["conversation_id"], "participants": user["id"]}, {"_id": 0})
    if not conv:
        raise HTTPException(403, "Not a participant")
    await db.calls.update_one({"id": call_id}, {"$set": {"status": "active"}, "$addToSet": {"participants": user["id"]}})
    for pid in conv["participants"]:
        await manager.send_personal(pid, {"type": "call_answered", "call_id": call_id, "user_id": user["id"], "username": user["username"]})
    return {"status": "active"}

@router.post("/dm/call/{call_id}/decline")
async def decline_dm_call(call_id: str, request: Request):
    user = await get_current_user(request)
    call = await db.calls.find_one({"id": call_id}, {"_id": 0})
    if not call:
        raise HTTPException(404, "Call not found")
    await db.calls.update_one({"id": call_id}, {"$set": {"status": "declined"}})
    conv = await db.conversations.find_one({"id": call["conversation_id"]}, {"_id": 0})
    if conv:
        for pid in conv["participants"]:
            await manager.send_personal(pid, {"type": "call_declined", "call_id": call_id, "user_id": user["id"]})
    return {"status": "declined"}

@router.post("/dm/call/{call_id}/end")
async def end_dm_call(call_id: str, request: Request):
    user = await get_current_user(request)
    call = await db.calls.find_one({"id": call_id}, {"_id": 0})
    if not call:
        raise HTTPException(404, "Call not found")
    await db.calls.update_one({"id": call_id}, {"$set": {"status": "ended", "ended_at": datetime.now(timezone.utc).isoformat()}})
    conv = await db.conversations.find_one({"id": call["conversation_id"]}, {"_id": 0})
    if conv:
        for pid in conv["participants"]:
            await manager.send_personal(pid, {"type": "call_ended", "call_id": call_id, "user_id": user["id"]})
    return {"status": "ended"}

@router.get("/dm/{conversation_id}/messages")
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
        if msg.get("e2e"):
            pass
        elif msg.get("content_encrypted"):
            msg["content"] = decrypt_text(msg["content_encrypted"])
        msg.pop("content_encrypted", None)
        msg["reactions"] = await db.reactions.find({"message_id": msg["id"]}, {"_id": 0}).to_list(50)
        msg["thread_count"] = msg.get("thread_count", 0)
    messages.reverse()
    return messages

@router.post("/dm/search")
async def search_messages(data: SearchQuery, request: Request):
    user = await get_current_user(request)
    if data.conversation_id:
        conv = await db.conversations.find_one({"id": data.conversation_id, "participants": user["id"]}, {"_id": 0})
        if not conv:
            raise HTTPException(404, "Conversation not found")
        messages = await db.messages.find({"conversation_id": data.conversation_id}, {"_id": 0}).sort("created_at", -1).limit(200).to_list(200)
    else:
        user_convs = await db.conversations.find({"participants": user["id"]}, {"_id": 0, "id": 1}).to_list(100)
        conv_ids = [c["id"] for c in user_convs]
        messages = await db.messages.find({"conversation_id": {"$in": conv_ids}}, {"_id": 0}).sort("created_at", -1).limit(200).to_list(200)
    results = []
    for msg in messages:
        if msg.get("e2e"):
            continue
        if msg.get("content_encrypted"):
            decrypted = decrypt_text(msg["content_encrypted"])
            if data.query.lower() in decrypted.lower():
                msg["content"] = decrypted
                msg.pop("content_encrypted", None)
                results.append(msg)
    return results[:data.limit]

# ─── DM Read Receipts ───
@router.post("/dm/{conversation_id}/read")
async def mark_dm_read(conversation_id: str, request: Request):
    user = await get_current_user(request)
    body = await request.json()
    last_message_id = body.get("last_message_id")
    if not last_message_id:
        raise HTTPException(400, "last_message_id required")
    conv = await db.conversations.find_one({"id": conversation_id, "participants": user["id"]}, {"_id": 0})
    if not conv:
        raise HTTPException(404, "Conversation not found")
    now = datetime.now(timezone.utc).isoformat()
    await db.read_receipts.update_one(
        {"conversation_id": conversation_id, "user_id": user["id"]},
        {"$set": {"last_message_id": last_message_id, "read_at": now, "user_id": user["id"], "username": user["username"], "conversation_id": conversation_id}},
        upsert=True
    )
    for pid in conv["participants"]:
        if pid != user["id"]:
            await manager.send_personal(pid, {"type": "read_receipt", "conversation_id": conversation_id, "user_id": user["id"], "username": user["username"], "last_message_id": last_message_id, "read_at": now})
    return {"message": "Marked as read"}

@router.get("/dm/{conversation_id}/read-receipts")
async def get_dm_read_receipts(conversation_id: str, request: Request):
    user = await get_current_user(request)
    conv = await db.conversations.find_one({"id": conversation_id, "participants": user["id"]}, {"_id": 0})
    if not conv:
        raise HTTPException(404, "Conversation not found")
    receipts = await db.read_receipts.find({"conversation_id": conversation_id}, {"_id": 0}).to_list(50)
    return receipts

# ─── DM Reactions ───
@router.post("/messages/{message_id}/reactions")
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

@router.delete("/messages/{message_id}/reactions/{emoji}")
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

@router.get("/messages/{message_id}/reactions")
async def get_dm_reactions(message_id: str, request: Request):
    await get_current_user(request)
    reactions = await db.reactions.find({"message_id": message_id}, {"_id": 0}).to_list(100)
    return reactions

# ─── DM Threads ───
@router.post("/messages/{message_id}/thread")
async def reply_dm_thread(message_id: str, data: ThreadReply, request: Request):
    user = await get_current_user(request)
    parent = await db.messages.find_one({"id": message_id}, {"_id": 0})
    if not parent:
        raise HTTPException(404, "Message not found")
    conv = await db.conversations.find_one({"id": parent["conversation_id"], "participants": user["id"]}, {"_id": 0})
    if not conv:
        raise HTTPException(403, "Not a participant")
    reply_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    if data.e2e and data.encrypted_content:
        reply = {"id": reply_id, "parent_message_id": message_id, "conversation_id": parent["conversation_id"], "sender_id": user["id"], "sender_username": user["username"], "sender_avatar": user.get("avatar_url"), "e2e": True, "encrypted_content": data.encrypted_content, "iv": data.iv, "encrypted_keys": data.encrypted_keys or {}, "attachments": data.attachments or [], "created_at": now}
    else:
        reply = {"id": reply_id, "parent_message_id": message_id, "conversation_id": parent["conversation_id"], "sender_id": user["id"], "sender_username": user["username"], "sender_avatar": user.get("avatar_url"), "content_encrypted": encrypt_text(data.content), "attachments": data.attachments or [], "created_at": now}
    await db.thread_replies.insert_one(reply)
    await db.messages.update_one({"id": message_id}, {"$inc": {"thread_count": 1}})
    broadcast_reply = {"id": reply_id, "parent_message_id": message_id, "sender_id": user["id"], "sender_username": user["username"], "attachments": data.attachments or [], "created_at": now}
    if data.e2e:
        broadcast_reply.update({"e2e": True, "encrypted_content": data.encrypted_content, "iv": data.iv, "encrypted_keys": data.encrypted_keys or {}})
    else:
        broadcast_reply["content"] = data.content
    broadcast = {"type": "thread_reply", "parent_message_id": message_id, "reply": broadcast_reply}
    for pid in conv["participants"]:
        await manager.send_personal(pid, broadcast)
    return broadcast_reply

@router.get("/messages/{message_id}/thread")
async def get_dm_thread(message_id: str, request: Request):
    await get_current_user(request)
    replies = await db.thread_replies.find({"parent_message_id": message_id}, {"_id": 0}).sort("created_at", 1).to_list(200)
    for r in replies:
        if r.get("e2e"):
            pass
        elif r.get("content_encrypted"):
            r["content"] = decrypt_text(r["content_encrypted"])
        r.pop("content_encrypted", None)
    return replies

# ─── DM Edit / Delete ───
@router.put("/messages/{message_id}")
async def edit_dm_message(message_id: str, data: MessageEdit, request: Request):
    user = await get_current_user(request)
    msg = await db.messages.find_one({"id": message_id, "sender_id": user["id"]}, {"_id": 0})
    if not msg:
        raise HTTPException(404, "Message not found or not yours")
    if data.e2e and data.encrypted_content:
        await db.messages.update_one({"id": message_id}, {"$set": {"e2e": True, "encrypted_content": data.encrypted_content, "iv": data.iv, "encrypted_keys": data.encrypted_keys or {}, "edited": True}, "$unset": {"content_encrypted": ""}})
        broadcast = {"type": "message_edited", "message_id": message_id, "edited": True, "e2e": True, "encrypted_content": data.encrypted_content, "iv": data.iv, "encrypted_keys": data.encrypted_keys or {}}
    else:
        encrypted = encrypt_text(data.content)
        await db.messages.update_one({"id": message_id}, {"$set": {"content_encrypted": encrypted, "edited": True}})
        broadcast = {"type": "message_edited", "message_id": message_id, "content": data.content, "edited": True}
    conv = await db.conversations.find_one({"id": msg["conversation_id"]}, {"_id": 0})
    if conv:
        for pid in conv["participants"]:
            await manager.send_personal(pid, broadcast)
    return {"message": "Edited"}

@router.delete("/messages/{message_id}")
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
