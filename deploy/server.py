from fastapi import FastAPI, APIRouter, HTTPException, Depends, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
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
import sqlite3
import json
from contextlib import contextmanager

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Static files directory for frontend
STATIC_DIR = ROOT_DIR / "static"

# SQLite Database Configuration
DB_PATH = os.environ.get('DB_PATH', str(ROOT_DIR / 'port_forward.db'))

# JWT Configuration
JWT_SECRET = os.environ.get('JWT_SECRET', 'port-forward-manager-secret-key-change-in-production')
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24

# WireGuard Configuration
WIREGUARD_INTERFACE = os.environ.get('WIREGUARD_INTERFACE', 'wg0')
WIREGUARD_DEST_IP = os.environ.get('WIREGUARD_DEST_IP', '10.0.0.2')
WIREGUARD_DOCKER_CONTAINER = os.environ.get('WIREGUARD_DOCKER_CONTAINER', '')  # Set to container name if WG runs in Docker
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

# ==================== DATABASE SETUP ====================

@contextmanager
def get_db():
    """Context manager for database connections"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_database():
    """Initialize SQLite database with required tables"""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Create users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user',
                must_change_password INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                last_login TEXT
            )
        ''')
        
        # Create port_rules table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS port_rules (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                external_port INTEGER NOT NULL UNIQUE,
                internal_port INTEGER NOT NULL,
                protocol TEXT NOT NULL DEFAULT 'both',
                description TEXT DEFAULT '',
                enabled INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                created_by TEXT NOT NULL,
                is_outside_safe_range INTEGER NOT NULL DEFAULT 0
            )
        ''')
        
        # Create settings table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        ''')
        
        # Create indexes
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_port_rules_external_port ON port_rules(external_port)')

def dict_from_row(row):
    """Convert sqlite3.Row to dictionary"""
    if row is None:
        return None
    return dict(row)

# ==================== MODELS ====================

class UserCreate(BaseModel):
    username: str
    password: str
    role: str = "user"

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
    protocol: str = "both"
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
        
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
            user = dict_from_row(cursor.fetchone())
        
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        
        user['must_change_password'] = bool(user['must_change_password'])
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

SIMULATION_MODE = os.environ.get('SIMULATION_MODE', 'true').lower() == 'true'
PUBLIC_INTERFACE = os.environ.get('PUBLIC_INTERFACE', 'eth0')  # The interface receiving public traffic

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

def check_iptables_nat_rule_exists(external_port: int, internal_port: int, protocol: str) -> bool:
    """Check if an iptables NAT PREROUTING rule already exists"""
    if SIMULATION_MODE:
        return False
    
    # Check for the DNAT rule
    success, output = run_command([
        'iptables', '-t', 'nat', '-C', 'PREROUTING',
        '-i', PUBLIC_INTERFACE, '-p', protocol,
        '--dport', str(external_port),
        '-j', 'DNAT', '--to-destination', f'{WIREGUARD_DEST_IP}:{internal_port}'
    ])
    return success

def check_iptables_forward_rule_exists(internal_port: int, protocol: str) -> bool:
    """Check if an iptables FORWARD rule already exists"""
    if SIMULATION_MODE:
        return False
    
    success, output = run_command([
        'iptables', '-C', 'FORWARD',
        '-i', PUBLIC_INTERFACE, '-o', WIREGUARD_INTERFACE,
        '-p', protocol, '--dport', str(internal_port),
        '-d', WIREGUARD_DEST_IP,
        '-j', 'ACCEPT'
    ])
    return success

def check_ufw_route_rule_exists(port: int, protocol: str) -> bool:
    """Check if a UFW route rule already exists"""
    if SIMULATION_MODE:
        return False
    
    success, output = run_command(['ufw', 'status'])
    if success:
        # Look for route rules in the format: 10.0.0.2 60002/tcp on wg0 ALLOW FWD
        pattern = f"{WIREGUARD_DEST_IP} {port}/{protocol}"
        return pattern.lower() in output.lower()
    return False

def add_iptables_rules(external_port: int, internal_port: int, protocol: str) -> tuple:
    """Add iptables NAT PREROUTING and FORWARD rules for port forwarding"""
    results = []
    
    # 1. Add PREROUTING DNAT rule (redirect incoming traffic to wireguard destination)
    if not check_iptables_nat_rule_exists(external_port, internal_port, protocol):
        success, msg = run_command([
            'iptables', '-t', 'nat', '-A', 'PREROUTING',
            '-i', PUBLIC_INTERFACE, '-p', protocol,
            '--dport', str(external_port),
            '-j', 'DNAT', '--to-destination', f'{WIREGUARD_DEST_IP}:{internal_port}'
        ])
        results.append(f"NAT PREROUTING: {msg if not success else 'added'}")
    else:
        results.append("NAT PREROUTING: already exists")
    
    # 2. Add FORWARD rule to allow the forwarded traffic
    if not check_iptables_forward_rule_exists(internal_port, protocol):
        success, msg = run_command([
            'iptables', '-A', 'FORWARD',
            '-i', PUBLIC_INTERFACE, '-o', WIREGUARD_INTERFACE,
            '-p', protocol, '--dport', str(internal_port),
            '-d', WIREGUARD_DEST_IP,
            '-j', 'ACCEPT'
        ])
        results.append(f"FORWARD: {msg if not success else 'added'}")
    else:
        results.append("FORWARD: already exists")
    
    # 3. Add FORWARD rule for return traffic (ESTABLISHED,RELATED)
    # This is usually handled by conntrack but let's be explicit
    success, _ = run_command([
        'iptables', '-C', 'FORWARD',
        '-i', WIREGUARD_INTERFACE, '-o', PUBLIC_INTERFACE,
        '-m', 'state', '--state', 'ESTABLISHED,RELATED',
        '-j', 'ACCEPT'
    ])
    if not success:
        run_command([
            'iptables', '-A', 'FORWARD',
            '-i', WIREGUARD_INTERFACE, '-o', PUBLIC_INTERFACE,
            '-m', 'state', '--state', 'ESTABLISHED,RELATED',
            '-j', 'ACCEPT'
        ])
        results.append("FORWARD return: added")
    
    return True, "; ".join(results)

def remove_iptables_rules(external_port: int, internal_port: int, protocol: str) -> tuple:
    """Remove iptables NAT PREROUTING and FORWARD rules"""
    results = []
    
    # Remove PREROUTING DNAT rule
    success, msg = run_command([
        'iptables', '-t', 'nat', '-D', 'PREROUTING',
        '-i', PUBLIC_INTERFACE, '-p', protocol,
        '--dport', str(external_port),
        '-j', 'DNAT', '--to-destination', f'{WIREGUARD_DEST_IP}:{internal_port}'
    ])
    results.append(f"NAT PREROUTING: {'removed' if success else msg}")
    
    # Remove FORWARD rule
    success, msg = run_command([
        'iptables', '-D', 'FORWARD',
        '-i', PUBLIC_INTERFACE, '-o', WIREGUARD_INTERFACE,
        '-p', protocol, '--dport', str(internal_port),
        '-d', WIREGUARD_DEST_IP,
        '-j', 'ACCEPT'
    ])
    results.append(f"FORWARD: {'removed' if success else msg}")
    
    return True, "; ".join(results)

def add_ufw_rules(external_port: int, internal_port: int, protocol: str) -> tuple:
    """Add UFW rules for port forwarding"""
    results = []
    
    # 1. Allow incoming traffic on the external port
    success, msg = run_command(['ufw', 'allow', f'{external_port}/{protocol}'])
    results.append(f"allow {external_port}/{protocol}: {'ok' if success else msg}")
    
    # 2. Add route rule for forwarding (UFW's way of allowing forwarded traffic)
    if not check_ufw_route_rule_exists(internal_port, protocol):
        success, msg = run_command([
            'ufw', 'route', 'allow', 'proto', protocol,
            'from', 'any', 'to', WIREGUARD_DEST_IP, 'port', str(internal_port)
        ])
        results.append(f"route to {WIREGUARD_DEST_IP}:{internal_port}: {'ok' if success else msg}")
    else:
        results.append(f"route to {WIREGUARD_DEST_IP}:{internal_port}: already exists")
    
    return True, "; ".join(results)

def remove_ufw_rules(external_port: int, internal_port: int, protocol: str) -> tuple:
    """Remove UFW rules for port forwarding"""
    results = []
    
    # Remove allow rule
    success, msg = run_command(['ufw', 'delete', 'allow', f'{external_port}/{protocol}'])
    results.append(f"delete allow {external_port}/{protocol}: {'ok' if success else msg}")
    
    # Remove route rule
    success, msg = run_command([
        'ufw', 'route', 'delete', 'allow', 'proto', protocol,
        'from', 'any', 'to', WIREGUARD_DEST_IP, 'port', str(internal_port)
    ])
    results.append(f"delete route to {WIREGUARD_DEST_IP}:{internal_port}: {'ok' if success else msg}")
    
    return True, "; ".join(results)

def apply_port_rule(rule: dict, enable: bool) -> dict:
    """Apply or remove all firewall rules for a port forwarding rule"""
    results = {"iptables": [], "ufw": []}
    protocols = ['tcp', 'udp'] if rule['protocol'] == 'both' else [rule['protocol']]
    
    for proto in protocols:
        if enable:
            success, msg = add_iptables_rules(rule['external_port'], rule['internal_port'], proto)
            results['iptables'].append({"protocol": proto, "success": success, "message": msg})
            
            success, msg = add_ufw_rules(rule['external_port'], rule['internal_port'], proto)
            results['ufw'].append({"protocol": proto, "success": success, "message": msg})
        else:
            success, msg = remove_iptables_rules(rule['external_port'], rule['internal_port'], proto)
            results['iptables'].append({"protocol": proto, "success": success, "message": msg})
            
            success, msg = remove_ufw_rules(rule['external_port'], rule['internal_port'], proto)
            results['ufw'].append({"protocol": proto, "success": success, "message": msg})
    
    return results

# ==================== STARTUP ====================

@app.on_event("startup")
async def startup_event():
    """Initialize database and default admin user"""
    init_database()
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Check if admin user exists
        cursor.execute("SELECT * FROM users WHERE username = ?", ("admin",))
        admin = cursor.fetchone()
        
        if not admin:
            admin_id = str(uuid.uuid4())
            cursor.execute('''
                INSERT INTO users (id, username, password_hash, role, must_change_password, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                admin_id,
                "admin",
                hash_password("admin"),
                "admin",
                1,
                datetime.now(timezone.utc).isoformat()
            ))
            logger.info("Default admin user created (username: admin, password: admin)")
        
        # Apply all enabled port rules on startup
        cursor.execute("SELECT * FROM port_rules WHERE enabled = 1")
        enabled_rules = [dict_from_row(row) for row in cursor.fetchall()]
        
    for rule in enabled_rules:
        rule['enabled'] = bool(rule['enabled'])
        rule['is_outside_safe_range'] = bool(rule['is_outside_safe_range'])
        logger.info(f"Applying rule on startup: {rule['name']} (port {rule['external_port']})")
        apply_port_rule(rule, True)

# ==================== AUTH ROUTES ====================

@api_router.post("/auth/login", response_model=TokenResponse)
async def login(credentials: UserLogin):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ?", (credentials.username,))
        user = dict_from_row(cursor.fetchone())
    
    if not user or not verify_password(credentials.password, user['password_hash']):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    
    # Update last login
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE users SET last_login = ? WHERE id = ?",
            (datetime.now(timezone.utc).isoformat(), user['id'])
        )
    
    token = create_token(user['id'], user['username'], user['role'])
    
    return TokenResponse(
        access_token=token,
        user=UserResponse(
            id=user['id'],
            username=user['username'],
            role=user['role'],
            must_change_password=bool(user['must_change_password']),
            created_at=user['created_at'],
            last_login=user.get('last_login')
        )
    )

@api_router.post("/auth/change-password")
async def change_password(data: PasswordChange, user: dict = Depends(get_current_user)):
    if not verify_password(data.current_password, user['password_hash']):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    
    new_hash = hash_password(data.new_password)
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE users SET password_hash = ?, must_change_password = 0 WHERE id = ?",
            (new_hash, user['id'])
        )
    
    return {"message": "Password changed successfully"}

@api_router.get("/auth/me", response_model=UserResponse)
async def get_current_user_info(user: dict = Depends(get_current_user)):
    return UserResponse(
        id=user['id'],
        username=user['username'],
        role=user['role'],
        must_change_password=bool(user['must_change_password']),
        created_at=user['created_at'],
        last_login=user.get('last_login')
    )

# ==================== USER MANAGEMENT ROUTES ====================

@api_router.post("/users", response_model=UserResponse)
async def create_user(data: UserCreate, admin: dict = Depends(require_admin)):
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Check if username exists
        cursor.execute("SELECT id FROM users WHERE username = ?", (data.username,))
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="Username already exists")
        
        new_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc).isoformat()
        
        cursor.execute('''
            INSERT INTO users (id, username, password_hash, role, must_change_password, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            new_id,
            data.username,
            hash_password(data.password),
            data.role,
            1,
            created_at
        ))
    
    return UserResponse(
        id=new_id,
        username=data.username,
        role=data.role,
        must_change_password=True,
        created_at=created_at,
        last_login=None
    )

@api_router.get("/users", response_model=List[UserResponse])
async def list_users(admin: dict = Depends(require_admin)):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, role, must_change_password, created_at, last_login FROM users")
        users = [dict_from_row(row) for row in cursor.fetchall()]
    
    return [UserResponse(
        id=u['id'],
        username=u['username'],
        role=u['role'],
        must_change_password=bool(u['must_change_password']),
        created_at=u['created_at'],
        last_login=u.get('last_login')
    ) for u in users]

@api_router.delete("/users/{user_id}")
async def delete_user(user_id: str, admin: dict = Depends(require_admin)):
    if admin['id'] == user_id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="User not found")
    
    return {"message": "User deleted successfully"}

# ==================== PORT RULES ROUTES ====================

@api_router.post("/rules", response_model=PortRuleResponse)
async def create_port_rule(data: PortRuleCreate, user: dict = Depends(get_current_user)):
    is_outside_range = data.external_port < SAFE_PORT_MIN or data.external_port > SAFE_PORT_MAX
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Check if port already exists
        cursor.execute("SELECT id FROM port_rules WHERE external_port = ?", (data.external_port,))
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail=f"Port {data.external_port} is already configured")
        
        new_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc).isoformat()
        
        cursor.execute('''
            INSERT INTO port_rules (id, name, external_port, internal_port, protocol, description, enabled, created_at, created_by, is_outside_safe_range)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            new_id,
            data.name,
            data.external_port,
            data.internal_port,
            data.protocol,
            data.description or "",
            0,
            created_at,
            user['username'],
            1 if is_outside_range else 0
        ))
    
    return PortRuleResponse(
        id=new_id,
        name=data.name,
        external_port=data.external_port,
        internal_port=data.internal_port,
        protocol=data.protocol,
        description=data.description or "",
        enabled=False,
        created_at=created_at,
        created_by=user['username'],
        is_outside_safe_range=is_outside_range
    )

@api_router.get("/rules", response_model=List[PortRuleResponse])
async def list_port_rules(user: dict = Depends(get_current_user)):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM port_rules")
        rules = [dict_from_row(row) for row in cursor.fetchall()]
    
    return [PortRuleResponse(
        id=r['id'],
        name=r['name'],
        external_port=r['external_port'],
        internal_port=r['internal_port'],
        protocol=r['protocol'],
        description=r['description'],
        enabled=bool(r['enabled']),
        created_at=r['created_at'],
        created_by=r['created_by'],
        is_outside_safe_range=bool(r['is_outside_safe_range'])
    ) for r in rules]

@api_router.get("/rules/{rule_id}", response_model=PortRuleResponse)
async def get_port_rule(rule_id: str, user: dict = Depends(get_current_user)):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM port_rules WHERE id = ?", (rule_id,))
        rule = dict_from_row(cursor.fetchone())
    
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    return PortRuleResponse(
        id=rule['id'],
        name=rule['name'],
        external_port=rule['external_port'],
        internal_port=rule['internal_port'],
        protocol=rule['protocol'],
        description=rule['description'],
        enabled=bool(rule['enabled']),
        created_at=rule['created_at'],
        created_by=rule['created_by'],
        is_outside_safe_range=bool(rule['is_outside_safe_range'])
    )

@api_router.put("/rules/{rule_id}", response_model=PortRuleResponse)
async def update_port_rule(rule_id: str, data: PortRuleUpdate, user: dict = Depends(get_current_user)):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM port_rules WHERE id = ?", (rule_id,))
        rule = dict_from_row(cursor.fetchone())
        
        if not rule:
            raise HTTPException(status_code=404, detail="Rule not found")
        
        # Build update query dynamically
        updates = []
        values = []
        
        if data.name is not None:
            updates.append("name = ?")
            values.append(data.name)
        
        if data.external_port is not None:
            # Check for conflicts
            cursor.execute("SELECT id FROM port_rules WHERE external_port = ? AND id != ?", (data.external_port, rule_id))
            if cursor.fetchone():
                raise HTTPException(status_code=400, detail=f"Port {data.external_port} is already configured")
            updates.append("external_port = ?")
            values.append(data.external_port)
            updates.append("is_outside_safe_range = ?")
            values.append(1 if (data.external_port < SAFE_PORT_MIN or data.external_port > SAFE_PORT_MAX) else 0)
        
        if data.internal_port is not None:
            updates.append("internal_port = ?")
            values.append(data.internal_port)
        
        if data.protocol is not None:
            updates.append("protocol = ?")
            values.append(data.protocol)
        
        if data.description is not None:
            updates.append("description = ?")
            values.append(data.description)
        
        if data.enabled is not None:
            updates.append("enabled = ?")
            values.append(1 if data.enabled else 0)
        
        if updates:
            values.append(rule_id)
            cursor.execute(f"UPDATE port_rules SET {', '.join(updates)} WHERE id = ?", values)
        
        cursor.execute("SELECT * FROM port_rules WHERE id = ?", (rule_id,))
        updated_rule = dict_from_row(cursor.fetchone())
    
    return PortRuleResponse(
        id=updated_rule['id'],
        name=updated_rule['name'],
        external_port=updated_rule['external_port'],
        internal_port=updated_rule['internal_port'],
        protocol=updated_rule['protocol'],
        description=updated_rule['description'],
        enabled=bool(updated_rule['enabled']),
        created_at=updated_rule['created_at'],
        created_by=updated_rule['created_by'],
        is_outside_safe_range=bool(updated_rule['is_outside_safe_range'])
    )

@api_router.delete("/rules/{rule_id}")
async def delete_port_rule(rule_id: str, user: dict = Depends(get_current_user)):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM port_rules WHERE id = ?", (rule_id,))
        rule = dict_from_row(cursor.fetchone())
        
        if not rule:
            raise HTTPException(status_code=404, detail="Rule not found")
        
        # Remove firewall rules if enabled
        if rule['enabled']:
            rule['enabled'] = bool(rule['enabled'])
            rule['is_outside_safe_range'] = bool(rule['is_outside_safe_range'])
            apply_port_rule(rule, False)
        
        cursor.execute("DELETE FROM port_rules WHERE id = ?", (rule_id,))
    
    return {"message": "Rule deleted successfully"}

@api_router.post("/rules/{rule_id}/toggle")
async def toggle_port_rule(rule_id: str, user: dict = Depends(get_current_user)):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM port_rules WHERE id = ?", (rule_id,))
        rule = dict_from_row(cursor.fetchone())
        
        if not rule:
            raise HTTPException(status_code=404, detail="Rule not found")
        
        rule['enabled'] = bool(rule['enabled'])
        rule['is_outside_safe_range'] = bool(rule['is_outside_safe_range'])
        new_state = not rule['enabled']
        
        # Apply or remove firewall rules
        results = apply_port_rule(rule, new_state)
        
        # Update database
        cursor.execute("UPDATE port_rules SET enabled = ? WHERE id = ?", (1 if new_state else 0, rule_id))
    
    return {
        "enabled": new_state,
        "message": f"Rule {'enabled' if new_state else 'disabled'}",
        "firewall_results": results
    }

# ==================== SYSTEM STATUS ROUTES ====================

@api_router.get("/system/status", response_model=SystemStatus)
async def get_system_status(user: dict = Depends(get_current_user)):
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
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM port_rules")
        total_rules = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(*) as count FROM port_rules WHERE enabled = 1")
        active_rules = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(*) as count FROM users")
        total_users = cursor.fetchone()['count']
    
    return {
        "total_rules": total_rules,
        "active_rules": active_rules,
        "inactive_rules": total_rules - active_rules,
        "total_users": total_users
    }

@api_router.get("/system/wireguard")
async def get_wireguard_status(user: dict = Depends(get_current_user)):
    """Get WireGuard tunnel status including up/down state and last handshake"""
    if SIMULATION_MODE:
        # Return simulated data
        return {
            "status": "up",
            "interface": WIREGUARD_INTERFACE,
            "public_key": "SIMULATED_PUBLIC_KEY",
            "endpoint": "simulated.endpoint:51820",
            "last_handshake": "simulated - 45 seconds ago",
            "last_handshake_timestamp": None,
            "transfer_rx": "1.5 GiB",
            "transfer_tx": "500 MiB",
            "simulation_mode": True,
            "docker_container": WIREGUARD_DOCKER_CONTAINER or None
        }
    
    # Check if WireGuard is running in Docker
    if WIREGUARD_DOCKER_CONTAINER:
        # Check if Docker container is running
        success, output = run_command(['docker', 'inspect', '-f', '{{.State.Running}}', WIREGUARD_DOCKER_CONTAINER])
        if not success or 'true' not in output.lower():
            return {
                "status": "down",
                "interface": WIREGUARD_INTERFACE,
                "error": f"Docker container '{WIREGUARD_DOCKER_CONTAINER}' is not running",
                "simulation_mode": False,
                "docker_container": WIREGUARD_DOCKER_CONTAINER
            }
        
        # Get WireGuard status from inside the Docker container
        success, output = run_command(['docker', 'exec', WIREGUARD_DOCKER_CONTAINER, 'wg', 'show', WIREGUARD_INTERFACE])
        if not success:
            return {
                "status": "down",
                "interface": WIREGUARD_INTERFACE,
                "error": output,
                "simulation_mode": False,
                "docker_container": WIREGUARD_DOCKER_CONTAINER
            }
    else:
        # WireGuard running on host - check if interface exists
        success, output = run_command(['ip', 'link', 'show', WIREGUARD_INTERFACE])
        if not success:
            return {
                "status": "down",
                "interface": WIREGUARD_INTERFACE,
                "error": "Interface not found",
                "simulation_mode": False,
                "docker_container": None
            }
        
        # Get WireGuard status from host
        success, output = run_command(['wg', 'show', WIREGUARD_INTERFACE])
        if not success:
            return {
                "status": "down",
                "interface": WIREGUARD_INTERFACE,
                "error": output,
                "simulation_mode": False,
                "docker_container": None
            }
    
    # Parse the wg show output
    result = {
        "status": "up",
        "interface": WIREGUARD_INTERFACE,
        "public_key": None,
        "endpoint": None,
        "last_handshake": None,
        "last_handshake_timestamp": None,
        "transfer_rx": None,
        "transfer_tx": None,
        "simulation_mode": False,
        "docker_container": WIREGUARD_DOCKER_CONTAINER or None
    }
    
    lines = output.strip().split('\n')
    for line in lines:
        line = line.strip()
        if line.startswith('public key:'):
            result['public_key'] = line.split(':', 1)[1].strip()
        elif line.startswith('endpoint:'):
            result['endpoint'] = line.split(':', 1)[1].strip()
        elif line.startswith('latest handshake:'):
            handshake = line.split(':', 1)[1].strip()
            result['last_handshake'] = handshake
            # If no handshake, tunnel might be down
            if 'never' in handshake.lower():
                result['status'] = 'waiting'
        elif line.startswith('transfer:'):
            transfer = line.split(':', 1)[1].strip()
            parts = transfer.split(',')
            if len(parts) >= 2:
                result['transfer_rx'] = parts[0].strip().replace('received', '').strip()
                result['transfer_tx'] = parts[1].strip().replace('sent', '').strip()
    
    return result

# ==================== SETTINGS ROUTES ====================

class PortRangeSettings(BaseModel):
    safe_port_min: int
    safe_port_max: int

@api_router.get("/settings/port-range")
async def get_port_range_settings(user: dict = Depends(get_current_user)):
    """Get the current safe port range settings"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT key, value FROM settings WHERE key IN ('safe_port_min', 'safe_port_max')")
        rows = cursor.fetchall()
        
        settings = {row['key']: int(row['value']) for row in rows}
    
    return {
        "safe_port_min": settings.get('safe_port_min', SAFE_PORT_MIN),
        "safe_port_max": settings.get('safe_port_max', SAFE_PORT_MAX)
    }

