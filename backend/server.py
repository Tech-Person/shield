from fastapi import FastAPI, APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
import uuid
from datetime import datetime, timezone, timedelta
import jwt
import bcrypt
import subprocess
import re

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# JWT Configuration
JWT_SECRET = os.environ.get('JWT_SECRET', 'port-forward-manager-secret-key-change-in-production')
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24

# WireGuard Configuration
WIREGUARD_INTERFACE = os.environ.get('WIREGUARD_INTERFACE', 'wg0')
WIREGUARD_DEST_IP = os.environ.get('WIREGUARD_DEST_IP', '10.0.0.2')
SAFE_PORT_MIN = 60000
SAFE_PORT_MAX = 61000

# Create the main app
app = FastAPI(title="Port Forwarding Manager")
api_router = APIRouter(prefix="/api")
security = HTTPBearer()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ==================== MODELS ====================

class UserCreate(BaseModel):
    username: str
    password: str
    role: str = "user"  # "admin" or "user"

class UserLogin(BaseModel):
    username: str
    password: str

class UserResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    username: str
    role: str
    must_change_password: bool
    created_at: str
    last_login: Optional[str] = None

class PasswordChange(BaseModel):
    current_password: str
    new_password: str

class PortRuleCreate(BaseModel):
    name: str
    external_port: int
    internal_port: int
    protocol: str = "both"  # "tcp", "udp", or "both"
    description: Optional[str] = ""

class PortRuleUpdate(BaseModel):
    name: Optional[str] = None
    external_port: Optional[int] = None
    internal_port: Optional[int] = None
    protocol: Optional[str] = None
    description: Optional[str] = None
    enabled: Optional[bool] = None

class PortRuleResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    name: str
    external_port: int
    internal_port: int
    protocol: str
    description: str
    enabled: bool
    created_at: str
    created_by: str
    is_outside_safe_range: bool

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

class SystemStatus(BaseModel):
    iptables_available: bool
    ufw_available: bool
    wireguard_interface: str
    destination_ip: str
    simulation_mode: bool

# ==================== HELPER FUNCTIONS ====================

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def create_token(user_id: str, username: str, role: str) -> str:
    payload = {
        "sub": user_id,
        "username": username,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRATION_HOURS)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        user = await db.users.find_one({"id": user_id}, {"_id": 0})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

