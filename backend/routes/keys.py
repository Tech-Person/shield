from fastapi import APIRouter, Request, HTTPException
from deps import db, get_current_user
from models import DeviceKeyRegister, KeyBackupCreate
from datetime import datetime, timezone
import uuid

router = APIRouter()

@router.post("/keys/register")
async def register_device_key(data: DeviceKeyRegister, request: Request):
    user = await get_current_user(request)
    await db.device_keys.update_one(
        {"user_id": user["id"], "device_id": data.device_id},
        {"$set": {
            "user_id": user["id"], "device_id": data.device_id,
            "public_key_jwk": data.public_key_jwk,
            "registered_at": datetime.now(timezone.utc).isoformat()
        }},
        upsert=True
    )
    return {"message": "Device key registered"}

@router.get("/keys/devices")
async def get_my_devices(request: Request):
    user = await get_current_user(request)
    devices = await db.device_keys.find({"user_id": user["id"]}, {"_id": 0}).to_list(20)
    return devices

@router.get("/keys/user/{user_id}")
async def get_user_keys(user_id: str, request: Request):
    await get_current_user(request)
    keys = await db.device_keys.find({"user_id": user_id}, {"_id": 0}).to_list(20)
    return keys

@router.post("/keys/bundle")
async def get_key_bundle(request: Request):
    await get_current_user(request)
    body = await request.json()
    user_ids = body.get("user_ids", [])
    bundle = {}
    for uid in user_ids:
        keys = await db.device_keys.find({"user_id": uid}, {"_id": 0}).to_list(20)
        if keys:
            bundle[uid] = keys
    return bundle

@router.delete("/keys/device/{device_id}")
async def remove_device_key(device_id: str, request: Request):
    user = await get_current_user(request)
    await db.device_keys.delete_one({"user_id": user["id"], "device_id": device_id})
    return {"message": "Device key removed"}

@router.post("/keys/backup")
async def store_key_backup(data: KeyBackupCreate, request: Request):
    user = await get_current_user(request)
    await db.key_backups.update_one(
        {"user_id": user["id"]},
        {"$set": {
            "user_id": user["id"],
            "encrypted_private_key": data.encrypted_private_key,
            "salt": data.salt, "iv": data.iv,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }},
        upsert=True
    )
    return {"message": "Key backup stored"}

@router.get("/keys/backup")
async def get_key_backup(request: Request):
    user = await get_current_user(request)
    backup = await db.key_backups.find_one({"user_id": user["id"]}, {"_id": 0})
    if not backup:
        raise HTTPException(404, "No key backup found")
    return backup
