#!/bin/bash
# Build frontend for Raspberry Pi deployment
# Run this BEFORE copying files to your Pi

set -e

echo "Building frontend for production..."

# Navigate to frontend directory
cd /app/frontend

# Set the backend URL for the Pi
# Change this IP to your Raspberry Pi's IP address
PI_IP="${PI_IP:-localhost}"
PI_PORT="${PI_PORT:-5005}"

echo "Building for backend URL: http://${PI_IP}:${PI_PORT}"

# Create production .env
cat > .env.production << EOF
REACT_APP_BACKEND_URL=http://${PI_IP}:${PI_PORT}
EOF

# Build
yarn build

# Create deployment package
echo "Creating deployment package..."
mkdir -p /app/deploy
cp -r /app/frontend/build/* /app/deploy/
cp /app/backend/server.py /app/deploy/
cp /app/backend/requirements.txt /app/deploy/
cp /app/scripts/install-raspberry-pi.sh /app/deploy/

echo ""
echo "========================================"
echo "Build complete!"
echo "========================================"
echo ""
echo "Files ready in /app/deploy/"
echo ""
echo "To deploy to your Pi:"
echo "1. Copy files: scp -r /app/deploy/* pi@<pi-ip>:/tmp/port-forward/"
echo "2. SSH to Pi: ssh pi@<pi-ip>"
echo "3. Run installer: sudo bash /tmp/port-forward/install-raspberry-pi.sh"
echo ""
