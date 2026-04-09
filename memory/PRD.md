# SecureComm - Privacy-Focused Discord Replacement

## Architecture
- **Backend**: FastAPI (Python) with MongoDB (Motor async driver)
- **Frontend**: React with Tailwind CSS, Shadcn/UI components
- **Real-time**: WebSocket (FastAPI native)
- **Encryption**: AES-256 (Fernet) for messages at rest
- **Storage**: Emergent Object Storage for file uploads
- **Auth**: JWT (httpOnly cookies) + 2FA (TOTP) + Passkeys (WebAuthn)
- **Voice/Video**: WebRTC (P2P with STUN)
- **GIFs**: GIPHY API (proxied through backend)
- **PWA**: Service worker + manifest for installable app

## All Implemented Features

### Auth & Security
- Registration, login with JWT httpOnly cookies
- 2FA (TOTP with QR code)
- Passkey/WebAuthn registration and authentication
- Brute force protection (5 attempts = 15min lockout)
- AES-256 message encryption at rest

### Messaging
- DMs (1-on-1 and group)
- Channel messages with slowmode
- GIF search & inline sending (GIPHY API)
- Emoji reactions (12 common emojis)
- Threaded replies
- Message edit/delete (own messages)
- File attachments via object storage
- Encrypted message search
- Typing indicators via WebSocket

### Servers
- Server CRUD, channels, roles, permissions
- Text + voice channels
- Invite codes with expiry/max uses
- Member kick/ban
- Share drive with storage limits (5GB user, 25GB server)
- Role-based permission system

### Voice/Video
- WebRTC voice channels with P2P
- Video with quality selector (480p-2160p, 30-60fps)
- Screen sharing via getDisplayMedia
- Mute/video/screen share controls

### Platform
- Admin dashboard with stats + charts
- User status (Online/Away/Busy/Invisible) with auto-AFK
- Custom status messages with expiration
- Desktop notifications (browser Notification API)
- PWA manifest + service worker
- Update check endpoint

## Prioritized Backlog
### P0
- TURN server relay for NAT traversal
- Debian deployment package skeleton

### P1
- Native app skeletons (Electron/Tauri)
- GitHub-based auto-update polling
- Channel permission overrides
- Message pinning
- Rich text/markdown rendering

### P2
- User profile popover cards
- DM calling (voice/video in DMs)
- Push notifications (FCM/APNs)
