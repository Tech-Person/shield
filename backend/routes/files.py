from fastapi import APIRouter, Request, Response, HTTPException, UploadFile, File, Query
from deps import db, get_current_user
from encryption import encrypt_text, decrypt_text
from storage_utils import put_object, get_object, generate_storage_path
from pydantic import BaseModel
from datetime import datetime, timezone
import uuid

router = APIRouter()

class TextFileCreate(BaseModel):
    filename: str
    content: str

class TextFileUpdate(BaseModel):
    content: str

# ─── FILE UPLOAD ───
@router.post("/upload")
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
        "id": str(uuid.uuid4()), "storage_path": result["path"],
        "original_filename": file.filename, "content_type": file.content_type,
        "size": size, "uploader_id": user["id"], "context": context,
        "is_deleted": False, "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.files.insert_one(file_doc)
    await db.users.update_one({"id": user["id"]}, {"$inc": {"storage_used_bytes": size}})
    file_doc.pop("_id", None)
    return file_doc

@router.get("/files/{file_id}/download")
async def download_file(file_id: str, request: Request):
    await get_current_user(request)
    record = await db.files.find_one({"id": file_id, "is_deleted": False}, {"_id": 0})
    if not record:
        record = await db.drive_files.find_one({"id": file_id, "is_deleted": False}, {"_id": 0})
    if not record:
        raise HTTPException(404, "File not found")
    if record.get("is_text_file"):
        content = decrypt_text(record.get("content_encrypted", ""))
        return Response(content=content.encode("utf-8"), media_type="text/plain", headers={"Content-Disposition": f"attachment; filename=\"{record['original_filename']}\""})
    data, content_type = get_object(record["storage_path"])
    return Response(content=data, media_type=record.get("content_type", content_type))

# ─── SHARE DRIVE ───
@router.post("/servers/{server_id}/drive/upload")
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
        "id": str(uuid.uuid4()), "server_id": server_id, "storage_path": result["path"],
        "original_filename": file.filename, "content_type": file.content_type,
        "size": size, "uploader_id": user["id"], "uploader_username": user["username"],
        "is_deleted": False, "is_text_file": False, "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.drive_files.insert_one(file_doc)
    await db.servers.update_one({"id": server_id}, {"$inc": {"storage_used_bytes": size}})
    file_doc.pop("_id", None)
    return file_doc

@router.get("/servers/{server_id}/drive")
async def list_drive_files(server_id: str, request: Request):
    user = await get_current_user(request)
    member = await db.server_members.find_one({"server_id": server_id, "user_id": user["id"]})
    if not member:
        raise HTTPException(403, "Not a member")
    files = await db.drive_files.find({"server_id": server_id, "is_deleted": False}, {"_id": 0}).sort("created_at", -1).to_list(1000)
    return files

@router.delete("/servers/{server_id}/drive/{file_id}")
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

# ─── TEXT FILES ───
@router.post("/servers/{server_id}/drive/text")
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
        "id": file_id, "server_id": server_id,
        "original_filename": data.filename if data.filename.endswith(".txt") else data.filename + ".txt",
        "content_type": "text/plain", "content_encrypted": encrypted_content,
        "size": size, "uploader_id": user["id"], "uploader_username": user["username"],
        "is_deleted": False, "is_text_file": True,
        "created_at": datetime.now(timezone.utc).isoformat(), "updated_at": datetime.now(timezone.utc).isoformat()
    }
    await db.drive_files.insert_one(file_doc)
    await db.servers.update_one({"id": server_id}, {"$inc": {"storage_used_bytes": size}})
    file_doc.pop("_id", None)
    file_doc["content"] = data.content
    file_doc.pop("content_encrypted", None)
    return file_doc

@router.get("/servers/{server_id}/drive/{file_id}/content")
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

@router.put("/servers/{server_id}/drive/{file_id}/content")
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

@router.get("/servers/{server_id}/drive/{file_id}/link")
async def get_drive_file_link(server_id: str, file_id: str, request: Request):
    user = await get_current_user(request)
    member = await db.server_members.find_one({"server_id": server_id, "user_id": user["id"]})
    if not member:
        raise HTTPException(403, "Not a member")
    f = await db.drive_files.find_one({"id": file_id, "server_id": server_id, "is_deleted": False}, {"_id": 0})
    if not f:
        raise HTTPException(404, "File not found")
    return {"link": f"/api/files/{file_id}/download", "filename": f["original_filename"]}
