#!/bin/bash
# Port Forward Manager - Installation Script for Raspberry Pi
# Now uses SQLite (no MongoDB required!)
# Run this script as root on your Raspberry Pi

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

# Configuration
APP_DIR="/opt/port-forward-manager"
SERVICE_NAME="port-forward-manager"
WEB_PORT="${WEB_PORT:-5005}"
WIREGUARD_INTERFACE="${WIREGUARD_INTERFACE:-wg0}"
WIREGUARD_DEST_IP="${WIREGUARD_DEST_IP:-10.0.0.2}"

echo "Configuration:"
echo "  - App Directory: $APP_DIR"
echo "  - Web Port: $WEB_PORT"
echo "  - Database: SQLite (file-based, no external service)"
echo "  - WireGuard Interface: $WIREGUARD_INTERFACE"
echo "  - WireGuard Destination: $WIREGUARD_DEST_IP"
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
mkdir -p "$APP_DIR"
mkdir -p "$APP_DIR/backend"

# Copy backend files
echo "Setting up backend..."
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

# Create .env file
echo "Creating environment configuration..."
cat > "$APP_DIR/backend/.env" << EOF
DB_PATH="$APP_DIR/port_forward.db"
CORS_ORIGINS="*"
JWT_SECRET="$(openssl rand -hex 32)"
WIREGUARD_INTERFACE="$WIREGUARD_INTERFACE"
WIREGUARD_DEST_IP="$WIREGUARD_DEST_IP"
SIMULATION_MODE="false"
EOF

echo ""
echo "IMPORTANT: Copy your server.py to $APP_DIR/backend/server.py"
echo ""

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
if ! grep -q "net.ipv4.ip_forward=1" /etc/sysctl.conf; then
    echo "net.ipv4.ip_forward=1" >> /etc/sysctl.conf
fi
sysctl -p

# Reload systemd
systemctl daemon-reload

echo ""
echo "=========================================="
echo "  Installation Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo ""
echo "1. Copy your server.py to the Pi:"
echo "   scp server.py pi@<your-pi-ip>:$APP_DIR/backend/"
echo ""
echo "2. Start the service:"
echo "   sudo systemctl start $SERVICE_NAME"
echo ""
echo "3. Enable on boot:"
echo "   sudo systemctl enable $SERVICE_NAME"
echo ""
echo "4. Access the web UI at:"
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
echo "(SQLite file - no external database service needed)"
echo ""
