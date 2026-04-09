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

## Implemented Features (as of 2026-04-09)

### Core
- [x] Auth system (Login, Register, 2FA/TOTP, Passkeys/WebAuthn)
- [x] Server & Channel CRUD (text + voice channels, categories)
- [x] DMs (1:1 and group), DM search
- [x] Real-time messaging via WebSockets
- [x] Message reactions (common emojis)
- [x] Threads (replies)
- [x] Typing indicators
- [x] File uploads (message attachments)
- [x] GIFs via Giphy API (inline rendering in chat + threads)
- [x] PWA manifest + service worker

### Latest Batch (2026-04-09)
- [x] **Custom Emojis & Stickers** — Upload, save to library, use in chat (renders inline)
- [x] **Share Drive** — Full UI: upload files, create/edit text files, copy links, delete, storage usage bar
- [x] **Server Storage Requests** — Owners request more storage, admin approves/denies in dashboard
- [x] **Quick Status Change** — Status popover on user avatar (Online/Away/Busy/Invisible)
- [x] **Escape Key Navigation** — Backs out of settings, drive, conversations, servers
- [x] **GIF rendering in threads** — Fixed: threads now use MessageContent component

### Admin
- [x] Admin Dashboard with stats, charts, server list
- [x] Storage request approval/denial UI
- [x] Admin account auto-seeded on startup

### Infrastructure
- [x] At-rest encryption for text files (Fernet)
- [x] Emergent Object Storage for files/emojis
- [x] Brute-force login protection
- [x] Role/permission system (framework)
- [x] Server invites with codes

## Prioritized Backlog

### P1
- [ ] P2P Voice/Video stream scaling (WebRTC, up to 10 viewers with server fallback)
- [ ] E2E Encryption validation (hybrid approach, key management)
- [ ] Read receipts

### P2
- [ ] Debian deployment script (auto-install dependencies, run as service)
- [ ] Self-destructing status messages (timer-based expiry)

### P3
- [ ] Native app skeletons (Linux, Windows, iOS, Android)
- [ ] Public server discovery (deferred per user)

## Architecture
```
/app/backend/server.py       — All API routes (~1985 lines)
/app/backend/encryption.py   — Fernet encryption helpers
/app/backend/storage_utils.py — Object storage wrapper
/app/backend/websocket_manager.py — WS state management
/app/frontend/src/pages/     — MainApp, Login, Register, Admin, Landing
/app/frontend/src/components/ — ChatArea, ServerSidebar, ChannelSidebar, ShareDrive, EmojiManager, etc.
/app/frontend/src/contexts/  — AuthContext (JWT + WS)
```

## Key DB Collections
- `users`, `servers`, `server_members`, `channels`
- `messages`, `channel_messages`, `thread_replies`, `reactions`
- `conversations`, `files`, `drive_files`
- `custom_emojis`, `saved_emojis`, `storage_requests`
- `invites`, `server_bans`, `passkey_credentials`, `passkey_challenges`
