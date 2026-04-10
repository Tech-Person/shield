from fastapi import APIRouter, Request, Response, HTTPException, Query
from deps import db, get_current_user, sanitize_user, hash_password, verify_password, create_access_token, create_refresh_token, set_auth_cookies, JWT_SECRET, JWT_ALGORITHM, logger
from models import UserCreate, UserLogin, TwoFactorVerify
from websocket_manager import manager
from datetime import datetime, timezone
import uuid, jwt, pyotp, qrcode, io, base64, os

from webauthn import generate_registration_options, verify_registration_response, generate_authentication_options, verify_authentication_response
from webauthn.helpers.structs import AuthenticatorSelectionCriteria, UserVerificationRequirement, ResidentKeyRequirement, PublicKeyCredentialDescriptor
from webauthn.helpers import bytes_to_base64url, base64url_to_bytes

WEBAUTHN_RP_ID = os.environ.get("WEBAUTHN_RP_ID", "localhost")
WEBAUTHN_RP_NAME = "Shield"
WEBAUTHN_ORIGIN = os.environ.get("WEBAUTHN_ORIGIN", "http://localhost:3000")

router = APIRouter()

@router.post("/auth/register")
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
        "id": user_id, "username": username, "username_lower": username.lower(),
        "email": email, "password_hash": hash_password(data.password),
        "display_name": username, "avatar_url": None, "about": "",
        "status": "online", "status_message": None, "status_message_expires": None,
        "totp_enabled": False, "totp_secret": None, "role": "user",
        "friends": [], "blocked": [], "friend_requests_sent": [], "friend_requests_received": [],
        "storage_used_bytes": 0, "storage_limit_bytes": 5 * 1024 * 1024 * 1024,
        "last_active": datetime.now(timezone.utc).isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.users.insert_one(user_doc)
    access = create_access_token(user_id, username)
    refresh = create_refresh_token(user_id)
    set_auth_cookies(response, access, refresh)
    return {"user": sanitize_user(user_doc), "access_token": access}

