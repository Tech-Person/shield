#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────
# Shield — Debian/Ubuntu Deployment Script
# Installs and configures the full stack as systemd services.
#
# DIRECTORY STRUCTURE REQUIRED:
#   shield/
#   ├── backend/
#   ├── frontend/
#   └── deploy/
#       └── install.sh  (this file)
#
# Run as root:  sudo bash deploy/install.sh
# ──────────────────────────────────────────────────────────────
set -uo pipefail

# ── Colour helpers ──
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
log()  { echo -e "${GREEN}[Shield]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
err()  { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

# ── Pre-flight checks ──
[[ $EUID -ne 0 ]] && err "This script must be run as root (sudo bash deploy/install.sh)"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

[[ ! -d "${PROJECT_ROOT}/backend" ]] && err "Missing backend/ directory at: ${PROJECT_ROOT}/backend"
[[ ! -d "${PROJECT_ROOT}/frontend" ]] && err "Missing frontend/ directory at: ${PROJECT_ROOT}/frontend"
[[ ! -f "${PROJECT_ROOT}/backend/server.py" ]] && err "backend/server.py not found."
[[ ! -f "${PROJECT_ROOT}/frontend/package.json" ]] && err "frontend/package.json not found."

log "Source directory: ${PROJECT_ROOT}"

# ──────────────────────────────────────────────────────────────
# INTERACTIVE SETUP
# ──────────────────────────────────────────────────────────────
echo ""
echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${CYAN}  Shield — Installation Setup${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
echo ""

# Domain
read -rp "$(echo -e "${CYAN}Domain name${NC} (e.g. chat.example.com, or 'localhost' for local): ")" INPUT_DOMAIN
DOMAIN="${INPUT_DOMAIN:-localhost}"

# Admin email
DEFAULT_ADMIN_EMAIL="admin@shield.local"
read -rp "$(echo -e "${CYAN}Admin email${NC} [${DEFAULT_ADMIN_EMAIL}]: ")" INPUT_ADMIN_EMAIL
ADMIN_EMAIL="${INPUT_ADMIN_EMAIL:-$DEFAULT_ADMIN_EMAIL}"

# Admin password
while true; do
    read -rsp "$(echo -e "${CYAN}Admin password${NC} (min 8 chars): ")" INPUT_ADMIN_PASSWORD
    echo ""
    if [[ ${#INPUT_ADMIN_PASSWORD} -ge 8 ]]; then
        ADMIN_PASSWORD="${INPUT_ADMIN_PASSWORD}"
        break
    elif [[ -z "${INPUT_ADMIN_PASSWORD}" ]]; then
        ADMIN_PASSWORD="$(openssl rand -base64 16)"
        echo -e "  ${YELLOW}Generated password:${NC} ${ADMIN_PASSWORD}"
        break
    else
        echo -e "  ${RED}Password must be at least 8 characters. Try again.${NC}"
    fi
done

# Install directory
read -rp "$(echo -e "${CYAN}Install directory${NC} [/opt/shield]: ")" INPUT_DIR
INSTALL_DIR="${INPUT_DIR:-/opt/shield}"

echo ""
echo -e "${GREEN}Configuration:${NC}"
echo -e "  Domain:     ${DOMAIN}"
echo -e "  Admin:      ${ADMIN_EMAIL}"
echo -e "  Install to: ${INSTALL_DIR}"
echo ""
read -rp "Proceed with installation? [Y/n]: " CONFIRM
[[ "${CONFIRM,,}" == "n" ]] && echo "Aborted." && exit 0

# ── Internal config ──
BACKEND_PORT="8001"
JWT_SECRET="$(openssl rand -hex 32)"
MONGO_DB_NAME="shield"

log "Installing Shield to ${INSTALL_DIR}"

# ── Step 1: System packages ──
log "Step 1/9 — Installing system dependencies..."
apt-get update -qq 2>/dev/null || warn "apt-get update had warnings (non-fatal)"

apt-get install -y -qq \
    curl wget gnupg2 \
    build-essential python3 python3-pip python3-venv \
    nginx certbot python3-certbot-nginx \
    git jq unzip 2>/dev/null || {
    warn "Some packages unavailable, trying minimal set..."
    apt-get install -y -qq curl wget gnupg2 python3 python3-pip python3-venv nginx git jq 2>/dev/null || err "Failed to install base packages."
}

# ── Step 2: Node.js 20.x ──
if ! command -v node &>/dev/null || [[ "$(node -v | cut -d. -f1 | tr -d v)" -lt 18 ]]; then
    log "Step 2/9 — Installing Node.js 20.x..."
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - > /dev/null 2>&1
    apt-get install -y -qq nodejs > /dev/null
else
    log "Step 2/9 — Node.js $(node -v) already installed, skipping."
fi

if ! command -v yarn &>/dev/null; then
    npm install -g yarn > /dev/null 2>&1
fi

# ── Step 3: MongoDB 7.0 ──
if ! command -v mongod &>/dev/null; then
    log "Step 3/9 — Installing MongoDB 7.0..."

    # Clean up any broken state from previous attempts
    rm -f /usr/share/keyrings/mongodb-server-7.0.gpg 2>/dev/null
    rm -f /etc/apt/sources.list.d/mongodb-org-7.0.list 2>/dev/null

    # Import GPG key (--batch avoids overwrite prompts)
    curl -fsSL https://www.mongodb.org/static/pgp/server-7.0.asc | \
        gpg --batch --yes --dearmor -o /usr/share/keyrings/mongodb-server-7.0.gpg

    # Detect OS and pick the right repo
    source /etc/os-release 2>/dev/null || true
    MONGO_INSTALLED=false

    if [[ "${ID:-}" == "debian" ]]; then
        # For Debian: use bookworm repo (works on bookworm + trixie)
        log "  Detected Debian — using bookworm repo..."
        echo "deb [arch=amd64,arm64 signed-by=/usr/share/keyrings/mongodb-server-7.0.gpg] https://repo.mongodb.org/apt/debian bookworm/mongodb-org/7.0 main" \
            > /etc/apt/sources.list.d/mongodb-org-7.0.list

        apt-get update -qq 2>/dev/null || true
        if apt-get install -y -qq mongodb-org > /dev/null 2>&1; then
            MONGO_INSTALLED=true
        fi
    fi

    if [[ "${MONGO_INSTALLED}" != "true" ]]; then
        # Fallback: try Ubuntu jammy repo (works on Ubuntu and some Debian)
        log "  Trying Ubuntu jammy repo as fallback..."
        echo "deb [arch=amd64,arm64 signed-by=/usr/share/keyrings/mongodb-server-7.0.gpg] https://repo.mongodb.org/apt/ubuntu jammy/mongodb-org/7.0 multiverse" \
            > /etc/apt/sources.list.d/mongodb-org-7.0.list

        apt-get update -qq 2>/dev/null || true
        if apt-get install -y -qq mongodb-org > /dev/null 2>&1; then
            MONGO_INSTALLED=true
        fi
    fi

    if [[ "${MONGO_INSTALLED}" != "true" ]]; then
        rm -f /etc/apt/sources.list.d/mongodb-org-7.0.list
        apt-get update -qq 2>/dev/null || true
        echo ""
        echo -e "${RED}MongoDB could not be installed automatically.${NC}"
        echo -e "Please install MongoDB manually:"
        echo -e "  ${CYAN}https://www.mongodb.com/docs/manual/administration/install-on-linux/${NC}"
        echo ""
        echo -e "After installing, start it and re-run this script:"
        echo -e "  sudo systemctl enable mongod && sudo systemctl start mongod"
        echo -e "  sudo bash deploy/install.sh"
        exit 1
    fi

    systemctl enable mongod 2>/dev/null || true
    systemctl start mongod 2>/dev/null || true
    sleep 3
else
    log "Step 3/9 — MongoDB already installed, ensuring it's running..."
    systemctl enable mongod 2>/dev/null || true
    systemctl start mongod 2>/dev/null || true
fi

# Verify MongoDB
for i in 1 2 3 4 5; do
    if mongosh --quiet --eval "db.runCommand({ping:1})" > /dev/null 2>&1; then
        break
    fi
    if mongosh --quiet --eval "db.runCommand({ping:1})" > /dev/null 2>&1; then
        break
    fi
    warn "MongoDB not ready (attempt $i/5)..."
    sleep 3
done
mongosh --quiet --eval "db.runCommand({ping:1})" > /dev/null 2>&1 || err "MongoDB is not responding.\n  Check: systemctl status mongod\n  Logs:  journalctl -u mongod"
log "MongoDB is running."

# ── Step 4: Copy application files ──
log "Step 4/9 — Setting up application at ${INSTALL_DIR}..."

# Ensure git is available (should be from Step 1)
if ! command -v git &>/dev/null; then
    apt-get install -y -qq git > /dev/null 2>&1 || warn "Could not install git"
fi

if [[ -d "${INSTALL_DIR}/.git" ]]; then
    log "  Existing git repo found. Pulling latest..."
    cd "${INSTALL_DIR}"
    git fetch --all 2>/dev/null
    git reset --hard origin/main 2>/dev/null || git reset --hard origin/master 2>/dev/null || true
elif command -v git &>/dev/null; then
    # Try to clone the repo directly
    config_url=""
    read -rp "$(echo -e "${CYAN}GitHub repo URL${NC} [https://github.com/Tech-Person/shield]: ")" config_url
    config_url="${config_url:-https://github.com/Tech-Person/shield}"

    if git ls-remote "${config_url}" HEAD > /dev/null 2>&1; then
        log "  Cloning from ${config_url}..."
        rm -rf "${INSTALL_DIR}.tmp"
        git clone "${config_url}" "${INSTALL_DIR}.tmp" 2>/dev/null

        # If install dir already has files, preserve .env and venv
        if [[ -d "${INSTALL_DIR}/backend" ]]; then
            [[ -f "${INSTALL_DIR}/backend/.env" ]] && cp "${INSTALL_DIR}/backend/.env" /tmp/shield-backend-env-backup
            [[ -f "${INSTALL_DIR}/frontend/.env" ]] && cp "${INSTALL_DIR}/frontend/.env" /tmp/shield-frontend-env-backup
        fi

        # Move cloned repo into place
        rm -rf "${INSTALL_DIR}/backend" "${INSTALL_DIR}/frontend" "${INSTALL_DIR}/deploy"
        mv "${INSTALL_DIR}.tmp/backend" "${INSTALL_DIR}/backend"
        mv "${INSTALL_DIR}.tmp/frontend" "${INSTALL_DIR}/frontend"
        [[ -d "${INSTALL_DIR}.tmp/deploy" ]] && mv "${INSTALL_DIR}.tmp/deploy" "${INSTALL_DIR}/deploy"
        mv "${INSTALL_DIR}.tmp/.git" "${INSTALL_DIR}/.git"
        rm -rf "${INSTALL_DIR}.tmp"

        # Restore .env backups
        [[ -f /tmp/shield-backend-env-backup ]] && mv /tmp/shield-backend-env-backup "${INSTALL_DIR}/backend/.env"
        [[ -f /tmp/shield-frontend-env-backup ]] && mv /tmp/shield-frontend-env-backup "${INSTALL_DIR}/frontend/.env"
    else
        log "  Repo not accessible. Copying local files..."
        mkdir -p "${INSTALL_DIR}"
        rsync -a --exclude='node_modules' --exclude='build' --exclude='venv' --exclude='__pycache__' --exclude='.git' "${PROJECT_ROOT}/backend/" "${INSTALL_DIR}/backend/" 2>/dev/null || cp -r "${PROJECT_ROOT}/backend" "${INSTALL_DIR}/backend"
        rsync -a --exclude='node_modules' --exclude='build' --exclude='.git' "${PROJECT_ROOT}/frontend/" "${INSTALL_DIR}/frontend/" 2>/dev/null || cp -r "${PROJECT_ROOT}/frontend" "${INSTALL_DIR}/frontend"
        cp -r "${PROJECT_ROOT}/deploy" "${INSTALL_DIR}/deploy" 2>/dev/null || true
    fi
else
    log "  Git not available. Copying local files..."
    mkdir -p "${INSTALL_DIR}"
    rsync -a --exclude='node_modules' --exclude='build' --exclude='venv' --exclude='__pycache__' --exclude='.git' "${PROJECT_ROOT}/backend/" "${INSTALL_DIR}/backend/" 2>/dev/null || cp -r "${PROJECT_ROOT}/backend" "${INSTALL_DIR}/backend"
    rsync -a --exclude='node_modules' --exclude='build' --exclude='.git' "${PROJECT_ROOT}/frontend/" "${INSTALL_DIR}/frontend/" 2>/dev/null || cp -r "${PROJECT_ROOT}/frontend" "${INSTALL_DIR}/frontend"
    cp -r "${PROJECT_ROOT}/deploy" "${INSTALL_DIR}/deploy" 2>/dev/null || true
fi

# ── Step 5: Backend setup ──
log "Step 5/9 — Setting up Python backend..."
cd "${INSTALL_DIR}/backend"

python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip

if [[ -f requirements.txt ]]; then
    # Filter out emergentintegrations (Emergent platform-only, not on public PyPI)
    grep -iv "emergentintegrations" requirements.txt > /tmp/shield-requirements.txt
    pip install -r /tmp/shield-requirements.txt || {
        warn "requirements.txt install had errors. Installing core deps manually..."
        pip install fastapi "uvicorn[standard]" motor pymongo "python-jose[cryptography]" PyJWT "passlib[bcrypt]" python-multipart pydantic cryptography httpx websockets aiofiles python-dotenv pyotp "qrcode[pil]" bcrypt requests webauthn
    }
    rm -f /tmp/shield-requirements.txt
else
    pip install fastapi "uvicorn[standard]" motor pymongo "python-jose[cryptography]" PyJWT "passlib[bcrypt]" python-multipart pydantic cryptography httpx websockets aiofiles python-dotenv pyotp "qrcode[pil]" bcrypt requests webauthn
fi

# Verify critical packages installed
python3 -c "import fastapi; import motor; import cryptography; import jwt; import webauthn; print('All core packages OK')" || err "Critical Python packages missing. Check pip output above."

ENCRYPTION_KEY=$(python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())') || err "Failed to generate encryption key."
deactivate

cat > "${INSTALL_DIR}/backend/.env" <<ENVEOF
MONGO_URL=mongodb://localhost:27017
DB_NAME=${MONGO_DB_NAME}
JWT_SECRET=${JWT_SECRET}
ENCRYPTION_KEY=${ENCRYPTION_KEY}
ADMIN_EMAIL=${ADMIN_EMAIL}
ADMIN_PASSWORD=${ADMIN_PASSWORD}
FRONTEND_URL=http://${DOMAIN}
ENVEOF

log "Backend configured."

# ── Step 6: Frontend setup ──
log "Step 6/9 — Building React frontend (this may take a few minutes)..."
cd "${INSTALL_DIR}/frontend"

if [[ "${DOMAIN}" == "localhost" ]]; then
    BROWSER_API_URL="http://localhost"
else
    BROWSER_API_URL="https://${DOMAIN}"
fi

cat > "${INSTALL_DIR}/frontend/.env" <<ENVEOF
REACT_APP_BACKEND_URL=${BROWSER_API_URL}
ENVEOF

yarn install --frozen-lockfile --silent 2>/dev/null || yarn install --silent
yarn build || err "Frontend build failed. Check Node.js version (need 18+): node -v"
log "Frontend built."

# ── Step 7: Systemd service ──
log "Step 7/9 — Creating systemd service..."

cat > /etc/systemd/system/shield-backend.service <<SVCEOF
[Unit]
Description=Shield Backend (FastAPI)
After=network.target mongod.service
Requires=mongod.service

[Service]
Type=simple
User=root
WorkingDirectory=${INSTALL_DIR}/backend
EnvironmentFile=${INSTALL_DIR}/backend/.env
ExecStart=${INSTALL_DIR}/backend/venv/bin/uvicorn server:app --host 0.0.0.0 --port ${BACKEND_PORT} --workers 2
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
SVCEOF

systemctl daemon-reload
systemctl enable shield-backend
systemctl start shield-backend
log "Backend service started."

# ── Step 8: nginx ──
log "Step 8/9 — Configuring nginx..."

cat > /etc/nginx/sites-available/shield <<NGXEOF
server {
    listen 80;
    server_name ${DOMAIN};

    root ${INSTALL_DIR}/frontend/build;
    index index.html;

    location /api/ {
        proxy_pass http://127.0.0.1:${BACKEND_PORT}/api/;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 300s;
        client_max_body_size 100M;
    }

    location /ws {
        proxy_pass http://127.0.0.1:${BACKEND_PORT}/ws;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_read_timeout 86400s;
    }

    location / {
        try_files \$uri \$uri/ /index.html;
    }

    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml;
    gzip_min_length 256;
}
NGXEOF

ln -sf /etc/nginx/sites-available/shield /etc/nginx/sites-enabled/shield
rm -f /etc/nginx/sites-enabled/default
nginx -t 2>/dev/null || err "nginx config test failed"
systemctl enable nginx
systemctl restart nginx
log "nginx running."

# ── Step 9: TLS ──
if [[ "${DOMAIN}" != "localhost" && "${DOMAIN}" != "127.0.0.1" ]]; then
    echo ""
    read -rp "$(echo -e "${CYAN}Set up HTTPS with Let's Encrypt for ${DOMAIN}?${NC} [y/N]: ")" SETUP_TLS
    if [[ "${SETUP_TLS,,}" == "y" ]]; then
        log "Step 9/9 — Setting up TLS..."
        certbot --nginx -d "${DOMAIN}" --non-interactive --agree-tos --email "${ADMIN_EMAIL}" || warn "Certbot failed. Run manually: sudo certbot --nginx -d ${DOMAIN}"
    else
        log "Step 9/9 — Skipping TLS. Run later: sudo certbot --nginx -d ${DOMAIN}"
    fi
else
    log "Step 9/9 — Skipping TLS (localhost)."
fi

# ── Done ──
echo ""
echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  Shield has been installed successfully!${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "  ${CYAN}URL:${NC}            http://${DOMAIN}"
echo -e "  ${CYAN}Admin email:${NC}    ${ADMIN_EMAIL}"
echo -e "  ${CYAN}Admin password:${NC} ${ADMIN_PASSWORD}"
echo -e "  ${CYAN}Install dir:${NC}    ${INSTALL_DIR}"
echo ""
echo -e "  ${YELLOW}Manage services:${NC}"
echo -e "    sudo systemctl status shield-backend"
echo -e "    sudo systemctl status nginx"
echo -e "    sudo systemctl status mongod"
echo ""
echo -e "  ${YELLOW}View logs:${NC}"
echo -e "    sudo journalctl -u shield-backend -f"
echo ""
echo -e "  ${YELLOW}Uninstall:${NC}"
echo -e "    sudo bash ${INSTALL_DIR}/deploy/uninstall.sh"
echo ""
echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
