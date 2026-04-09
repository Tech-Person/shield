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
- [x] **End-to-End Encryption (E2E)** - RSA-OAEP/AES-GCM, multi-device, key backup/restore
- [x] **TURN Server Management** - Admin controls for coturn Docker container
- [x] **WebRTC P2P Voice/Video** - TURN credential integration, connection state monitoring, 10-participant cap

#### P2 Features (Pending)
- [ ] Self-destructing status messages

#### P3 Features (Pending)
- [ ] Native app skeletons (Linux, Windows, iOS, Android)

### E2E Encryption Design
- **Key Generation**: RSA-OAEP 2048-bit key pair generated per device on login
- **Private Key Storage**: IndexedDB (never leaves device)
- **Public Key Distribution**: Uploaded to server, fetched as key bundles
- **Message Flow**: AES-256-GCM symmetric key per message, wrapped with each recipient device's RSA public key
- **Multi-Device**: Each device has unique key pair; key backup (PBKDF2 600k iterations + AES-GCM passphrase encryption) enables cross-device restore
- **Backward Compatible**: Old server-encrypted messages still readable; new messages use E2E

### TURN Server
- Managed via Docker (coturn container)
- Admin dashboard: start/stop/status controls, config editor
- Time-limited HMAC credentials for clients
- Required ports: UDP 3478, TCP 3478/3479, UDP 49152-65535
