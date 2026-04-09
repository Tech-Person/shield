# Shield — Debian Deployment Guide

## Files to Transfer

Copy these three folders to your server:

```
shield/
├── backend/
├── frontend/
└── deploy/
    ├── install.sh
    ├── uninstall.sh
    └── README.md
```

**Transfer with rsync (recommended):**
```bash
rsync -avz --exclude='node_modules' --exclude='build' --exclude='venv' --exclude='__pycache__' \
    backend/ frontend/ deploy/ user@your-server:~/shield/
```

## Install

```bash
cd ~/shield
sudo bash deploy/install.sh
```

The script will prompt you for:
1. **Domain name** — your server's domain (e.g. `chat.example.com`) or `localhost`
2. **Admin email** — for the admin account login
3. **Admin password** — min 8 characters (press Enter to auto-generate)
4. **Install directory** — where to install (default: `/opt/shield`)
5. **HTTPS setup** — optional Let's Encrypt TLS (if domain is not localhost)

Everything else is automatic.

## Requirements

| Requirement | Minimum |
|------------|---------|
| OS | Debian 11+ / Ubuntu 22.04+ |
| RAM | 2 GB |
| Disk | 10 GB free |
| Network | Port 80 (and 443 for HTTPS) |

## Managing Services

```bash
sudo systemctl status shield-backend
sudo systemctl status nginx
sudo systemctl status mongod

sudo systemctl restart shield-backend
sudo journalctl -u shield-backend -f
```

## HTTPS

If you skipped TLS during install:
```bash
sudo certbot --nginx -d your-domain.com
```

## Updating

```bash
# Backend
rsync -a backend/ /opt/shield/backend/
source /opt/shield/backend/venv/bin/activate && pip install -r /opt/shield/backend/requirements.txt && deactivate
sudo systemctl restart shield-backend

# Frontend
rsync -a --exclude='node_modules' --exclude='build' frontend/ /opt/shield/frontend/
cd /opt/shield/frontend && yarn install && yarn build
sudo systemctl restart nginx
```

## Uninstalling

```bash
sudo bash /opt/shield/deploy/uninstall.sh
```

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Backend won't start | `cat /opt/shield/backend/.env` — check credentials |
| MongoDB not running | `sudo systemctl start mongod && journalctl -u mongod` |
| nginx 502 | `sudo systemctl restart shield-backend` |
| WebSocket fails | Verify nginx has `/ws` proxy block |
