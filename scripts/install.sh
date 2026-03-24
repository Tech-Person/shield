#!/bin/bash
# Port Forward Manager - Installation Script for Raspberry Pi / Debian Linux
# Uses SQLite (no MongoDB required!)
# Run this script as root on your Raspberry Pi or Debian-based system

set -e

echo "=========================================="
echo "  Port Forward Manager - Installation"
echo "  (SQLite Version - No MongoDB Required)"
echo "=========================================="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "ERROR: Please run this script as root (sudo ./install.sh)"
    exit 1
fi

# Configuration - can be overridden with environment variables
APP_DIR="${APP_DIR:-/opt/port-forward-manager}"
SERVICE_NAME="port-forward-manager"
WEB_PORT="${WEB_PORT:-5005}"
WIREGUARD_INTERFACE="${WIREGUARD_INTERFACE:-wg0}"
WIREGUARD_DEST_IP="${WIREGUARD_DEST_IP:-10.0.0.2}"
PUBLIC_INTERFACE="${PUBLIC_INTERFACE:-eth0}"
WIREGUARD_DOCKER_CONTAINER="${WIREGUARD_DOCKER_CONTAINER:-}"

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Configuration:"
echo "  - App Directory: $APP_DIR"
echo "  - Web Port: $WEB_PORT"
echo "  - Database: SQLite (file-based, no external service)"
echo "  - WireGuard Interface: $WIREGUARD_INTERFACE"
echo "  - WireGuard Destination: $WIREGUARD_DEST_IP"
echo "  - Public Interface: $PUBLIC_INTERFACE"
if [ -n "$WIREGUARD_DOCKER_CONTAINER" ]; then
    echo "  - WireGuard Docker Container: $WIREGUARD_DOCKER_CONTAINER"
fi
echo "  - Source Directory: $SCRIPT_DIR"
echo ""

# ==================== INSTALL SYSTEM DEPENDENCIES ====================
echo "Installing system dependencies..."
apt-get update

# Install Python 3 and pip
echo "Installing Python 3..."
apt-get install -y python3 python3-pip python3-venv

# Install iptables
echo "Installing iptables..."
apt-get install -y iptables

# Install UFW (Uncomplicated Firewall)
echo "Installing UFW..."
apt-get install -y ufw

# Install curl for testing
apt-get install -y curl

echo "System dependencies installed successfully."
echo ""

# ==================== CREATE APPLICATION DIRECTORY ====================
echo "Creating application directory..."
mkdir -p "$APP_DIR/backend"
mkdir -p "$APP_DIR/backend/static"

# ==================== COPY APPLICATION FILES ====================
# Copy server.py if it exists in the same directory
if [ -f "$SCRIPT_DIR/server.py" ]; then
    echo "Copying server.py..."
    cp "$SCRIPT_DIR/server.py" "$APP_DIR/backend/"
else
    echo "ERROR: server.py not found in $SCRIPT_DIR"
    echo "Please make sure server.py is in the same directory as this script."
    exit 1
fi

# Copy frontend files if they exist (from build output)
if [ -f "$SCRIPT_DIR/index.html" ]; then
    echo "Copying frontend files..."
    cp "$SCRIPT_DIR/index.html" "$APP_DIR/backend/static/"
    cp "$SCRIPT_DIR/favicon.svg" "$APP_DIR/backend/static/" 2>/dev/null || true
    cp "$SCRIPT_DIR/asset-manifest.json" "$APP_DIR/backend/static/" 2>/dev/null || true
    
    if [ -d "$SCRIPT_DIR/static" ]; then
        cp -r "$SCRIPT_DIR/static" "$APP_DIR/backend/static/"
    fi
    echo "Frontend files copied successfully!"
else
    echo "WARNING: Frontend files not found. The API will work but no web UI."
    echo "To add the web UI, copy the built frontend to $APP_DIR/backend/static/"
fi

# ==================== SETUP PYTHON ENVIRONMENT ====================
echo "Setting up Python environment..."

# Create requirements.txt
cat > "$APP_DIR/backend/requirements.txt" << 'EOF'
fastapi==0.110.1
uvicorn==0.25.0
python-dotenv>=1.0.1
pydantic>=2.6.4
pyjwt>=2.10.1
bcrypt==4.1.3
EOF

