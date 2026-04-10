#!/bin/bash
# Shield Desktop - Linux Build Script
# Prerequisites: Node.js 18+, yarn

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== Shield Desktop Build ==="
echo ""

# Check prerequisites
if ! command -v node &> /dev/null; then
    echo "ERROR: Node.js is required. Install via: https://nodejs.org"
    exit 1
fi

if ! command -v yarn &> /dev/null; then
    echo "ERROR: yarn is required. Install via: npm install -g yarn"
    exit 1
fi

# Configure Shield server URL
if [ -z "$SHIELD_URL" ]; then
    read -p "Enter your Shield server URL [https://localhost:3000]: " url
    SHIELD_URL="${url:-https://localhost:3000}"
fi

export SHIELD_URL

echo "Shield URL: $SHIELD_URL"
echo ""

# Install dependencies
echo "[1/3] Installing dependencies..."
yarn install --frozen-lockfile 2>/dev/null || yarn install

# Generate icon if not present
if [ ! -f "assets/icon.png" ]; then
    echo "[2/3] Creating placeholder icon..."
    mkdir -p assets
    # Create a simple 256x256 SVG and convert if possible
    cat > assets/icon.svg << 'SVG'
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" width="256" height="256">
  <rect width="256" height="256" rx="48" fill="#020617"/>
  <path d="M128 40 L200 80 L200 160 L128 216 L56 160 L56 80 Z" fill="none" stroke="#10b981" stroke-width="8"/>
  <path d="M128 72 L168 96 L168 144 L128 176 L88 144 L88 96 Z" fill="#10b981" opacity="0.3"/>
  <circle cx="128" cy="120" r="20" fill="#10b981"/>
</svg>
SVG
    # Try to convert SVG to PNG using available tools
    if command -v convert &> /dev/null; then
        convert assets/icon.svg -resize 256x256 assets/icon.png
        cp assets/icon.png assets/tray-icon.png
    elif command -v rsvg-convert &> /dev/null; then
        rsvg-convert -w 256 -h 256 assets/icon.svg > assets/icon.png
        rsvg-convert -w 16 -h 16 assets/icon.svg > assets/tray-icon.png
    else
        echo "  (SVG created; install imagemagick or librsvg2-bin to generate PNG)"
        # Copy SVG as fallback — Electron can handle it
        cp assets/icon.svg assets/icon.png 2>/dev/null || true
        cp assets/icon.svg assets/tray-icon.png 2>/dev/null || true
    fi
fi

# Build
echo "[3/3] Building Linux packages..."
echo "  Targets: AppImage, .deb"
yarn build

echo ""
echo "=== Build Complete ==="
echo "Output in: $SCRIPT_DIR/dist/"
ls -lh dist/*.AppImage dist/*.deb 2>/dev/null || echo "(Check dist/ for built packages)"
