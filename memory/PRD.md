# SecureComm - Privacy-Focused Communication Platform (PRD)

## Original Problem Statement
User wants a privacy-focused replacement for Discord. Key features: E2E encrypted (hybrid approach - encrypted at rest on server), servers, roles, text/voice channels, DMs, friends list. Voice/video streaming (P2P preferred, server fallback, up to 10 viewers). Share drive for servers (25GB limit, files can be added/removed, simple text file creation). User media limit 5GB. Web UI + PWA, with a deployable package for Debian. Features include message reactions, threads, GIFs, typing indicators, read receipts, admin GUI (locked behind passkey/admin), user statuses (Online/Away/Busy/Invisible), and self-destructing status messages.

## Tech Stack
- Frontend: React + Tailwind CSS + Shadcn UI
- Backend: FastAPI (Python)
- Database: MongoDB
- Real-time: WebSockets
- Auth: JWT cookies + WebAuthn (Passkeys)
- Storage: Emergent Object Storage
- Encryption: At-rest encryption (Fernet)

## Implemented Features

### Core
- [x] Auth system (Login, Register, 2FA/TOTP, Passkeys/WebAuthn)
- [x] Server & Channel CRUD (text + voice channels, categories)
- [x] DMs (1:1 and group), DM search
- [x] Real-time messaging via WebSockets
- [x] Message reactions, Threads (inherits channel perms)
- [x] Typing indicators, File uploads, GIFs (Giphy), PWA
- [x] Custom Emojis & Stickers, Share Drive, Storage Requests
- [x] Quick Status Change, Escape Key Navigation

### Role Permission System (2026-04-09)
- [x] 47 permission bit flags in 8 categories (General, Membership, Text, Voice, Apps, Stage, Events, Advanced)
- [x] @everyone role auto-created with defaults on all servers
- [x] Permission enforcement on key endpoints (channels, messages, kick, ban, slowmode)
- [x] Server owner always has ALL permissions
- [x] Discord-style Role Editor UI with toggle switches
- [x] **Role Assignment per Member** — Members tab shows role badges, + Add Role popover to assign, X to remove

### Debian Deployment (2026-04-09)
- [x] `deploy/install.sh` — Automated installer (MongoDB 7.0, Node.js 20, Python venv, nginx, systemd, Let's Encrypt TLS)
- [x] `deploy/uninstall.sh` — Clean removal of services and files
- [x] `deploy/README.md` — Full documentation with configuration, management, troubleshooting

### Admin
- [x] Admin Dashboard with stats, charts, server list, storage request approval

## Prioritized Backlog

### P1
- [ ] P2P Voice/Video stream scaling (WebRTC, up to 10 viewers with server fallback)
- [ ] E2E Encryption validation (hybrid approach, key management)
- [ ] Read receipts
- [ ] Extend permission enforcement to more endpoints

### P2
- [ ] Self-destructing status messages (timer-based expiry)

### P3
- [ ] Native app skeletons (Linux, Windows, iOS, Android)

## Architecture
```
/app/backend/server.py          — All API routes (~2050 lines)
/app/backend/models.py          — Pydantic schemas + 47-flag Permissions
/app/backend/encryption.py      — Fernet encryption
/app/backend/storage_utils.py   — Object storage wrapper
/app/frontend/src/components/   — ChatArea, RoleEditor, ShareDrive, EmojiManager, etc.
/app/frontend/src/pages/        — MainApp, Login, Register, Admin, Landing
/app/deploy/                    — install.sh, uninstall.sh, README.md
```
