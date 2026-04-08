# SecureComm - Privacy-Focused Discord Replacement

## Original Problem Statement
Build a privacy-focused Discord replacement with E2E encryption, servers, channels, roles, DMs, group DMs, voice/video calls, screen sharing, share drives, admin dashboard, and multi-platform support (web + PWA).

## Architecture
- **Backend**: FastAPI (Python) with MongoDB (Motor async driver)
- **Frontend**: React with Tailwind CSS, Shadcn/UI components
- **Real-time**: WebSocket (FastAPI native)
- **Encryption**: AES-256 (Fernet) for messages at rest
- **Storage**: Emergent Object Storage for file uploads
- **Auth**: JWT (httpOnly cookies) + 2FA (TOTP/Google Authenticator)

## User Personas
1. **Regular User**: Creates account, joins servers, chats, DMs friends
2. **Server Admin/Owner**: Creates servers, manages channels/roles/permissions
3. **System Admin**: Access admin dashboard, monitor stats, manage platform

## Core Requirements
- [x] User registration and login (email/password + JWT)
- [x] 2FA setup/verify (TOTP with QR code)
- [x] Friend system (add/remove/block by username)
- [x] Direct Messages (1-on-1 + group DMs)
- [x] Message encryption at rest (AES-256)
- [x] DM search across encrypted messages
- [x] Server creation and management
- [x] Text and voice channels
- [x] Role-based permissions system
- [x] Channel messaging with slowmode
- [x] Invite system (codes with expiry/max uses)
- [x] Member management (kick/ban)
- [x] Server share drive (file upload/download/delete)
- [x] Storage limits (5GB user, 25GB server)
- [x] User status (Online/Away/Busy/Invisible) with auto-AFK
- [x] Custom status messages with expiration
- [x] Admin dashboard with statistics
- [x] WebSocket real-time messaging
- [x] Dark "Secure Vault" UI theme

## What's Been Implemented (Apr 8, 2026)
### Stage 1 - Auth & User Foundation ✅
- Registration, login, JWT auth with httpOnly cookies
- 2FA (TOTP) setup, confirm, verify, disable
- User profiles with display name, about, avatar
- Status system with auto-AFK (10 min timeout)
- Brute force protection (5 attempts = 15min lockout)

### Stage 2 - Social & Messaging ✅
- Friend request/accept/reject/remove/block/unblock
- DM conversations (1-on-1 and group)
- Encrypted messages with search capability
- Real-time message delivery via WebSocket

### Stage 3 - Servers & Channels ✅
- Server CRUD with channels and roles
- Text channels with slowmode enforcement
- Voice channel stubs (UI ready)
- Invite system with codes
- Member kick/ban
- Server share drive with storage tracking
- Admin dashboard with stats and charts

## Prioritized Backlog

### P0 (Critical - Next)
- Voice/Video WebRTC implementation
- Screen sharing (P2P up to 10 viewers, server relay fallback)
- File attachments in messages (photo/video inline preview)

### P1 (Important)
- WebRTC signaling server for voice/video
- Server relay logging in admin console
- Video quality selector (up to 2160p/60fps)
- Passkey/WebAuthn support
- Channel permission overrides

### P2 (Enhancement)
- PWA manifest and service worker
- Update check system (GitHub-based)
- Debian deployment package skeleton
- Native app skeletons (Electron/Tauri)
- Message reactions and threading
- Message editing and deletion
- Typing indicators display
- User search improvements
