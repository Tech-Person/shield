# Shield - Privacy-First Communication Platform

## Product Requirements Document

### Vision
A self-hosted, privacy-focused Discord replacement with end-to-end encryption, real-time messaging, voice/video, and full administrative control.

### Architecture
- Frontend: React (Shadcn UI), port 3000
- Backend: FastAPI (modular routers), port 8001
- Database: MongoDB
- Real-time: WebSockets (multi-connection per user)
- Auth: JWT + WebAuthn Passkeys + 2FA
- Encryption: RSA-OAEP 2048 + AES-256-GCM
- Voice/Video: WebRTC mesh + coturn TURN relay

### Backend Architecture (Refactored)
```
/app/backend/
  server.py          # Slim orchestrator (~220 lines): WebSocket, startup, CORS, router mounting
  deps.py            # Shared dependencies: db, auth helpers, permissions
  routes/
    auth.py          # Auth: register, login, 2FA, passkeys, logout, refresh
    users.py         # Users: profile, status, search
    friends.py       # Friends: request, accept, reject, block, unblock
    keys.py          # E2E keys: device register, backup, bundle
    dm.py            # DMs: create, messages, calls, threads, reactions, read receipts
    servers.py       # Servers: CRUD, invites, join
    channels.py      # Channels: CRUD, messages, voice, GIFs, read receipts, system update-check
    roles.py         # Roles: CRUD, assign, kick, ban
    files.py         # Files: upload, download, share drive, text files
    emojis.py        # Emojis: upload, save, delete
    admin.py         # Admin: stats, TURN, storage requests, updates
  websocket_manager.py
  models.py
  encryption.py
  storage_utils.py
```

### What's Implemented

#### P0 Features (Complete)
- [x] Authentication (JWT, Passkeys, 2FA, brute force protection)
- [x] Real-time messaging (WebSocket, DMs, channels, threads)
- [x] Server management (create, roles, channels, permissions - 47 flags)
- [x] Share Drive (file upload, text file creation, storage requests)
- [x] Custom emojis and stickers
- [x] Message reactions, threads, GIFs, typing indicators, read receipts
- [x] Member role assignment UI
- [x] Debian deployment package (install.sh, uninstall.sh)
- [x] UI-driven self-update from GitHub
- [x] Dynamic frontend API URL for self-hosting
- [x] End-to-End Encryption (E2E) - multi-device, key backup/restore
- [x] TURN Server Management - Admin coturn Docker controls
- [x] WebRTC P2P Voice/Video - TURN credentials, 10-participant cap
- [x] DM Voice/Video Calls - Ringing/answer/decline/end, WebRTC signaling
- [x] Group DM creation
- [x] Channel settings per channel (name, topic, slowmode, delete)
- [x] Copy invite link with feedback
- [x] Voice join/leave sounds, speaking indicator
- [x] Global voice persistence (VoiceFloat widget)
- [x] Remote speaking visual indicators
- [x] Voice connect/disconnect toasts
- [x] Ping/latency display

#### Refactoring (Complete - 2026-04-10)
- [x] Backend modular routers: Split server.py from 2976 -> 220 lines
- [x] 11 route modules under /app/backend/routes/
- [x] Shared deps in deps.py (db, auth, permissions)
- [x] Fixed MongoDB read_receipts partial indexes
- [x] All 35/35 API tests passed post-refactor

#### P1 Features (Pending)
- [ ] DM ringing (audio + visual incoming call alerts)

#### P2 Features (Pending)
- [ ] Self-destructing status messages

#### P3 Features (Pending)
- [ ] Native app skeletons (Linux)
