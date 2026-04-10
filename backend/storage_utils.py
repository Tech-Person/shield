import os
import uuid
import logging
import requests

logger = logging.getLogger(__name__)

STORAGE_URL = "https://integrations.emergentagent.com/objstore/api/v1/storage"
APP_NAME = "shield"
storage_key = None
use_local = False
LOCAL_STORAGE_DIR = os.environ.get("LOCAL_STORAGE_DIR", "/opt/shield/data/files")


def init_storage():
    global storage_key, use_local
    if storage_key:
        return storage_key
    emergent_key = os.environ.get("STORAGE_API_KEY") or os.environ.get("EMERGENT_LLM_KEY")
    if not emergent_key:
        logger.info("Using local file storage at %s", LOCAL_STORAGE_DIR)
        use_local = True
        os.makedirs(LOCAL_STORAGE_DIR, exist_ok=True)
        return "local"
    try:
        resp = requests.post(f"{STORAGE_URL}/init", json={"emergent_key": emergent_key}, timeout=30)
        resp.raise_for_status()
        storage_key = resp.json()["storage_key"]
        logger.info("Object storage initialized successfully")
        return storage_key
    except Exception as e:
        logger.warning("Cloud storage init failed (%s) — falling back to local storage", e)
        use_local = True
        os.makedirs(LOCAL_STORAGE_DIR, exist_ok=True)
        return "local"


def put_object(path: str, data: bytes, content_type: str) -> dict:
    init_storage()
    if use_local:
        full_path = os.path.join(LOCAL_STORAGE_DIR, path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "wb") as f:
            f.write(data)
        return {"path": path, "size": len(data)}

    resp = requests.put(
        f"{STORAGE_URL}/objects/{path}",
        headers={"X-Storage-Key": storage_key, "Content-Type": content_type},
        data=data,
        timeout=120
    )
    resp.raise_for_status()
    return resp.json()


def get_object(path: str):
    init_storage()
    if use_local:
        full_path = os.path.join(LOCAL_STORAGE_DIR, path)
        if not os.path.exists(full_path):
            raise FileNotFoundError(f"File not found: {path}")
        with open(full_path, "rb") as f:
            data = f.read()
        ext = path.rsplit(".", 1)[-1].lower()
        ct_map = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "gif": "image/gif", "webp": "image/webp", "pdf": "application/pdf", "txt": "text/plain"}
        return data, ct_map.get(ext, "application/octet-stream")

    resp = requests.get(
        f"{STORAGE_URL}/objects/{path}",
        headers={"X-Storage-Key": storage_key},
        timeout=60
    )
    resp.raise_for_status()
    return resp.content, resp.headers.get("Content-Type", "application/octet-stream")


def generate_storage_path(user_id: str, filename: str, category: str = "uploads") -> str:
    ext = filename.rsplit(".", 1)[-1] if "." in filename else "bin"
    return f"{APP_NAME}/{category}/{user_id}/{uuid.uuid4()}.{ext}"