@api_router.put("/settings/port-range")
async def update_port_range_settings(data: PortRangeSettings, admin: dict = Depends(require_admin)):
    """Update the safe port range settings (admin only)"""
    if data.safe_port_min >= data.safe_port_max:
        raise HTTPException(status_code=400, detail="Minimum port must be less than maximum port")
    
    if data.safe_port_min < 1 or data.safe_port_max > 65535:
        raise HTTPException(status_code=400, detail="Port range must be between 1 and 65535")
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Upsert settings
        cursor.execute('''
            INSERT OR REPLACE INTO settings (key, value, updated_at)
            VALUES ('safe_port_min', ?, ?)
        ''', (str(data.safe_port_min), datetime.now(timezone.utc).isoformat()))
        
        cursor.execute('''
            INSERT OR REPLACE INTO settings (key, value, updated_at)
            VALUES ('safe_port_max', ?, ?)
        ''', (str(data.safe_port_max), datetime.now(timezone.utc).isoformat()))
        
        # Update is_outside_safe_range for all existing rules
        cursor.execute('''
            UPDATE port_rules 
            SET is_outside_safe_range = CASE 
                WHEN external_port < ? OR external_port > ? THEN 1 
                ELSE 0 
            END
        ''', (data.safe_port_min, data.safe_port_max))
    
    return {
        "message": "Port range settings updated",
        "safe_port_min": data.safe_port_min,
        "safe_port_max": data.safe_port_max
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

# ==================== STATIC FILE SERVING ====================
# Serve frontend static files if they exist

# Mount static assets (JS, CSS, images)
if STATIC_DIR.exists() and (STATIC_DIR / "static").exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR / "static"), name="static")

