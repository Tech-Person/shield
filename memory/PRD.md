# Shield - Privacy-First Communication Platform

## Product Requirements Document

### Vision
A self-hosted, privacy-focused Discord replacement with end-to-end encryption, real-time messaging, voice/video, and full administrative control.

### Core Requirements
- E2E encrypted messages (server cannot read content)
- Servers with roles, text/voice channels, permissions
- DMs and group DMs with friends list
- Voice/Video streaming (WebRTC mesh, P2P, up to 10 viewers)
- Share Drive per server (25GB limit), user media 5GB
- Web UI + PWA, Debian deployment package
- Message reactions, threads, GIFs, typing indicators, read receipts
- Admin GUI with passkey auth, user statuses
- Self-destructing status messages
- UI-driven self-updates from GitHub

### Architecture
- Frontend: React (Shadcn UI), deployed on port 3000
- Backend: FastAPI, deployed on port 8001
- Database: MongoDB
- Real-time: WebSockets
- Auth: JWT + WebAuthn Passkeys + 2FA
- Encryption: RSA-OAEP 2048 (key exchange) + AES-256-GCM (message encryption)
- Voice/Video: WebRTC mesh with optional TURN relay (coturn via Docker)

### What's Implemented

#### P0 Features (Complete)
- [x] Authentication (JWT, Passkeys, 2FA, brute force protection)
- [x] Real-time messaging (WebSocket, DMs, channels, threads)
- [x] Server management (create, roles, channels, permissions - 47 flags)
- [x] Share Drive (file upload, text file creation, storage requests)
- [x] Custom emojis and stickers
- [x] Message reactions, threads, GIFs
- [x] Typing indicators and read receipts
- [x] Member role assignment UI
- [x] Debian deployment package (install.sh, uninstall.sh)
- [x] UI-driven self-update from GitHub
- [x] Dynamic frontend API URL for self-hosting
- [x] End-to-End Encryption (E2E) - RSA-OAEP/AES-GCM, multi-device, key backup/restore
- [x] TURN Server Management - Admin controls for coturn Docker container
- [x] WebRTC P2P Voice/Video - TURN credential integration, connection state monitoring, 10-participant cap

#### Bug Fixes (2026-04-09)
- [x] Fixed double message receives in DMs (removed redundant broadcast_dm)
- [x] Fixed messages requiring page reload (dedup in WS handler)
- [x] Fixed file uploads showing [File:Filename] text (proper attachment rendering with download links/image previews)
- [x] Fixed status message save (added Save Status button)
- [x] Fixed server settings not closing on channel click
- [x] Fixed display name not syncing to server members
- [x] Fixed status updates not broadcasting to server members (real-time via channels)
- [x] Fixed new DM not appearing in list (loadConversations called after DM create)
- [x] Added voice channel join/leave sounds (Web Audio API synthesis)
- [x] Added speaking indicator (green glow on avatar when talking)
- [x] Added interactive copy invite link (Popover dropdown with toast)
- [x] Added channel settings gear per channel (visible to managers only)
- [x] Added group DM creation dialog
- [x] Added voice persistence across navigation (voice bar when browsing other views)
- [x] Improved members panel (online/offline sections, status colors, tooltips)
- [x] Added server invites GET endpoint

#### P2 Features (Pending)
- [ ] Self-destructing status messages
- [ ] DM voice/video calls

#### P3 Features (Pending)
- [ ] Native app skeletons (Linux, Windows, iOS, Android)

### Refactoring Notes
- `server.py` is 2870+ lines. Should be split into modular routers (auth.py, messaging.py, admin.py, voice.py, keys.py)
