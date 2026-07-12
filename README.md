# Port Forward Manager

A web-based port forwarding management system for Raspberry Pi with WireGuard tunnel support.

## Features

- **Web UI** - Easy-to-use dashboard for managing port forwarding rules
- **User Authentication** - Secure login with password hashing (bcrypt)
- **Role-Based Access** - Admin and regular user roles
- **WireGuard Integration** - Real-time tunnel status monitoring (supports Docker)
- **iptables + UFW** - Automatic firewall rule management
- **Duplicate Prevention** - Checks for existing rules before adding
- **Boot Persistence** - Rules automatically restored on system restart
- **SQLite Database** - No external database service required

## Requirements

- Raspberry Pi or Debian-based Linux system
- Python 3.8+
- Root access (for iptables/UFW management)
- WireGuard tunnel configured (on host or in Docker)

## Quick Install

1. **Download the release files** to your Pi (all files in same directory):
   - `install.sh` - Installation script
   - `server.py` - Backend server
   - `index.html` - Frontend entry point
   - `favicon.svg` - Browser icon
   - `asset-manifest.json` - Asset manifest
   - `static/` - Frontend assets (JS/CSS)

2. **Run the installer as root:**
   ```bash
   cd /path/to/downloaded/files
   sudo bash install.sh
   ```

3. **Access the web UI:**
   ```
   http://<your-pi-ip>:5005
   ```

4. **Login with default credentials:**
   - Username: `admin`
   - Password: `admin`
   - (You'll be prompted to change password on first login)

## Configuration Options

You can customize the installation by setting environment variables before running the installer:

```bash
# Example: Custom configuration
sudo WEB_PORT=8080 \
     WIREGUARD_INTERFACE=wg0 \
     WIREGUARD_DEST_IP=10.0.0.2 \
     PUBLIC_INTERFACE=eth0 \
     WIREGUARD_DOCKER_CONTAINER=wireguard \
     bash install.sh
```

### Available Options

| Variable | Default | Description |
|----------|---------|-------------|
| `WEB_PORT` | `5005` | Port for the web UI |
| `WIREGUARD_INTERFACE` | `wg0` | WireGuard interface name |
| `WIREGUARD_DEST_IP` | `10.0.0.2` | Destination IP (Utah server) |
| `PUBLIC_INTERFACE` | `eth0` | Public-facing network interface |
| `WIREGUARD_DOCKER_CONTAINER` | _(empty)_ | Docker container name if WG runs in Docker |
| `APP_DIR` | `/opt/port-forward-manager` | Installation directory |

## Post-Installation Configuration

### If WireGuard runs in Docker

Edit the configuration file:
```bash
sudo nano /opt/port-forward-manager/backend/.env
```

Add or update:
```
WIREGUARD_DOCKER_CONTAINER="wireguard"
```

Then restart:
```bash
sudo systemctl restart port-forward-manager
```

### Changing the Port Range

1. Login as admin
2. Go to Account Settings (gear icon)
3. Update "Port Range Settings"
4. Click Save

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Internet Traffic                         │
│                    (Public IP in CA)                         │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                   Raspberry Pi (CA)                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │   UFW       │  │  iptables   │  │  Port Forward       │  │
│  │  (Firewall) │──│   (NAT)     │──│  Manager (Web UI)   │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
│                          │                                   │
│                          ▼                                   │
│              ┌─────────────────────┐                        │
│              │  WireGuard Tunnel   │                        │
│              │     (wg0)           │                        │
│              └──────────┬──────────┘                        │
└─────────────────────────┼───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                   Linux Server (Utah)                        │
│                      10.0.0.2                                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │  Terraria   │  │    Ark      │  │   Other Game        │  │
│  │   Server    │  │   Server    │  │   Servers           │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

## How It Works

When you add and enable a port forwarding rule (e.g., port 60002):

1. **UFW Allow** - Opens the port on the firewall:
   ```bash
   ufw allow 60002/tcp
   ufw allow 60002/udp
   ```

2. **iptables NAT** - Redirects traffic to WireGuard destination:
   ```bash
   iptables -t nat -A PREROUTING -i eth0 -p tcp --dport 60002 \
     -j DNAT --to-destination 10.0.0.2:60002
   ```

3. **iptables FORWARD** - Allows the forwarded traffic:
   ```bash
   iptables -A FORWARD -i eth0 -o wg0 -p tcp --dport 60002 \
     -d 10.0.0.2 -j ACCEPT
   ```

4. **UFW Route** - Enables forwarding through UFW:
   ```bash
   ufw route allow proto tcp from any to 10.0.0.2 port 60002
   ```

## Useful Commands

```bash
# Service management
sudo systemctl status port-forward-manager
sudo systemctl restart port-forward-manager
sudo systemctl stop port-forward-manager

# View logs
sudo journalctl -u port-forward-manager -f

# Check firewall rules
sudo ufw status verbose
sudo iptables -t nat -L PREROUTING -n -v
sudo iptables -L FORWARD -n -v

# Test API
curl http://localhost:5005/api/
curl -X POST http://localhost:5005/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin"}'
```

## Troubleshooting

### Login fails after fresh install
```bash
# Reset database to recreate admin user
sudo systemctl stop port-forward-manager
sudo rm /opt/port-forward-manager/port_forward.db
sudo systemctl start port-forward-manager
```

### WireGuard shows "DOWN" (Docker)
Make sure the Docker container name is set in `.env`:
```bash
sudo nano /opt/port-forward-manager/backend/.env
# Add: WIREGUARD_DOCKER_CONTAINER="wireguard"
sudo systemctl restart port-forward-manager
```

### Port forwarding not working
1. Check IP forwarding is enabled:
   ```bash
   cat /proc/sys/net/ipv4/ip_forward
   # Should output: 1
   ```

2. Check iptables rules:
   ```bash
   sudo iptables -t nat -L PREROUTING -n -v
   ```

3. Check UFW status:
   ```bash
   sudo ufw status verbose
   ```

### Service won't start
```bash
# Check logs for errors
sudo journalctl -u port-forward-manager -n 50

# Check Python environment
/opt/port-forward-manager/venv/bin/python --version
```

## Uninstall

```bash
# Stop and disable service
sudo systemctl stop port-forward-manager
sudo systemctl disable port-forward-manager

# Remove service file
sudo rm /etc/systemd/system/port-forward-manager.service
sudo systemctl daemon-reload

# Remove application files
sudo rm -rf /opt/port-forward-manager

# Remove UFW rule for web UI
sudo ufw delete allow 5005/tcp
```

## License

MIT License - Feel free to use and modify as needed.