# Serve favicon
@app.get("/favicon.svg")
async def serve_favicon():
    """Serve the favicon"""
    favicon_file = STATIC_DIR / "favicon.svg"
    if favicon_file.exists():
        return FileResponse(favicon_file, media_type="image/svg+xml")
    raise HTTPException(status_code=404, detail="Favicon not found")

@app.get("/favicon.ico")
async def serve_favicon_ico():
    """Serve favicon.ico (redirect to svg or return svg)"""
    favicon_file = STATIC_DIR / "favicon.svg"
    if favicon_file.exists():
        return FileResponse(favicon_file, media_type="image/svg+xml")
    raise HTTPException(status_code=404, detail="Favicon not found")

# Serve index.html for all non-API routes (SPA support)
@app.get("/{full_path:path}")
async def serve_spa(request: Request, full_path: str):
    """Serve the React SPA for all non-API routes"""
    # Don't intercept API routes
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="Not Found")
    
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    
    # If no frontend files, return a simple HTML page with instructions
    return HTMLResponse(content="""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Port Forward Manager</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: 'IBM Plex Sans', -apple-system, sans-serif; 
            background: #09090B; 
            color: #F8FAFC; 
            min-height: 100vh; 
            display: flex; 
            align-items: center; 
            justify-content: center; 
            padding: 20px;
        }
        .container { max-width: 600px; text-align: center; }
        h1 { color: #3B82F6; margin-bottom: 20px; font-size: 2rem; }
        p { color: #94A3B8; margin-bottom: 15px; line-height: 1.6; }
        code { 
            background: #1E1E22; 
            padding: 2px 8px; 
            border-radius: 4px; 
            font-family: 'JetBrains Mono', monospace;
            color: #06B6D4;
        }
        .api-link { 
            display: inline-block; 
            margin-top: 20px; 
            padding: 10px 20px; 
            background: #3B82F6; 
            color: white; 
            text-decoration: none; 
            border-radius: 4px;
        }
        .api-link:hover { background: #2563EB; }
        .status { 
            margin-top: 30px; 
            padding: 15px; 
            background: #10B98120; 
            border: 1px solid #10B981; 
            border-radius: 4px;
        }
        .status-title { color: #10B981; font-weight: 600; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Port Forward Manager</h1>
        <div class="status">
            <p class="status-title">✓ Backend API is running!</p>
        </div>
        <p style="margin-top: 20px;">The frontend files are not installed yet.</p>
        <p>To complete setup, copy the frontend build files to:</p>
        <p><code>/opt/port-forward-manager/backend/static/</code></p>
        <p style="margin-top: 20px;">Or test the API directly:</p>
        <a href="/api/" class="api-link">View API Status</a>
    </div>
</body>
</html>
    """, status_code=200)
