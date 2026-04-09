#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────
# Shield — Debian/Ubuntu Deployment Script
# Installs and configures the full stack as systemd services.
#
# DIRECTORY STRUCTURE REQUIRED:
#   ~/shield/            (or wherever you place it)
#   ├── backend/         (entire backend folder)
#   ├── frontend/        (entire frontend folder)
#   └── deploy/          (this script lives here)
#       ├── install.sh
#       ├── uninstall.sh
#       └── README.md
#
# Run as root:  sudo bash deploy/install.sh
# ──────────────────────────────────────────────────────────────
set -euo pipefail

# ── Colour helpers ──
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
log()  { echo -e "${GREEN}[Shield]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
err()  { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

# ── Pre-flight checks ──
[[ $EUID -ne 0 ]] && err "This script must be run as root (sudo bash deploy/install.sh)"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Verify required directories exist
[[ ! -d "${PROJECT_ROOT}/backend" ]] && err "Missing backend/ directory. Expected at: ${PROJECT_ROOT}/backend\nSee deploy/README.md for the required directory structure."
[[ ! -d "${PROJECT_ROOT}/frontend" ]] && err "Missing frontend/ directory. Expected at: ${PROJECT_ROOT}/frontend\nSee deploy/README.md for the required directory structure."
[[ ! -f "${PROJECT_ROOT}/backend/server.py" ]] && err "backend/server.py not found. Is this the correct project directory?"
[[ ! -f "${PROJECT_ROOT}/frontend/package.json" ]] && err "frontend/package.json not found. Is this the correct project directory?"

log "Source directory: ${PROJECT_ROOT}"

# ── Configuration (override via environment) ──
INSTALL_DIR="${SHIELD_DIR:-/opt/shield}"
DOMAIN="${SHIELD_DOMAIN:-localhost}"
BACKEND_PORT="${SHIELD_BACKEND_PORT:-8001}"
ADMIN_EMAIL="${SHIELD_ADMIN_EMAIL:-admin@shield.local}"
ADMIN_PASSWORD="${SHIELD_ADMIN_PASSWORD:-$(openssl rand -base64 16)}"
JWT_SECRET="${SHIELD_JWT_SECRET:-$(openssl rand -hex 32)}"
MONGO_DB_NAME="${SHIELD_DB_NAME:-shield}"

log "Installing Shield to ${INSTALL_DIR}"
log "Domain: ${DOMAIN}"

# ── Step 1: System packages ──
log "Step 1/9 — Installing system dependencies..."
apt-get update -qq

# Install core packages (software-properties-common is optional, skip if unavailable)
apt-get install -y -qq \
    curl wget gnupg2 lsb-release \
    build-essential python3 python3-pip python3-venv \
    nginx certbot python3-certbot-nginx \
    git jq unzip > /dev/null 2>&1 || {
    warn "Some optional packages missing, trying minimal set..."
    apt-get install -y -qq \
        curl wget gnupg2 \
        python3 python3-pip python3-venv \
        nginx git jq > /dev/null
}

# ── Step 2: Node.js 20.x via NodeSource ──
if ! command -v node &>/dev/null || [[ "$(node -v | cut -d. -f1 | tr -d v)" -lt 18 ]]; then
    log "Step 2/9 — Installing Node.js 20.x..."
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - > /dev/null 2>&1
    apt-get install -y -qq nodejs > /dev/null
else
    log "Step 2/9 — Node.js $(node -v) already installed, skipping."
fi

# Install yarn globally
if ! command -v yarn &>/dev/null; then
    npm install -g yarn > /dev/null 2>&1
fi

# ── Step 3: MongoDB 7.0 ──
if ! command -v mongod &>/dev/null && ! command -v mongosh &>/dev/null; then
    log "Step 3/9 — Installing MongoDB 7.0..."
    curl -fsSL https://www.mongodb.org/static/pgp/server-7.0.asc | gpg --dearmor -o /usr/share/keyrings/mongodb-server-7.0.gpg 2>/dev/null

    # Detect codename; fall back to jammy for unknown distros
    CODENAME="$(lsb_release -cs 2>/dev/null || echo jammy)"
    echo "deb [signed-by=/usr/share/keyrings/mongodb-server-7.0.gpg] https://repo.mongodb.org/apt/ubuntu ${CODENAME}/mongodb-org/7.0 multiverse" > /etc/apt/sources.list.d/mongodb-org-7.0.list
    apt-get update -qq
    apt-get install -y -qq mongodb-org > /dev/null 2>&1 || {
        warn "MongoDB repo failed for '${CODENAME}'. Trying 'jammy'..."
        echo "deb [signed-by=/usr/share/keyrings/mongodb-server-7.0.gpg] https://repo.mongodb.org/apt/ubuntu jammy/mongodb-org/7.0 multiverse" > /etc/apt/sources.list.d/mongodb-org-7.0.list
        apt-get update -qq
        apt-get install -y -qq mongodb-org > /dev/null
    }
    systemctl enable mongod
    systemctl start mongod
    sleep 2
else
    log "Step 3/9 — MongoDB already installed, ensuring it's running..."
    systemctl enable mongod 2>/dev/null || true
    systemctl start mongod 2>/dev/null || true
fi

# Verify MongoDB is up
for i in 1 2 3; do
    if mongosh --quiet --eval "db.runCommand({ping:1})" > /dev/null 2>&1; then
        break
    fi
    warn "MongoDB not ready, retrying in 3s... (attempt $i/3)"
    sleep 3
done
mongosh --quiet --eval "db.runCommand({ping:1})" > /dev/null 2>&1 || err "MongoDB is not responding. Check: systemctl status mongod"
log "MongoDB is running."

# ── Step 4: Copy application files ──
log "Step 4/9 — Copying application to ${INSTALL_DIR}..."
mkdir -p "${INSTALL_DIR}"
cp -r "${PROJECT_ROOT}/backend" "${INSTALL_DIR}/backend"
cp -r "${PROJECT_ROOT}/frontend" "${INSTALL_DIR}/frontend"
cp -r "${PROJECT_ROOT}/deploy" "${INSTALL_DIR}/deploy"

# ── Step 5: Backend setup ──
log "Step 5/9 — Setting up Python backend..."
cd "${INSTALL_DIR}/backend"

python3 -m venv venv
source venv/bin/activate
pip install --quiet --upgrade pip

if [[ -f requirements.txt ]]; then
    pip install --quiet -r requirements.txt
else
    pip install --quiet fastapi uvicorn motor pymongo python-jose[cryptography] passlib[bcrypt] python-multipart pydantic cryptography httpx websockets aiofiles
fi

# Generate encryption key
ENCRYPTION_KEY=$(python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')

# Write backend .env
cat > "${INSTALL_DIR}/backend/.env" <<ENVEOF
MONGO_URL=mongodb://localhost:27017
DB_NAME=${MONGO_DB_NAME}
JWT_SECRET=${JWT_SECRET}
ENCRYPTION_KEY=${ENCRYPTION_KEY}
ADMIN_EMAIL=${ADMIN_EMAIL}
ADMIN_PASSWORD=${ADMIN_PASSWORD}
FRONTEND_URL=http://${DOMAIN}
ENVEOF

deactivate
log "Backend configured."

# ── Step 6: Frontend setup ──
log "Step 6/9 — Building React frontend..."
cd "${INSTALL_DIR}/frontend"

# Determine the backend URL the browser will use
if [[ "${DOMAIN}" == "localhost" ]]; then
    BROWSER_API_URL="http://localhost"
else
    BROWSER_API_URL="https://${DOMAIN}"
fi

cat > "${INSTALL_DIR}/frontend/.env" <<ENVEOF
REACT_APP_BACKEND_URL=${BROWSER_API_URL}
ENVEOF

# Remove node_modules if transferred (saves space, will reinstall)
rm -rf node_modules/.cache 2>/dev/null || true

yarn install --frozen-lockfile --silent 2>/dev/null || yarn install --silent
yarn build
log "Frontend built."

# ── Step 7: Create systemd service ──
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

# ── Step 8: Configure nginx ──
log "Step 8/9 — Configuring nginx reverse proxy..."

cat > /etc/nginx/sites-available/shield <<NGXEOF
server {
    listen 80;
    server_name ${DOMAIN};

    # Frontend — serve static build
    root ${INSTALL_DIR}/frontend/build;
    index index.html;

    # API & WebSocket reverse proxy
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

    # SPA fallback
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
log "nginx configured and running."

# ── Step 9: Optional TLS with Let's Encrypt ──
if [[ "${DOMAIN}" != "localhost" && "${DOMAIN}" != "127.0.0.1" ]]; then
    log "Step 9/9 — TLS setup..."
    echo ""
    read -rp "Set up HTTPS with Let's Encrypt for ${DOMAIN}? [y/N]: " SETUP_TLS
    if [[ "${SETUP_TLS,,}" == "y" ]]; then
        certbot --nginx -d "${DOMAIN}" --non-interactive --agree-tos --email "${ADMIN_EMAIL}" || warn "Certbot failed. Run manually later: certbot --nginx -d ${DOMAIN}"
    else
        log "Skipping TLS. Set up later: sudo certbot --nginx -d ${DOMAIN}"
    fi
else
    log "Step 9/9 — Skipping TLS (localhost deployment)."
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
echo -e "  ${YELLOW}Services:${NC}"
echo -e "    sudo systemctl status shield-backend"
echo -e "    sudo systemctl status nginx"
echo -e "    sudo systemctl status mongod"
echo ""
echo -e "  ${YELLOW}Logs:${NC}"
echo -e "    sudo journalctl -u shield-backend -f"
echo ""
echo -e "  ${YELLOW}Uninstall:${NC}"
echo -e "    sudo bash ${INSTALL_DIR}/deploy/uninstall.sh"
echo ""
echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
