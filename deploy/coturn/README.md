# Shield TURN Server (coturn) — Setup & Hardening Guide

## Why ports must be open

Cloudflare Tunnels operate at Layer 7 (HTTP/WS) and **cannot relay raw UDP/TCP media streams**.
Your web UI, API, and WebSocket signaling all go through the tunnel. TURN/STUN need direct access.

**Most calls won't even use TURN** — WebRTC tries direct P2P first (via STUN hole-punching).
TURN only activates when both peers are behind symmetric NATs or restrictive firewalls.

## Required firewall ports

```bash
# UFW example
sudo ufw allow 3478/udp comment "STUN/TURN"
sudo ufw allow 3478/tcp comment "TURN TCP fallback"
sudo ufw allow 49152:65535/udp comment "TURN media relay range"
```

## Built-in security hardening (applied automatically)

When you start TURN from the admin dashboard, these protections are active:

| Protection | What it does |
|---|---|
| `--use-auth-secret` | Time-limited HMAC credentials (6h TTL) — no static passwords |
| `--denied-peer-ip=10.x/172.x/192.168.x` | Blocks relay to your internal network (anti-SSRF) |
| `--no-multicast-peers` | Blocks multicast relay abuse |
| `--max-bps=1500000` | 1.5 Mbps cap per session (prevents bandwidth abuse) |
| `--total-quota=100` | Max 100 concurrent relay sessions |
| `--user-quota=10` | Max 10 sessions per user |
| `--stale-nonce=600` | Nonce expires every 10 minutes |
| `--no-tcp-relay` | UDP relay only (shrinks TCP attack surface) |

## Additional hardening (recommended)

### 1. Rate-limit TURN port with iptables
```bash
# Limit new TURN connections to 20/sec per source IP
sudo iptables -A INPUT -p udp --dport 3478 -m state --state NEW -m recent --set
sudo iptables -A INPUT -p udp --dport 3478 -m state --state NEW -m recent --update --seconds 1 --hitcount 20 -j DROP
```

### 2. Restrict source IPs (if users are known)
```bash
# Only allow TURN from specific IP ranges
sudo ufw allow from 203.0.113.0/24 to any port 3478 proto udp
```

### 3. Monitor for abuse
```bash
# Check active TURN sessions
docker exec shield-coturn turnadmin -l

# Watch logs
docker logs -f shield-coturn 2>&1 | grep "session"
```

### 4. Use a strong shared secret
Generate a proper secret (set via Admin Dashboard → TURN config):
```bash
openssl rand -hex 32
```

### 5. Fail2ban for TURN (optional)
```bash
# /etc/fail2ban/filter.d/coturn.conf
[Definition]
failregex = .*401.*from\s+<HOST>
```

## Resource requirements

- **RAM**: ~256MB base + ~2MB per concurrent relay
- **CPU**: 1 core handles hundreds of streams
- **Bandwidth**: ~100kbps/audio, ~2.5Mbps/1080p video per relayed stream
- **Same machine is fine** for small deployments — coturn only sees encrypted DTLS-SRTP media, never plaintext

## Manual Docker usage (alternative to admin UI)

```bash
docker run -d --name shield-coturn --network=host --restart=unless-stopped \
  coturn/coturn:latest \
  --listening-port=3478 --realm=shield.local \
  --use-auth-secret --static-auth-secret=YOUR_SECRET \
  --no-cli --fingerprint --lt-cred-mech \
  --min-port=49152 --max-port=65535 \
  --denied-peer-ip=10.0.0.0-10.255.255.255 \
  --denied-peer-ip=172.16.0.0-172.31.255.255 \
  --denied-peer-ip=192.168.0.0-192.168.255.255 \
  --no-multicast-peers --no-tcp-relay \
  --max-bps=1500000 --total-quota=100 --user-quota=10
```