@router.post("/auth/login")
async def login(data: UserLogin, request: Request, response: Response):
    email = data.email.lower().strip()
    ip = request.headers.get("x-real-ip") or request.headers.get("x-forwarded-for", "").split(",")[0].strip() or (request.client.host if request.client else "unknown")
    identifier = f"{ip}:{email}"
    attempt = await db.login_attempts.find_one({"identifier": identifier})
    if attempt and attempt.get("locked_until"):
        lock_time = datetime.fromisoformat(attempt["locked_until"])
        if datetime.now(timezone.utc) < lock_time:
            remaining = int((lock_time - datetime.now(timezone.utc)).total_seconds())
            raise HTTPException(429, f"Too many login attempts. Try again in {remaining} seconds.")
        else:
            await db.login_attempts.delete_one({"identifier": identifier})

    user = await db.users.find_one({"email": email})
    if not user or not verify_password(data.password, user["password_hash"]):
        if not attempt:
            await db.login_attempts.insert_one({"identifier": identifier, "count": 1, "last_attempt": datetime.now(timezone.utc).isoformat()})
        else:
            new_count = attempt.get("count", 0) + 1
            update = {"count": new_count, "last_attempt": datetime.now(timezone.utc).isoformat()}
            if new_count >= 5:
                from datetime import timedelta
                update["locked_until"] = (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()
            await db.login_attempts.update_one({"identifier": identifier}, {"$set": update})
        raise HTTPException(401, "Invalid credentials")

    await db.login_attempts.delete_one({"identifier": identifier})
    user.pop("_id", None)

    if user.get("totp_enabled"):
        temp_token = jwt.encode({"sub": user["id"], "type": "2fa_pending", "exp": datetime.now(timezone.utc) + __import__('datetime').timedelta(minutes=10)}, JWT_SECRET, algorithm=JWT_ALGORITHM)
        return {"requires_2fa": True, "temp_token": temp_token}

    await db.users.update_one({"id": user["id"]}, {"$set": {"status": "online", "last_active": datetime.now(timezone.utc).isoformat()}})
    access = create_access_token(user["id"], user["username"])
    refresh = create_refresh_token(user["id"])
    set_auth_cookies(response, access, refresh)
    return {"user": sanitize_user(user), "access_token": access}

@router.post("/auth/verify-2fa")
async def verify_2fa(data: TwoFactorVerify, request: Request, response: Response, temp_token: str = Query(...)):
    try:
        payload = jwt.decode(temp_token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "2fa_pending":
            raise HTTPException(401, "Invalid token")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid or expired token")

    user = await db.users.find_one({"id": payload["sub"]})
    if not user:
        raise HTTPException(404, "User not found")
    totp = pyotp.TOTP(user["totp_secret"])
    if not totp.verify(data.code, valid_window=1):
        raise HTTPException(401, "Invalid 2FA code")

    await db.users.update_one({"id": user["id"]}, {"$set": {"status": "online", "last_active": datetime.now(timezone.utc).isoformat()}})
    user.pop("_id", None)
    access = create_access_token(user["id"], user["username"])
    refresh = create_refresh_token(user["id"])
    set_auth_cookies(response, access, refresh)
    return {"user": sanitize_user(user), "access_token": access}

@router.post("/auth/setup-2fa")
async def setup_2fa(request: Request):
    user = await get_current_user(request)
    secret = pyotp.random_base32()
    totp = pyotp.TOTP(secret)
    uri = totp.provisioning_uri(name=user["email"], issuer_name="Shield")
    qr = qrcode.make(uri)
    buffer = io.BytesIO()
    qr.save(buffer, format="PNG")
    qr_b64 = base64.b64encode(buffer.getvalue()).decode()
    await db.users.update_one({"id": user["id"]}, {"$set": {"totp_secret": secret}})
    return {"secret": secret, "qr_code": f"data:image/png;base64,{qr_b64}", "uri": uri}

@router.post("/auth/confirm-2fa")
async def confirm_2fa(data: TwoFactorVerify, request: Request):
    user = await get_current_user(request)
    full = await db.users.find_one({"id": user["id"]})
    if not full or not full.get("totp_secret"):
        raise HTTPException(400, "Setup 2FA first")
    totp = pyotp.TOTP(full["totp_secret"])
    if not totp.verify(data.code, valid_window=1):
        raise HTTPException(401, "Invalid code")
    await db.users.update_one({"id": user["id"]}, {"$set": {"totp_enabled": True}})
    return {"message": "2FA enabled"}

@router.post("/auth/disable-2fa")
async def disable_2fa(data: TwoFactorVerify, request: Request):
    user = await get_current_user(request)
    full = await db.users.find_one({"id": user["id"]})
    if not full or not full.get("totp_secret"):
        raise HTTPException(400, "2FA not enabled")
    totp = pyotp.TOTP(full["totp_secret"])
    if not totp.verify(data.code, valid_window=1):
        raise HTTPException(401, "Invalid code")
    await db.users.update_one({"id": user["id"]}, {"$set": {"totp_enabled": False, "totp_secret": None}})
    return {"message": "2FA disabled"}

@router.get("/auth/me")
async def get_me(request: Request):
    user = await get_current_user(request)
    return {"user": sanitize_user(user)}

@router.post("/auth/logout")
async def logout(request: Request, response: Response):
    user = await get_current_user(request)
    await db.users.update_one({"id": user["id"]}, {"$set": {"status": "offline", "last_active": datetime.now(timezone.utc).isoformat()}})
    servers = await db.server_members.find({"user_id": user["id"]}, {"server_id": 1}).to_list(100)
    for s in servers:
        members = await db.server_members.find({"server_id": s["server_id"]}, {"user_id": 1}).to_list(500)
        for m in members:
            if m["user_id"] != user["id"]:
                await manager.send_personal(m["user_id"], {"type": "status_update", "user_id": user["id"], "status": "offline"})
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")
    return {"message": "Logged out"}

@router.post("/auth/refresh")
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
        user.pop("_id", None)
        access = create_access_token(user["id"], user["username"])
        refresh = create_refresh_token(user["id"])
        set_auth_cookies(response, access, refresh)
        return {"user": sanitize_user(user), "access_token": access}
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid refresh token")

# ─── PASSKEY / WEBAUTHN ───
@router.post("/auth/passkey/register/begin")
async def begin_passkey_registration(request: Request):
    user = await get_current_user(request)
    existing_creds = await db.passkey_credentials.find({"user_id": user["id"]}, {"_id": 0}).to_list(20)
    exclude = [PublicKeyCredentialDescriptor(id=base64url_to_bytes(cred["credential_id"])) for cred in existing_creds]
    options = generate_registration_options(
        rp_id=WEBAUTHN_RP_ID, rp_name=WEBAUTHN_RP_NAME,
        user_id=user["id"].encode(), user_name=user["username"],
        user_display_name=user.get("display_name", user["username"]),
        authenticator_selection=AuthenticatorSelectionCriteria(resident_key=ResidentKeyRequirement.PREFERRED, user_verification=UserVerificationRequirement.PREFERRED),
        exclude_credentials=exclude, timeout=60000,
    )
    challenge_b64 = bytes_to_base64url(options.challenge)
    await db.passkey_challenges.insert_one({"user_id": user["id"], "challenge": challenge_b64, "type": "registration", "created_at": datetime.now(timezone.utc).isoformat()})
    return {
        "challenge": challenge_b64,
        "rp": {"id": options.rp.id, "name": options.rp.name},
        "user": {"id": bytes_to_base64url(options.user.id), "name": options.user.name, "displayName": options.user.display_name},
        "pubKeyCredParams": [{"type": "public-key", "alg": p.alg} for p in options.pub_key_cred_params],
        "timeout": options.timeout, "attestation": options.attestation,
        "excludeCredentials": [{"type": "public-key", "id": bytes_to_base64url(e.id)} for e in exclude],
        "authenticatorSelection": {"residentKey": "preferred", "userVerification": "preferred"}
    }

@router.post("/auth/passkey/register/complete")
async def complete_passkey_registration(request: Request):
    user = await get_current_user(request)
    body = await request.json()
    challenge_doc = await db.passkey_challenges.find_one({"user_id": user["id"], "type": "registration"}, {"_id": 0})
    if not challenge_doc:
        raise HTTPException(400, "No registration challenge found")
    await db.passkey_challenges.delete_many({"user_id": user["id"], "type": "registration"})
    try:
        verification = verify_registration_response(
            credential=body["credential"], expected_challenge=base64url_to_bytes(challenge_doc["challenge"]),
            expected_origin=WEBAUTHN_ORIGIN, expected_rp_id=WEBAUTHN_RP_ID,
        )
    except Exception as e:
        raise HTTPException(400, f"Verification failed: {str(e)}")
    cred_id_b64 = bytes_to_base64url(verification.credential_id)
    pub_key_b64 = bytes_to_base64url(verification.credential_public_key)
    await db.passkey_credentials.insert_one({
        "id": str(uuid.uuid4()), "user_id": user["id"], "credential_id": cred_id_b64,
        "public_key": pub_key_b64, "sign_count": verification.sign_count,
        "name": body.get("name", "Passkey"), "created_at": datetime.now(timezone.utc).isoformat()
    })
    return {"message": "Passkey registered successfully"}

@router.post("/auth/passkey/authenticate/begin")
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
        rp_id=WEBAUTHN_RP_ID, allow_credentials=allow_creds,
        user_verification=UserVerificationRequirement.PREFERRED, timeout=120000,
    )
    challenge_b64 = bytes_to_base64url(options.challenge)
    if user:
        await db.passkey_challenges.insert_one({"user_id": user["id"], "challenge": challenge_b64, "type": "authentication", "created_at": datetime.now(timezone.utc).isoformat()})
    return {
        "challenge": challenge_b64, "timeout": options.timeout, "rpId": options.rp_id, "userVerification": "preferred",
        "allowCredentials": [{"type": "public-key", "id": bytes_to_base64url(c.id), "transports": ["internal"]} for c in allow_creds]
    }

@router.post("/auth/passkey/authenticate/complete")
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
            credential=credential, expected_challenge=base64url_to_bytes(challenge_doc["challenge"]),
            expected_origin=WEBAUTHN_ORIGIN, expected_rp_id=WEBAUTHN_RP_ID,
            credential_public_key=base64url_to_bytes(stored_cred["public_key"]),
            credential_current_sign_count=stored_cred["sign_count"],
        )
    except Exception as e:
        raise HTTPException(401, f"Authentication failed: {str(e)}")
    await db.passkey_credentials.update_one({"user_id": user["id"], "credential_id": cred_id}, {"$set": {"sign_count": verification.new_sign_count}})
    await db.users.update_one({"id": user["id"]}, {"$set": {"status": "online", "last_active": datetime.now(timezone.utc).isoformat()}})
    access = create_access_token(user["id"], user["username"])
    refresh = create_refresh_token(user["id"])
    set_auth_cookies(response, access, refresh)
    return {"user": sanitize_user(user), "access_token": access}

@router.get("/auth/passkeys")
async def list_passkeys(request: Request):
    user = await get_current_user(request)
    creds = await db.passkey_credentials.find({"user_id": user["id"]}, {"_id": 0}).to_list(20)
    return creds

@router.delete("/auth/passkeys/{credential_id}")
async def delete_passkey(credential_id: str, request: Request):
    user = await get_current_user(request)
    await db.passkey_credentials.delete_one({"user_id": user["id"], "credential_id": credential_id})
    return {"message": "Passkey removed"}