# Create virtual environment
echo "Creating Python virtual environment..."
python3 -m venv "$APP_DIR/venv"

# Activate and install dependencies
echo "Installing Python dependencies..."
source "$APP_DIR/venv/bin/activate"
pip install --upgrade pip
pip install -r "$APP_DIR/backend/requirements.txt"
deactivate

echo "Python environment setup complete."
echo ""

# ==================== CREATE CONFIGURATION ====================
echo "Creating configuration..."

# Generate secure JWT secret
JWT_SECRET=$(openssl rand -hex 32 2>/dev/null || head -c 32 /dev/urandom | xxd -p | tr -d '\n')

# Create .env file
cat > "$APP_DIR/backend/.env" << EOF
DB_PATH="$APP_DIR/port_forward.db"
CORS_ORIGINS="*"
JWT_SECRET="$JWT_SECRET"
WIREGUARD_INTERFACE="$WIREGUARD_INTERFACE"
WIREGUARD_DEST_IP="$WIREGUARD_DEST_IP"
PUBLIC_INTERFACE="$PUBLIC_INTERFACE"
WIREGUARD_DOCKER_CONTAINER="$WIREGUARD_DOCKER_CONTAINER"
SIMULATION_MODE="false"
EOF

echo "Configuration file created at $APP_DIR/backend/.env"
echo ""

# ==================== CREATE SYSTEMD SERVICE ====================
echo "Creating systemd service..."

cat > "/etc/systemd/system/${SERVICE_NAME}.service" << EOF
[Unit]
Description=Port Forward Manager
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$APP_DIR/backend
Environment=PATH=$APP_DIR/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin
ExecStart=$APP_DIR/venv/bin/uvicorn server:app --host 0.0.0.0 --port $WEB_PORT
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd
systemctl daemon-reload

echo "Systemd service created."
echo ""

# ==================== CONFIGURE FIREWALL ====================
echo "Configuring firewall..."

# Enable UFW if not already enabled
if ! ufw status | grep -q "Status: active"; then
    echo "Enabling UFW..."
    # Allow SSH first to prevent lockout
    ufw allow ssh
    ufw --force enable
fi

# Allow web UI port
ufw allow $WEB_PORT/tcp comment "Port Forward Manager Web UI"

echo "Firewall configured."
echo ""

# ==================== ENABLE IP FORWARDING ====================
echo "Enabling IP forwarding..."

if [ -f /etc/sysctl.conf ]; then
    if ! grep -q "^net.ipv4.ip_forward=1" /etc/sysctl.conf; then
        echo "net.ipv4.ip_forward=1" >> /etc/sysctl.conf
    fi
    sysctl -p 2>/dev/null || true
fi

echo "IP forwarding enabled."
echo ""

# ==================== START SERVICE ====================
echo "Starting service..."
systemctl start $SERVICE_NAME
systemctl enable $SERVICE_NAME

# Wait for service to start
sleep 3

# Check if service is running
if systemctl is-active --quiet $SERVICE_NAME; then
    echo "Service started successfully!"
else
    echo "WARNING: Service may not have started correctly."
    echo "Check logs with: journalctl -u $SERVICE_NAME -f"
fi

echo ""
echo "=========================================="
echo "  Installation Complete!"
echo "=========================================="
echo ""
echo "Access the web UI at:"
echo "   http://$(hostname -I | awk '{print $1}'):$WEB_PORT"
echo ""
echo "Default credentials:"
echo "   Username: admin"
echo "   Password: admin"
echo "   (You will be prompted to change password on first login)"
echo ""
echo "Useful commands:"
echo "   Check status:  sudo systemctl status $SERVICE_NAME"
echo "   View logs:     sudo journalctl -u $SERVICE_NAME -f"
echo "   Restart:       sudo systemctl restart $SERVICE_NAME"
echo "   Stop:          sudo systemctl stop $SERVICE_NAME"
echo ""
echo "Configuration file: $APP_DIR/backend/.env"
echo "Database file:      $APP_DIR/port_forward.db"
echo ""
echo "To modify settings, edit the .env file and restart the service."
echo ""
