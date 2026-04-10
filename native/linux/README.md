# Shield Desktop (Linux)

Privacy-first communication app — native Linux wrapper using Electron.

## Features
- System tray integration (minimize to tray)
- Single instance lock (one window only)
- WebRTC permissions auto-granted (mic, camera)
- External links open in default browser
- Desktop notifications for messages and calls
- Supports `.deb` and `.AppImage` builds

## Quick Start (Development)

```bash
# Set your Shield server URL
export SHIELD_URL="https://your-shield-server.com"

# Install dependencies
yarn install

# Run in dev mode
yarn start
```

## Build for Distribution

```bash
# Automated build script
chmod +x build.sh
SHIELD_URL="https://your-shield-server.com" ./build.sh

# Or manual build
yarn build          # AppImage + deb
yarn build:deb      # .deb only
yarn build:appimage # AppImage only
```

Built packages will be in `dist/`.

## Configuration

Set the `SHIELD_URL` environment variable to point to your Shield instance:

```bash
# Option 1: Environment variable
export SHIELD_URL="https://shield.example.com"

# Option 2: Edit main.js line 5
const SHIELD_URL = 'https://shield.example.com';
```

## System Requirements
- Node.js 18+
- yarn
- Linux x64 (Ubuntu 20.04+, Debian 11+, Fedora 36+)
- For `.deb` build: `dpkg` (usually pre-installed)

## Project Structure
```
linux/
  main.js       - Electron main process
  preload.js    - Context bridge for renderer
  package.json  - Dependencies & build config
  build.sh      - Automated build script
  assets/       - Icons (generated on first build)
```
