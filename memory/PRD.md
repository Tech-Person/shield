# Shield - Privacy-First Communication Platform

## Product Requirements Document

### Vision
A self-hosted, privacy-focused Discord replacement with end-to-end encryption, real-time messaging, voice/video, and full administrative control.

### Architecture
- Frontend: React (Shadcn UI), port 3000
- Backend: FastAPI, port 8001
- Database: MongoDB
- Real-time: WebSockets (multi-connection per user)
- Auth: JWT + WebAuthn Passkeys + 2FA
- Encryption: RSA-OAEP 2048 + AES-256-GCM
- Voice/Video: WebRTC mesh + coturn TURN relay

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

#### Bug Fixes (2026-04-09, Batch 1)
- [x] Fixed double message receives in DMs
- [x] Fixed file uploads showing [File:Filename] text
- [x] Fixed status message save, server settings not closing
- [x] Fixed display name sync, new DM not appearing
- [x] Added persistent voice across navigation

#### Bug Fixes (2026-04-09, Batch 2)
- [x] **Fixed WebSocket manager** - Now supports multiple connections per user (multi-tab), send_personal only removes dead individual connections instead of nuking the entire user
- [x] **Fixed status makes all users offline** - Status broadcasts directly to server members (not per-channel spam), MainApp updates member status locally without full refetch
- [x] **Fixed messages not updating live** - Removed duplicate broadcast_dm, fixed orphaned decorator on DM messages endpoint
- [x] **Fixed voice not updating live** - VoiceChannel now subscribes to channel on mount; join_voice auto-subscribes in backend
- [x] **Fixed voice showing users alone** - Same subscription fix enables voice_state_update to reach all participants

#### Voice Persistence Fix (2026-04-09)
- [x] **Global Voice Manager** (`voiceManager.js`) - WebRTC peer connections, streams, and Audio() elements now live at MainApp level and survive React routing/unmounting
- [x] **VoiceChannel refactored** - Stripped of local WebRTC state, now a pure UI view consuming voiceManager props
- [x] **VoiceFloat widget** (`VoiceFloat.js`) - Persistent floating bottom-left panel with mute/deafen/disconnect controls visible on all screens when in a voice call
- [x] **Navigate-back** - Clicking the float returns user to the active voice channel view

#### P2 Features (Pending)
- [ ] Self-destructing status messages

#### P3 Features (Pending)
- [ ] Native app skeletons (Linux, Windows, iOS, Android)

### Refactoring Notes
- `server.py` is 2970+ lines — split into modular routers recommended
