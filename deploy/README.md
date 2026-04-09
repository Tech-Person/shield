# Shield — Debian Deployment Guide

## Files to Transfer

Copy these three folders to your server (keeping this structure):

```
shield/
├── backend/          ← Entire backend folder
├── frontend/         ← Entire frontend folder (including node_modules or not — installer runs yarn)
└── deploy/           ← This folder
    ├── install.sh
    ├── uninstall.sh
    └── README.md
```

**Example using rsync:**
```bash
rsync -avz --exclude='frontend/node_modules' --exclude='frontend/build' \
    --exclude='backend/__pycache__' --exclude='backend/venv' \
    backend/ frontend/ deploy/ user@your-server:~/shield/
```

**Or using scp:**
```bash
scp -r backend frontend deploy user@your-server:~/shield/
```

> The `deploy/` folder alone is NOT enough. The script reads `../backend` and `../frontend` relative to itself.

## Quick Start

```bash
cd ~/shield
sudo bash deploy/install.sh
```

The script handles everything automatically:
- Installs system dependencies (Node.js 20, Python 3, nginx)
- Installs MongoDB 7.0
- Sets up Python virtual environment and backend packages
- Builds the React frontend for production
- Configures nginx as a reverse proxy (API + WebSocket + SPA)
- Creates a systemd service for the backend
- Optionally sets up HTTPS via Let's Encrypt

## Requirements

| Requirement | Minimum |
|------------|---------|
| OS | Debian 11+ / Ubuntu 22.04+ |
| RAM | 2 GB |
| Disk | 10 GB free |
| CPU | 1 core (2+ recommended) |
| Network | Port 80 (and 443 for HTTPS) |

## Configuration

Override defaults with environment variables **before** running the script:

```bash
export SHIELD_DOMAIN="chat.example.com"       # Default: localhost
export SHIELD_ADMIN_EMAIL="you@example.com"    # Default: admin@shield.local
export SHIELD_ADMIN_PASSWORD="YourPassword"     # Default: random 16-char
export SHIELD_DIR="/opt/shield"                 # Default: /opt/shield
export SHIELD_DB_NAME="shield"                  # Default: shield
sudo -E bash deploy/install.sh
```

> **Note:** Use `sudo -E` to pass your environment variables through to the script.

## What Gets Installed

| Component | Location |
|-----------|----------|
| Application | `/opt/shield/` |
| Backend service | `shield-backend.service` (systemd) |
| nginx config | `/etc/nginx/sites-available/shield` |
| Backend .env | `/opt/shield/backend/.env` |
| Frontend build | `/opt/shield/frontend/build/` |
| MongoDB data | `/var/lib/mongodb/` (default) |

## Managing Services

```bash
# Status
sudo systemctl status shield-backend
sudo systemctl status nginx
sudo systemctl status mongod

# Restart
sudo systemctl restart shield-backend

# View logs
sudo journalctl -u shield-backend -f
sudo journalctl -u mongod -f
```

## HTTPS / TLS

The installer prompts for Let's Encrypt setup if your domain is not `localhost`. To set it up later:

```bash
sudo certbot --nginx -d your-domain.com
```

## Updating

```bash
cd ~/shield-source

# Update backend
cp -r backend/* /opt/shield/backend/
source /opt/shield/backend/venv/bin/activate
pip install -r /opt/shield/backend/requirements.txt
deactivate
sudo systemctl restart shield-backend

# Update frontend
cp -r frontend/src frontend/public frontend/package.json frontend/yarn.lock /opt/shield/frontend/
cd /opt/shield/frontend && yarn install && yarn build
sudo systemctl restart nginx
```

## Uninstalling

```bash
sudo bash /opt/shield/deploy/uninstall.sh
```

Removes services and application files. MongoDB and its data are preserved.

## Firewall

If using `ufw`:

```bash
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Backend won't start | `cat /opt/shield/backend/.env` — check credentials |
| MongoDB not running | `sudo systemctl start mongod && journalctl -u mongod` |
| nginx 502 | Backend not running: `sudo systemctl restart shield-backend` |
| WebSocket fails | Verify nginx `/ws` proxy block exists |
| Permission denied | Run with `sudo` |
| Let's Encrypt fails | DNS must point to server, port 80 open |
