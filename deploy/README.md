# SecureComm — Debian Deployment Guide

## Quick Start

```bash
sudo bash deploy/install.sh
```

That's it. The script handles everything:
- Installs system dependencies (Node.js 20, Python 3, nginx, MongoDB 7.0)
- Sets up the Python virtual environment and installs backend packages
- Builds the React frontend for production
- Configures nginx as a reverse proxy (API + WebSocket + static SPA)
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

Override defaults with environment variables before running the script:

```bash
export SECURECOMM_DOMAIN="chat.example.com"     # Default: localhost
export SECURECOMM_ADMIN_EMAIL="you@example.com"  # Default: admin@securecomm.local
export SECURECOMM_ADMIN_PASSWORD="YourPassword"   # Default: random 16-char
export SECURECOMM_DIR="/opt/securecomm"           # Default: /opt/securecomm
sudo -E bash deploy/install.sh
```

> **Note:** Use `sudo -E` to pass your environment variables through to the script.

## What Gets Installed

| Component | Location |
|-----------|----------|
| Application | `/opt/securecomm/` |
| Backend service | `securecomm-backend.service` (systemd) |
| nginx config | `/etc/nginx/sites-available/securecomm` |
| Backend .env | `/opt/securecomm/backend/.env` |
| Frontend build | `/opt/securecomm/frontend/build/` |
| MongoDB data | `/var/lib/mongodb/` (default) |

## Managing Services

```bash
# Status
sudo systemctl status securecomm-backend
sudo systemctl status nginx
sudo systemctl status mongod

# Restart
sudo systemctl restart securecomm-backend

# View logs
sudo journalctl -u securecomm-backend -f
sudo journalctl -u mongod -f
```

## HTTPS / TLS

The installer prompts for Let's Encrypt setup if your domain is not `localhost`. To set it up later:

```bash
sudo certbot --nginx -d your-domain.com
```

Certbot auto-renews via a systemd timer. Verify with:
```bash
sudo certbot renew --dry-run
```

## Updating

To update SecureComm after pulling new code:

```bash
cd /path/to/securecomm-source

# Update backend
cp -r backend/* /opt/securecomm/backend/
source /opt/securecomm/backend/venv/bin/activate
pip install -r /opt/securecomm/backend/requirements.txt
deactivate
sudo systemctl restart securecomm-backend

# Update frontend
cp -r frontend/src frontend/public frontend/package.json frontend/yarn.lock /opt/securecomm/frontend/
cd /opt/securecomm/frontend && yarn install && yarn build
sudo systemctl restart nginx
```

## Uninstalling

```bash
sudo bash /opt/securecomm/deploy/uninstall.sh
```

This removes services and application files. MongoDB and its data are preserved (manual removal instructions provided).

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
| Backend won't start | Check `.env` file: `cat /opt/securecomm/backend/.env` |
| MongoDB not running | `sudo systemctl start mongod && journalctl -u mongod` |
| nginx 502 | Backend not running: `sudo systemctl restart securecomm-backend` |
| WebSocket fails | Check nginx config has `/ws` proxy block |
| Permission denied | Ensure script was run with `sudo` |
| Let's Encrypt fails | DNS must point to this server, port 80 must be open |
