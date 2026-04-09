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
- [x] Message reactions (common emojis)
- [x] Threads (replies, inherits channel permissions)
- [x] Typing indicators
- [x] File uploads (message attachments)
- [x] GIFs via Giphy API (inline rendering in chat + threads)
- [x] PWA manifest + service worker
- [x] Custom Emojis & Stickers — Upload, save to library, use in chat
- [x] Share Drive — Upload files, create/edit text files, copy links, storage usage bar
- [x] Server Storage Requests — Owners request more storage, admin approves/denies
- [x] Quick Status Change — Status popover on user avatar (Online/Away/Busy/Invisible)
- [x] Escape Key Navigation — Backs out of settings, drive, conversations, servers
- [x] GIF rendering in threads — Uses MessageContent component

### Role Permission System (2026-04-09)
- [x] **47 permission bit flags** organized in 8 categories:
  - General Server (9): View Channels, Manage Channels, Manage Roles, Create/Manage Expressions, View Audit Log, View Server Insights, Manage Webhooks, Manage Server
  - Membership (6): Create Invite, Change/Manage Nicknames, Kick/Ban/Timeout Members
  - Text Channel (16): Send Messages, Threads, Embed Links, Attach Files, Reactions, External Emoji, Mention Everyone, Manage Messages, Pin Messages, Bypass Slowmode, Manage Threads, Read History, TTS, Voice Messages, Polls
  - Voice Channel (9): Connect, Speak, Video, Voice Activity, Priority Speaker, Mute/Deafen/Move Members, Set Status
  - Apps (3): Application Commands, Activities, External Apps
  - Stage (1): Request to Speak
  - Events (2): Create/Manage Events
  - Advanced (1): Administrator (bypasses all checks)
- [x] **@everyone role** auto-created with default permissions on all servers
- [x] **Permission enforcement** on: create channel (MANAGE_CHANNELS), send messages (SEND_MESSAGES), kick (KICK_MEMBERS), ban (BAN_MEMBERS), bypass slowmode (BYPASS_SLOWMODE)
- [x] **Server owner** always has ALL permissions (bypasses role checks)
- [x] **Discord-style Role Editor UI** — Role list left panel, permission toggles right panel, create/delete roles, clear permissions, save changes
- [x] **Migration** — Existing servers' @everyone roles updated to new expanded defaults on startup
- [x] Discarded: Soundboard permissions, Private threads (threads inherit channel permissions)

### Admin
- [x] Admin Dashboard with stats, charts, server list
- [x] Storage request approval/denial UI
- [x] Admin account auto-seeded on startup

### Infrastructure
- [x] At-rest encryption for text files (Fernet)
- [x] Emergent Object Storage for files/emojis
- [x] Brute-force login protection
- [x] Server invites with codes

## Prioritized Backlog

### P1
- [ ] P2P Voice/Video stream scaling (WebRTC, up to 10 viewers with server fallback)
- [ ] E2E Encryption validation (hybrid approach, key management)
- [ ] Read receipts

### P2
- [ ] Debian deployment script (auto-install dependencies, run as service)
- [ ] Self-destructing status messages (timer-based expiry)
- [ ] Extend permission enforcement to more endpoints (manage messages, pin, manage roles, manage server, attach files, reactions)

### P3
- [ ] Native app skeletons (Linux, Windows, iOS, Android)

## Architecture
```
/app/backend/server.py       — All API routes (~2050 lines)
/app/backend/models.py       — Pydantic schemas + Permissions class (47 bit flags)
/app/backend/encryption.py   — Fernet encryption helpers
/app/backend/storage_utils.py — Object storage wrapper
/app/backend/websocket_manager.py — WS state management
/app/frontend/src/pages/     — MainApp, Login, Register, Admin, Landing
/app/frontend/src/components/ — ChatArea, ServerSidebar, ChannelSidebar, RoleEditor, ShareDrive, EmojiManager, etc.
/app/frontend/src/contexts/  — AuthContext (JWT + WS)
```

## Key DB Collections
- `users`, `servers`, `server_members`, `channels`
- `messages`, `channel_messages`, `thread_replies`, `reactions`
- `conversations`, `files`, `drive_files`
- `custom_emojis`, `saved_emojis`, `storage_requests`
- `invites`, `server_bans`, `passkey_credentials`, `passkey_challenges`
