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
- **Voice/Video**: WebRTC (P2P with STUN/TURN, quality up to 2160p/60fps)

## User Personas
1. **Regular User**: Creates account, joins servers, chats, DMs friends
2. **Server Admin/Owner**: Creates servers, manages channels/roles/permissions
3. **System Admin**: Access admin dashboard, monitor stats, manage platform

## What's Been Implemented

### Stage 1 - Auth & User Foundation (Apr 8, 2026) ✅
- Registration, login, JWT auth with httpOnly cookies
- 2FA (TOTP) setup, confirm, verify, disable
- User profiles with display name, about, avatar
- Status system with auto-AFK (10 min timeout)
- Brute force protection (5 attempts = 15min lockout)

### Stage 2 - Social & Messaging (Apr 8, 2026) ✅
- Friend request/accept/reject/remove/block/unblock
- DM conversations (1-on-1 and group)
- Encrypted messages with search capability
- Real-time message delivery via WebSocket

### Stage 3 - Servers & Channels (Apr 8, 2026) ✅
- Server CRUD with channels and roles
- Text channels with slowmode enforcement
- Voice channel stubs (UI ready)
- Invite system with codes
- Member kick/ban
- Server share drive with storage tracking
- Admin dashboard with stats and charts

### Stage 4 - Reactions, Threads, Edit/Delete (Apr 9, 2026) ✅
- Emoji reactions on DM and channel messages (12 common emojis)
- Threaded replies with thread panel UI
- Message editing (own messages only)
- Message deletion (own messages only)
- File attachments in chat via object storage

### Stage 5 - Voice/Video & Streaming (Apr 9, 2026) ✅
- WebRTC voice channels with P2P connections
- Video toggle with quality selector (480p-2160p, 30-60fps)
- Screen sharing via getDisplayMedia
- Mute/unmute, video on/off controls
- Join/leave voice channel with participant tracking
- STUN servers (Google's public STUN)

### Stage 6 - Admin & Deployment (Apr 9, 2026) ✅
- Admin dashboard with 8 stat cards + bar chart
- Server listing with storage metrics
- PWA manifest + service worker
- Update check endpoint (/api/system/update-check)

## Prioritized Backlog

### P0 (Next)
- TURN server relay for NAT traversal (currently P2P only)
- Server relay logging in admin console
- Typing indicator display in chat
- Passkey/WebAuthn support

### P1 (Important)
- Debian deployment package
- Native app skeletons (Electron/Tauri)
- GitHub-based auto-update polling
- Channel permission overrides
- Message pinning

### P2 (Enhancement)
- Rich text/markdown in messages
- User profile popover cards
- Server discovery / public servers
- DM calling (voice/video in DMs)
- Notification system (desktop + push)
