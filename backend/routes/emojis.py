from fastapi import APIRouter, Request, Response, HTTPException, UploadFile, File, Query
from deps import db, get_current_user
from storage_utils import put_object, get_object, generate_storage_path
from datetime import datetime, timezone
import uuid

router = APIRouter()

@router.post("/emojis/upload")
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
        "id": emoji_id, "name": name.strip().lower().replace(" ", "_"),
        "type": emoji_type, "storage_path": result["path"],
        "content_type": file.content_type, "size": size,
        "owner_id": user["id"], "owner_username": user["username"],
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.custom_emojis.insert_one(doc)
    doc.pop("_id", None)
    return doc

@router.get("/emojis/mine")
async def get_my_emojis(request: Request):
    user = await get_current_user(request)
    own = await db.custom_emojis.find({"owner_id": user["id"]}, {"_id": 0}).to_list(200)
    saved = await db.saved_emojis.find({"user_id": user["id"]}, {"_id": 0}).to_list(200)
    saved_ids = [s["emoji_id"] for s in saved]
    saved_emojis = []
    if saved_ids:
        saved_emojis = await db.custom_emojis.find({"id": {"$in": saved_ids}}, {"_id": 0}).to_list(200)
    return {"owned": own, "saved": saved_emojis}

@router.get("/emojis/{emoji_id}/image")
async def get_emoji_image(emoji_id: str):
    doc = await db.custom_emojis.find_one({"id": emoji_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Emoji not found")
    data, ct = get_object(doc["storage_path"])
    return Response(content=data, media_type=doc.get("content_type", ct))

@router.post("/emojis/{emoji_id}/save")
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

@router.delete("/emojis/{emoji_id}/save")
async def unsave_emoji(emoji_id: str, request: Request):
    user = await get_current_user(request)
    await db.saved_emojis.delete_one({"user_id": user["id"], "emoji_id": emoji_id})
    return {"message": "Emoji removed from library"}

@router.delete("/emojis/{emoji_id}")
async def delete_emoji(emoji_id: str, request: Request):
    user = await get_current_user(request)
    doc = await db.custom_emojis.find_one({"id": emoji_id, "owner_id": user["id"]}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Emoji not found or not yours")
    await db.custom_emojis.delete_one({"id": emoji_id})
    await db.saved_emojis.delete_many({"emoji_id": emoji_id})
    return {"message": "Emoji deleted"}
