from fastapi import APIRouter, Request, HTTPException
from deps import db, get_current_user, logger
from websocket_manager import manager
from datetime import datetime, timezone, timedelta
import uuid, os, asyncio, subprocess, hmac, hashlib, base64, time as _time

router = APIRouter()

# ─── STORAGE REQUESTS ───
@router.post("/servers/{server_id}/storage-request")
async def request_storage(server_id: str, request: Request):
    user = await get_current_user(request)
    server = await db.servers.find_one({"id": server_id}, {"_id": 0})
    if not server or server["owner_id"] != user["id"]:
        raise HTTPException(403, "Only server owner can request storage")
    body = await request.json()
    req_id = str(uuid.uuid4())
    req_doc = {
        "id": req_id, "server_id": server_id, "server_name": server["name"],
        "requester_id": user["id"], "requester_username": user["username"],
        "requested_gb": body.get("requested_gb", 50),
        "current_limit_gb": server["storage_limit_bytes"] / (1024**3),
        "reason": body.get("reason", ""), "status": "pending",
        "approved_gb": None, "admin_note": None,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.storage_requests.insert_one(req_doc)
    req_doc.pop("_id", None)
    return req_doc

@router.get("/servers/{server_id}/storage-request")
async def get_storage_requests(server_id: str, request: Request):
    user = await get_current_user(request)
    server = await db.servers.find_one({"id": server_id}, {"_id": 0})
    if not server or server["owner_id"] != user["id"]:
        raise HTTPException(403, "Not the server owner")
    reqs = await db.storage_requests.find({"server_id": server_id}, {"_id": 0}).sort("created_at", -1).to_list(50)
    return reqs

@router.get("/admin/storage-requests")
async def admin_list_storage_requests(request: Request):
    user = await get_current_user(request)
    if user.get("role") != "admin":
        raise HTTPException(403, "Admin access required")
    reqs = await db.storage_requests.find({"status": "pending"}, {"_id": 0}).sort("created_at", -1).to_list(100)
    return reqs

@router.post("/admin/storage-requests/{request_id}/approve")
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

@router.post("/admin/storage-requests/{request_id}/deny")
async def admin_deny_storage(request_id: str, request: Request):
    user = await get_current_user(request)
    if user.get("role") != "admin":
        raise HTTPException(403, "Admin access required")
    body = await request.json()
    await db.storage_requests.update_one({"id": request_id}, {"$set": {"status": "denied", "admin_note": body.get("note", "")}})
    return {"message": "Storage request denied"}

# ─── TURN SERVER MANAGEMENT ───
@router.get("/turn/credentials")
async def get_turn_credentials(request: Request):
    user = await get_current_user(request)
    turn_config = await db.settings.find_one({"key": "turn_server"}, {"_id": 0})
    if not turn_config or not turn_config.get("enabled"):
        return {"ice_servers": [{"urls": "stun:stun.l.google.com:19302"}, {"urls": "stun:stun1.l.google.com:19302"}]}
    host = turn_config.get("host", "127.0.0.1")
    port = turn_config.get("port", 3478)
    secret = turn_config.get("shared_secret", "")
    ttl = 21600
    timestamp = int(_time.time()) + ttl
    username = f"{timestamp}:{user['id']}"
    h = hmac.new(secret.encode(), username.encode(), hashlib.sha1)
    credential = base64.b64encode(h.digest()).decode()
    return {"ice_servers": [
        {"urls": "stun:stun.l.google.com:19302"},
        {"urls": f"turn:{host}:{port}?transport=udp", "username": username, "credential": credential},
        {"urls": f"turn:{host}:{port}?transport=tcp", "username": username, "credential": credential},
        {"urls": f"turns:{host}:{port + 1}?transport=tcp", "username": username, "credential": credential}
    ]}

@router.get("/admin/turn/config")
async def get_turn_config(request: Request):
    user = await get_current_user(request)
    if user.get("role") != "admin":
        raise HTTPException(403, "Admin access required")
    config = await db.settings.find_one({"key": "turn_server"}, {"_id": 0})
    if not config:
        config = {"key": "turn_server", "enabled": False, "host": "", "port": 3478, "shared_secret": "", "status": "stopped"}
    return config

@router.put("/admin/turn/config")
async def update_turn_config(request: Request):
    user = await get_current_user(request)
    if user.get("role") != "admin":
        raise HTTPException(403, "Admin access required")
    body = await request.json()
    allowed = {"host", "port", "shared_secret", "enabled", "realm"}
    update = {k: v for k, v in body.items() if k in allowed}
    update["key"] = "turn_server"
    await db.settings.update_one({"key": "turn_server"}, {"$set": update}, upsert=True)
    return {"status": "ok"}

@router.post("/admin/turn/start")
async def start_turn_server(request: Request):
    user = await get_current_user(request)
    if user.get("role") != "admin":
        raise HTTPException(403, "Admin access required")
    config = await db.settings.find_one({"key": "turn_server"}, {"_id": 0})
    secret = config.get("shared_secret", "shield-turn-secret") if config else "shield-turn-secret"
    realm = config.get("realm", "shield.local") if config else "shield.local"
    port = config.get("port", 3478) if config else 3478
    try:
        result = subprocess.run(
            ["docker", "run", "-d", "--name", "shield-coturn", "--network=host", "--restart=unless-stopped",
             "coturn/coturn:latest",
             f"--listening-port={port}", f"--tls-listening-port={port + 1}",
             f"--realm={realm}", "--use-auth-secret", f"--static-auth-secret={secret}",
             "--no-cli", "--no-tls", "--no-dtls", "--fingerprint", "--lt-cred-mech",
             "--min-port=49152", "--max-port=65535",
             "--no-multicast-peers",
             "--denied-peer-ip=10.0.0.0-10.255.255.255", "--denied-peer-ip=172.16.0.0-172.31.255.255",
             "--denied-peer-ip=192.168.0.0-192.168.255.255", "--denied-peer-ip=127.0.0.0-127.255.255.255",
             "--denied-peer-ip=0.0.0.0-0.255.255.255", "--denied-peer-ip=::1",
             "--stale-nonce=600", "--max-bps=1500000", "--total-quota=100", "--user-quota=10", "--no-tcp-relay"],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            result2 = subprocess.run(["docker", "start", "shield-coturn"], capture_output=True, text=True, timeout=15)
            if result2.returncode != 0:
                raise HTTPException(500, f"Failed to start TURN: {result.stderr} {result2.stderr}")
        await db.settings.update_one({"key": "turn_server"}, {"$set": {"enabled": True, "status": "running", "shared_secret": secret, "port": port, "realm": realm}}, upsert=True)
        return {"status": "running"}
    except subprocess.TimeoutExpired:
        raise HTTPException(500, "Docker command timed out")
    except FileNotFoundError:
        raise HTTPException(500, "Docker not installed on this server")

@router.post("/admin/turn/stop")
async def stop_turn_server(request: Request):
    user = await get_current_user(request)
    if user.get("role") != "admin":
        raise HTTPException(403, "Admin access required")
    try:
        subprocess.run(["docker", "stop", "shield-coturn"], capture_output=True, text=True, timeout=15)
        subprocess.run(["docker", "rm", "shield-coturn"], capture_output=True, text=True, timeout=15)
        await db.settings.update_one({"key": "turn_server"}, {"$set": {"enabled": False, "status": "stopped"}}, upsert=True)
        return {"status": "stopped"}
    except Exception as e:
        raise HTTPException(500, f"Failed to stop TURN: {str(e)}")

@router.get("/admin/turn/status")
async def get_turn_status(request: Request):
    user = await get_current_user(request)
    if user.get("role") != "admin":
        raise HTTPException(403, "Admin access required")
    try:
        result = subprocess.run(["docker", "inspect", "-f", "{{.State.Status}}", "shield-coturn"], capture_output=True, text=True, timeout=10)
        status = result.stdout.strip() if result.returncode == 0 else "not_found"
    except FileNotFoundError:
        status = "docker_not_installed"
    except Exception:
        status = "error"
    return {"container_status": status}

# ─── ADMIN STATS ───
@router.get("/admin/stats")
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
        "users_registered": total_users, "users_online": online_users,
        "voice_chats_active": voice_channels_active, "total_servers": total_servers,
        "total_messages": total_messages, "messages_today": msgs_today,
        "messages_this_week": msgs_week, "messages_this_month": msgs_month,
        "total_files": total_files, "total_drive_files": total_drive_files,
        "message_attachment_storage_bytes": msg_storage[0]["total"] if msg_storage else 0,
        "drive_storage_bytes": drive_storage[0]["total"] if drive_storage else 0,
        "relay_streams": []
    }

@router.get("/admin/servers")
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

@router.get("/admin/update/config")
async def get_update_config(request: Request):
    user = await get_current_user(request)
    if user.get("role") != "admin":
        raise HTTPException(403, "Admin access required")
    config = await db.update_config.find_one({"key": "update"}, {"_id": 0})
    if not config:
        config = {"key": "update", "repo_url": DEFAULT_REPO_URL, "last_check": None, "last_update": None}
        await db.update_config.insert_one(config)
    return {"repo_url": config.get("repo_url", DEFAULT_REPO_URL), "last_check": config.get("last_check"), "last_update": config.get("last_update"), "last_update_status": config.get("last_update_status"), "current_commit": config.get("current_commit"), "current_commit_message": config.get("current_commit_message")}

@router.put("/admin/update/config")
async def set_update_config(request: Request):
    user = await get_current_user(request)
    if user.get("role") != "admin":
        raise HTTPException(403, "Admin access required")
    body = await request.json()
    repo_url = body.get("repo_url", "").strip()
    if not repo_url:
        raise HTTPException(400, "repo_url required")
    await db.update_config.update_one({"key": "update"}, {"$set": {"repo_url": repo_url}}, upsert=True)
    return {"message": "Config updated"}

@router.post("/admin/update/check")
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
        remote_commits = [{"sha": c["sha"][:7], "message": c["commit"]["message"].split("\n")[0][:80], "author": c["commit"]["author"]["name"], "date": c["commit"]["author"]["date"]} for c in commits[:5]]
        remote_latest = remote_commits[0]["sha"] if remote_commits else None
        has_updates = local_commit != remote_latest if local_commit and remote_latest else True
        now = datetime.now(timezone.utc).isoformat()
        await db.update_config.update_one({"key": "update"}, {"$set": {"last_check": now, "current_commit": local_commit, "current_commit_message": local_message, "remote_latest": remote_latest}}, upsert=True)
        return {"has_updates": has_updates, "local_commit": local_commit, "local_message": local_message, "remote_latest": remote_latest, "remote_commits": remote_commits, "checked_at": now}
    except Exception as e:
        raise HTTPException(500, f"Failed to check for updates: {str(e)}")

@router.post("/admin/update/apply")
async def apply_update(request: Request):
    user = await get_current_user(request)
    if user.get("role") != "admin":
        raise HTTPException(403, "Admin access required")
    if update_lock.locked():
        raise HTTPException(409, "An update is already in progress")
    config = await db.update_config.find_one({"key": "update"}, {"_id": 0})
    repo_url = (config or {}).get("repo_url", DEFAULT_REPO_URL)
    now = datetime.now(timezone.utc).isoformat()
    await db.update_config.update_one({"key": "update"}, {"$set": {"last_update_status": "in_progress", "last_update": now}}, upsert=True)
    asyncio.create_task(_run_update(repo_url))
    return {"message": "Update started", "status": "in_progress"}

@router.get("/admin/update/status")
async def get_update_status(request: Request):
    user = await get_current_user(request)
    if user.get("role") != "admin":
        raise HTTPException(403, "Admin access required")
    config = await db.update_config.find_one({"key": "update"}, {"_id": 0})
    return {"status": (config or {}).get("last_update_status", "idle"), "log": (config or {}).get("update_log", ""), "last_update": (config or {}).get("last_update"), "current_commit": (config or {}).get("current_commit")}

async def _run_update(repo_url: str):
    async with update_lock:
        log_lines = []
        def log(msg):
            log_lines.append(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] {msg}")
        try:
            log("Starting update...")
            is_git = os.path.isdir(os.path.join(INSTALL_DIR, ".git"))
            if is_git:
                log("Git repo found. Pulling latest changes...")
                env_backups = {}
                for env_path in [os.path.join(INSTALL_DIR, "backend", ".env"), os.path.join(INSTALL_DIR, "frontend", ".env")]:
                    if os.path.exists(env_path):
                        with open(env_path) as f:
                            env_backups[env_path] = f.read()
                proc = await asyncio.create_subprocess_exec("git", "fetch", "--all", cwd=INSTALL_DIR, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
                stdout, stderr = await proc.communicate()
                log(f"git fetch: {stdout.decode().strip() or stderr.decode().strip() or 'ok'}")
                proc = await asyncio.create_subprocess_exec("git", "reset", "--hard", "origin/main", cwd=INSTALL_DIR, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
                stdout, stderr = await proc.communicate()
                if proc.returncode != 0:
                    proc = await asyncio.create_subprocess_exec("git", "reset", "--hard", "origin/master", cwd=INSTALL_DIR, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
                    stdout, stderr = await proc.communicate()
                log(f"git reset: {stdout.decode().strip() or stderr.decode().strip() or 'ok'}")
                for env_path, content in env_backups.items():
                    with open(env_path, "w") as f:
                        f.write(content)
                    log(f"Restored {env_path}")
            else:
                log("Not a git repo. Initializing from remote...")
                tmp_dir = f"/tmp/shield-update-{uuid.uuid4().hex[:8]}"
                proc = await asyncio.create_subprocess_exec("git", "clone", "--depth=1", repo_url, tmp_dir, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
                stdout, stderr = await proc.communicate()
                if proc.returncode != 0:
                    log(f"git clone failed: {stderr.decode()}")
                    raise Exception("git clone failed")
                log("Clone complete. Syncing files...")
                for item in ["backend", "frontend", "deploy"]:
                    src = os.path.join(tmp_dir, item)
                    dst = os.path.join(INSTALL_DIR, item)
                    if os.path.isdir(src):
                        env_backup = None
                        env_path = os.path.join(dst, ".env")
                        if os.path.exists(env_path):
                            with open(env_path) as f:
                                env_backup = f.read()
                        proc = await asyncio.create_subprocess_exec("rsync", "-a", "--delete", "--exclude=venv", "--exclude=node_modules", "--exclude=.env", "--exclude=build", f"{src}/", f"{dst}/", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
                        await proc.communicate()
                        log(f"Synced {item}/")
                        if env_backup:
                            with open(env_path, "w") as f:
                                f.write(env_backup)
                proc = await asyncio.create_subprocess_exec("rsync", "-a", f"{tmp_dir}/.git/", f"{INSTALL_DIR}/.git/", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
                await proc.communicate()
                proc = await asyncio.create_subprocess_exec("rm", "-rf", tmp_dir)
                await proc.communicate()
                log("Git initialized for future updates.")

            log("Installing backend dependencies...")
            venv_pip = os.path.join(INSTALL_DIR, "backend", "venv", "bin", "pip")
            req_file = os.path.join(INSTALL_DIR, "backend", "requirements.txt")
            if os.path.exists(venv_pip) and os.path.exists(req_file):
                proc = await asyncio.create_subprocess_exec(venv_pip, "install", "-r", req_file, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
                stdout, stderr = await proc.communicate()
                log(f"pip install: {'ok' if proc.returncode == 0 else stderr.decode()[:200]}")
            else:
                log("Skipping pip (no venv or requirements.txt)")

            log("Rebuilding frontend...")
            frontend_dir = os.path.join(INSTALL_DIR, "frontend")
            if os.path.exists(os.path.join(frontend_dir, "package.json")):
                proc = await asyncio.create_subprocess_exec("yarn", "install", "--frozen-lockfile", cwd=frontend_dir, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
                stdout, stderr = await proc.communicate()
                log(f"yarn install: {'ok' if proc.returncode == 0 else 'failed (trying without lockfile)'}")
                if proc.returncode != 0:
                    proc = await asyncio.create_subprocess_exec("yarn", "install", cwd=frontend_dir, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
                    await proc.communicate()
                proc = await asyncio.create_subprocess_exec("yarn", "build", cwd=frontend_dir, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
                stdout, stderr = await proc.communicate()
                log(f"yarn build: {'ok' if proc.returncode == 0 else stderr.decode()[:200]}")
            else:
                log("Skipping frontend (no package.json)")

            log("Restarting backend service...")
            proc = await asyncio.create_subprocess_exec("systemctl", "restart", "shield-backend", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            stdout, stderr = await proc.communicate()
            log(f"Service restart: {'ok' if proc.returncode == 0 else stderr.decode()[:200]}")
            log("Reloading nginx...")
            proc = await asyncio.create_subprocess_exec("systemctl", "reload", "nginx", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            await proc.communicate()

            current_commit = None
            current_message = None
            try:
                proc = await asyncio.create_subprocess_exec("git", "log", "-1", "--format=%H|||%s", cwd=INSTALL_DIR, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
                stdout, _ = await proc.communicate()
                if "|||" in stdout.decode():
                    parts = stdout.decode().strip().split("|||", 1)
                    current_commit = parts[0][:7]
                    current_message = parts[1]
            except Exception:
                pass
            log("Update complete!")
            await db.update_config.update_one({"key": "update"}, {"$set": {"last_update_status": "success", "update_log": "\n".join(log_lines), "current_commit": current_commit, "current_commit_message": current_message}}, upsert=True)
        except Exception as e:
            log(f"Update failed: {str(e)}")
            await db.update_config.update_one({"key": "update"}, {"$set": {"last_update_status": "failed", "update_log": "\n".join(log_lines)}}, upsert=True)