async def require_admin(user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user

# ==================== SYSTEM COMMANDS ====================
# These are MOCKED for the dev environment. On real Pi, set SIMULATION_MODE=false

SIMULATION_MODE = os.environ.get('SIMULATION_MODE', 'true').lower() == 'true'

def run_command(cmd: List[str]) -> tuple:
    """Execute a system command. Returns (success, output)"""
    if SIMULATION_MODE:
        logger.info(f"[SIMULATION] Would execute: {' '.join(cmd)}")
        return True, f"[SIMULATED] {' '.join(cmd)}"
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            return True, result.stdout
        else:
            logger.error(f"Command failed: {result.stderr}")
            return False, result.stderr
    except Exception as e:
        logger.error(f"Command exception: {e}")
        return False, str(e)

def check_iptables_rule_exists(external_port: int, protocol: str) -> bool:
    """Check if an iptables NAT rule already exists"""
    if SIMULATION_MODE:
        return False
    
    success, output = run_command([
        'iptables', '-t', 'nat', '-C', 'PREROUTING',
        '-p', protocol, '--dport', str(external_port),
        '-j', 'DNAT', '--to-destination', f'{WIREGUARD_DEST_IP}:{external_port}'
    ])
    return success

def check_ufw_rule_exists(port: int, protocol: str) -> bool:
    """Check if a UFW rule already exists"""
    if SIMULATION_MODE:
        return False
    
    success, output = run_command(['ufw', 'status', 'numbered'])
    if success:
        pattern = f"{port}/{protocol}"
        return pattern.lower() in output.lower()
    return False

def add_iptables_rule(external_port: int, internal_port: int, protocol: str) -> tuple:
    """Add iptables NAT PREROUTING rule"""
    if check_iptables_rule_exists(external_port, protocol):
        return True, "Rule already exists"
    
    return run_command([
        'iptables', '-t', 'nat', '-A', 'PREROUTING',
        '-i', WIREGUARD_INTERFACE, '-p', protocol,
        '--dport', str(external_port),
        '-j', 'DNAT', '--to-destination', f'{WIREGUARD_DEST_IP}:{internal_port}'
    ])

def remove_iptables_rule(external_port: int, internal_port: int, protocol: str) -> tuple:
    """Remove iptables NAT PREROUTING rule"""
    return run_command([
        'iptables', '-t', 'nat', '-D', 'PREROUTING',
        '-i', WIREGUARD_INTERFACE, '-p', protocol,
        '--dport', str(external_port),
        '-j', 'DNAT', '--to-destination', f'{WIREGUARD_DEST_IP}:{internal_port}'
    ])

def add_ufw_rule(port: int, protocol: str) -> tuple:
    """Add UFW allow rule"""
    if check_ufw_rule_exists(port, protocol):
        return True, "Rule already exists"
    
    return run_command(['ufw', 'allow', f'{port}/{protocol}'])

def remove_ufw_rule(port: int, protocol: str) -> tuple:
    """Remove UFW rule"""
    return run_command(['ufw', 'delete', 'allow', f'{port}/{protocol}'])

def apply_port_rule(rule: dict, enable: bool) -> dict:
    """Apply or remove all firewall rules for a port forwarding rule"""
    results = {"iptables": [], "ufw": []}
    protocols = ['tcp', 'udp'] if rule['protocol'] == 'both' else [rule['protocol']]
    
    for proto in protocols:
        if enable:
            # Add rules
            success, msg = add_iptables_rule(rule['external_port'], rule['internal_port'], proto)
            results['iptables'].append({"protocol": proto, "success": success, "message": msg})
            
            success, msg = add_ufw_rule(rule['external_port'], proto)
            results['ufw'].append({"protocol": proto, "success": success, "message": msg})
        else:
            # Remove rules
            success, msg = remove_iptables_rule(rule['external_port'], rule['internal_port'], proto)
            results['iptables'].append({"protocol": proto, "success": success, "message": msg})
            
            success, msg = remove_ufw_rule(rule['external_port'], proto)
            results['ufw'].append({"protocol": proto, "success": success, "message": msg})
    
    return results

# ==================== STARTUP ====================

@app.on_event("startup")
async def startup_event():
    """Initialize database and default admin user"""
    # Create indexes
    await db.users.create_index("username", unique=True)
    await db.users.create_index("id", unique=True)
    await db.port_rules.create_index("id", unique=True)
    await db.port_rules.create_index("external_port")
    
    # Check if admin user exists
    admin = await db.users.find_one({"username": "admin"})
    if not admin:
        admin_user = {
            "id": str(uuid.uuid4()),
            "username": "admin",
            "password_hash": hash_password("admin"),
            "role": "admin",
            "must_change_password": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "last_login": None
        }
        await db.users.insert_one(admin_user)
        logger.info("Default admin user created (username: admin, password: admin)")
    
    # Apply all enabled port rules on startup
    enabled_rules = await db.port_rules.find({"enabled": True}, {"_id": 0}).to_list(1000)
    for rule in enabled_rules:
        logger.info(f"Applying rule on startup: {rule['name']} (port {rule['external_port']})")
        apply_port_rule(rule, True)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()

# ==================== AUTH ROUTES ====================

@api_router.post("/auth/login", response_model=TokenResponse)
async def login(credentials: UserLogin):
    user = await db.users.find_one({"username": credentials.username}, {"_id": 0})
    if not user or not verify_password(credentials.password, user['password_hash']):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    
    # Update last login
    await db.users.update_one(
        {"id": user['id']},
        {"$set": {"last_login": datetime.now(timezone.utc).isoformat()}}
    )
    
    token = create_token(user['id'], user['username'], user['role'])
    
    return TokenResponse(
        access_token=token,
        user=UserResponse(
            id=user['id'],
            username=user['username'],
            role=user['role'],
            must_change_password=user['must_change_password'],
            created_at=user['created_at'],
            last_login=user.get('last_login')
        )
    )

@api_router.post("/auth/change-password")
async def change_password(data: PasswordChange, user: dict = Depends(get_current_user)):
    if not verify_password(data.current_password, user['password_hash']):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    
    new_hash = hash_password(data.new_password)
    await db.users.update_one(
        {"id": user['id']},
        {"$set": {"password_hash": new_hash, "must_change_password": False}}
    )
    
    return {"message": "Password changed successfully"}

@api_router.get("/auth/me", response_model=UserResponse)
async def get_current_user_info(user: dict = Depends(get_current_user)):
    return UserResponse(
        id=user['id'],
        username=user['username'],
        role=user['role'],
        must_change_password=user['must_change_password'],
        created_at=user['created_at'],
        last_login=user.get('last_login')
    )

# ==================== USER MANAGEMENT ROUTES ====================

@api_router.post("/users", response_model=UserResponse)
async def create_user(data: UserCreate, admin: dict = Depends(require_admin)):
    # Check if username exists
    existing = await db.users.find_one({"username": data.username})
    if existing:
        raise HTTPException(status_code=400, detail="Username already exists")
    
    new_user = {
        "id": str(uuid.uuid4()),
        "username": data.username,
        "password_hash": hash_password(data.password),
        "role": data.role,
        "must_change_password": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "last_login": None
    }
    await db.users.insert_one(new_user)
    
    return UserResponse(
        id=new_user['id'],
        username=new_user['username'],
        role=new_user['role'],
        must_change_password=new_user['must_change_password'],
        created_at=new_user['created_at'],
        last_login=None
    )

@api_router.get("/users", response_model=List[UserResponse])
async def list_users(admin: dict = Depends(require_admin)):
    users = await db.users.find({}, {"_id": 0, "password_hash": 0}).to_list(1000)
    return [UserResponse(**u) for u in users]

@api_router.delete("/users/{user_id}")
async def delete_user(user_id: str, admin: dict = Depends(require_admin)):
    if admin['id'] == user_id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")
    
    result = await db.users.delete_one({"id": user_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {"message": "User deleted successfully"}

# ==================== PORT RULES ROUTES ====================

@api_router.post("/rules", response_model=PortRuleResponse)
async def create_port_rule(data: PortRuleCreate, user: dict = Depends(get_current_user)):
    # Check if port already exists
    existing = await db.port_rules.find_one({"external_port": data.external_port})
    if existing:
        raise HTTPException(status_code=400, detail=f"Port {data.external_port} is already configured")
    
    is_outside_range = data.external_port < SAFE_PORT_MIN or data.external_port > SAFE_PORT_MAX
    
    new_rule = {
        "id": str(uuid.uuid4()),
        "name": data.name,
        "external_port": data.external_port,
        "internal_port": data.internal_port,
        "protocol": data.protocol,
        "description": data.description or "",
        "enabled": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": user['username'],
        "is_outside_safe_range": is_outside_range
    }
    await db.port_rules.insert_one(new_rule)
    
    return PortRuleResponse(**new_rule)

@api_router.get("/rules", response_model=List[PortRuleResponse])
async def list_port_rules(user: dict = Depends(get_current_user)):
    rules = await db.port_rules.find({}, {"_id": 0}).to_list(1000)
    return [PortRuleResponse(**r) for r in rules]

@api_router.get("/rules/{rule_id}", response_model=PortRuleResponse)
async def get_port_rule(rule_id: str, user: dict = Depends(get_current_user)):
    rule = await db.port_rules.find_one({"id": rule_id}, {"_id": 0})
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    return PortRuleResponse(**rule)

@api_router.put("/rules/{rule_id}", response_model=PortRuleResponse)
async def update_port_rule(rule_id: str, data: PortRuleUpdate, user: dict = Depends(get_current_user)):
    rule = await db.port_rules.find_one({"id": rule_id}, {"_id": 0})
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    
    # Check if external port is being changed and if new port conflicts
    if 'external_port' in update_data and update_data['external_port'] != rule['external_port']:
        existing = await db.port_rules.find_one({"external_port": update_data['external_port']})
        if existing:
            raise HTTPException(status_code=400, detail=f"Port {update_data['external_port']} is already configured")
        update_data['is_outside_safe_range'] = update_data['external_port'] < SAFE_PORT_MIN or update_data['external_port'] > SAFE_PORT_MAX
    
    if update_data:
        await db.port_rules.update_one({"id": rule_id}, {"$set": update_data})
    
    updated_rule = await db.port_rules.find_one({"id": rule_id}, {"_id": 0})
    return PortRuleResponse(**updated_rule)

@api_router.delete("/rules/{rule_id}")
async def delete_port_rule(rule_id: str, user: dict = Depends(get_current_user)):
    rule = await db.port_rules.find_one({"id": rule_id}, {"_id": 0})
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    # Remove firewall rules if enabled
    if rule['enabled']:
        apply_port_rule(rule, False)
    
    await db.port_rules.delete_one({"id": rule_id})
    return {"message": "Rule deleted successfully"}

@api_router.post("/rules/{rule_id}/toggle")
async def toggle_port_rule(rule_id: str, user: dict = Depends(get_current_user)):
    rule = await db.port_rules.find_one({"id": rule_id}, {"_id": 0})
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    new_state = not rule['enabled']
    
    # Apply or remove firewall rules
    results = apply_port_rule(rule, new_state)
    
    # Update database
    await db.port_rules.update_one({"id": rule_id}, {"$set": {"enabled": new_state}})
    
    return {
        "enabled": new_state,
        "message": f"Rule {'enabled' if new_state else 'disabled'}",
        "firewall_results": results
    }

# ==================== SYSTEM STATUS ROUTES ====================

@api_router.get("/system/status", response_model=SystemStatus)
async def get_system_status(user: dict = Depends(get_current_user)):
    # Check if iptables is available
    iptables_ok, _ = run_command(['which', 'iptables']) if not SIMULATION_MODE else (True, "simulated")
    ufw_ok, _ = run_command(['which', 'ufw']) if not SIMULATION_MODE else (True, "simulated")
    
    return SystemStatus(
        iptables_available=iptables_ok or SIMULATION_MODE,
        ufw_available=ufw_ok or SIMULATION_MODE,
        wireguard_interface=WIREGUARD_INTERFACE,
        destination_ip=WIREGUARD_DEST_IP,
        simulation_mode=SIMULATION_MODE
    )

@api_router.get("/system/stats")
async def get_system_stats(user: dict = Depends(get_current_user)):
    total_rules = await db.port_rules.count_documents({})
    active_rules = await db.port_rules.count_documents({"enabled": True})
    total_users = await db.users.count_documents({})
    
    return {
        "total_rules": total_rules,
        "active_rules": active_rules,
        "inactive_rules": total_rules - active_rules,
        "total_users": total_users
    }

@api_router.get("/")
async def root():
    return {"message": "Port Forwarding Manager API", "version": "1.0.0"}

# Include router and configure middleware
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)
