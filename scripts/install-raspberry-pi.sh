#!/bin/bash
# Port Forward Manager - Installation Script for Raspberry Pi
# Uses SQLite (no MongoDB required!)
# Run this script as root on your Raspberry Pi

set -e

echo "=========================================="
echo "  Port Forward Manager - Installation"
echo "  (SQLite Version - No MongoDB Required)"
echo "=========================================="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "ERROR: Please run this script as root (sudo ./install-raspberry-pi.sh)"
    exit 1
fi

# Configuration
APP_DIR="/opt/port-forward-manager"
SERVICE_NAME="port-forward-manager"
WEB_PORT="${WEB_PORT:-5005}"
WIREGUARD_INTERFACE="${WIREGUARD_INTERFACE:-wg0}"
WIREGUARD_DEST_IP="${WIREGUARD_DEST_IP:-10.0.0.2}"
PUBLIC_INTERFACE="${PUBLIC_INTERFACE:-eth0}"

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Configuration:"
echo "  - App Directory: $APP_DIR"
echo "  - Web Port: $WEB_PORT"
echo "  - Database: SQLite (file-based, no external service)"
echo "  - WireGuard Interface: $WIREGUARD_INTERFACE"
echo "  - WireGuard Destination: $WIREGUARD_DEST_IP"
echo "  - Public Interface: $PUBLIC_INTERFACE"
echo "  - Source Directory: $SCRIPT_DIR"
echo ""

# Check dependencies
echo "Checking dependencies..."

# Check for Python 3
if ! command -v python3 &> /dev/null; then
    echo "Installing Python 3..."
    apt-get update
    apt-get install -y python3 python3-pip python3-venv
fi

# Check for iptables
if ! command -v iptables &> /dev/null; then
    echo "Installing iptables..."
    apt-get install -y iptables
fi

# Check for UFW
if ! command -v ufw &> /dev/null; then
    echo "Installing UFW..."
    apt-get install -y ufw
fi

# Create application directory
echo "Creating application directory..."
mkdir -p "$APP_DIR/backend"
mkdir -p "$APP_DIR/backend/static"

# Copy server.py if it exists in the same directory
if [ -f "$SCRIPT_DIR/server.py" ]; then
    echo "Copying server.py..."
    cp "$SCRIPT_DIR/server.py" "$APP_DIR/backend/"
else
    echo "WARNING: server.py not found in $SCRIPT_DIR"
    echo "Please copy server.py to $APP_DIR/backend/ manually"
fi

# Copy frontend files if they exist (from build output)
if [ -f "$SCRIPT_DIR/index.html" ]; then
    echo "Copying frontend files..."
    cp -r "$SCRIPT_DIR"/*.html "$APP_DIR/backend/static/" 2>/dev/null || true
    cp -r "$SCRIPT_DIR"/*.json "$APP_DIR/backend/static/" 2>/dev/null || true
    cp -r "$SCRIPT_DIR"/*.ico "$APP_DIR/backend/static/" 2>/dev/null || true
    cp -r "$SCRIPT_DIR"/*.txt "$APP_DIR/backend/static/" 2>/dev/null || true
    cp -r "$SCRIPT_DIR"/static "$APP_DIR/backend/static/" 2>/dev/null || true
    echo "Frontend files copied successfully!"
else
    echo "NOTE: Frontend files not found. The API will work but no web UI."
    echo "To add the web UI, copy the built frontend to $APP_DIR/backend/static/"
fi

# Create requirements.txt
echo "Setting up Python requirements..."
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
source "$APP_DIR/venv/bin/activate"
pip install --upgrade pip
pip install -r "$APP_DIR/backend/requirements.txt"
deactivate

# Create .env file with secure JWT secret
echo "Creating environment configuration..."
JWT_SECRET=$(openssl rand -hex 32 2>/dev/null || head -c 32 /dev/urandom | xxd -p)
cat > "$APP_DIR/backend/.env" << EOF
DB_PATH="$APP_DIR/port_forward.db"
CORS_ORIGINS="*"
JWT_SECRET="$JWT_SECRET"
WIREGUARD_INTERFACE="$WIREGUARD_INTERFACE"
WIREGUARD_DEST_IP="$WIREGUARD_DEST_IP"
PUBLIC_INTERFACE="$PUBLIC_INTERFACE"
SIMULATION_MODE="false"
EOF

# Create systemd service
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

# Allow web UI port through UFW
echo "Configuring UFW for web UI access..."
ufw allow $WEB_PORT/tcp comment "Port Forward Manager Web UI"

# Enable IP forwarding
echo "Enabling IP forwarding..."
if [ -f /etc/sysctl.conf ]; then
    if ! grep -q "net.ipv4.ip_forward=1" /etc/sysctl.conf; then
        echo "net.ipv4.ip_forward=1" >> /etc/sysctl.conf
    fi
    sysctl -p 2>/dev/null || true
fi

# Reload systemd
systemctl daemon-reload

echo ""
echo "=========================================="
echo "  Installation Complete!"
echo "=========================================="
echo ""
echo "Start the service:"
echo "   sudo systemctl start $SERVICE_NAME"
echo ""
echo "Enable on boot:"
echo "   sudo systemctl enable $SERVICE_NAME"
echo ""
echo "Access the web UI at:"
echo "   http://<pi-ip>:$WEB_PORT"
echo ""
echo "Default credentials: admin / admin"
echo "(You will be prompted to change password on first login)"
echo ""
echo "To check service status:"
echo "   sudo systemctl status $SERVICE_NAME"
echo ""
echo "To view logs:"
echo "   sudo journalctl -u $SERVICE_NAME -f"
echo ""
echo "Database location: $APP_DIR/port_forward.db"
echo ""
