# Shield - Privacy-Focused Communication Platform (PRD)

## Original Problem Statement
User wants a privacy-focused replacement for Discord named "Shield". Key features: E2E encrypted (hybrid approach - encrypted at rest on server), servers, roles, text/voice channels, DMs, friends list. Voice/video streaming (P2P preferred, server fallback, up to 10 viewers). Share drive for servers (25GB limit). User media limit 5GB. Web UI + PWA + Debian deployment. Features include message reactions, threads, GIFs, typing indicators, read receipts, admin GUI, user statuses, and self-destructing status messages.

## Tech Stack
React + Tailwind/Shadcn | FastAPI | MongoDB | WebSockets | JWT + WebAuthn | Emergent Object Storage | Fernet encryption

## Implemented Features
- [x] Auth (Login, Register, 2FA/TOTP, Passkeys/WebAuthn)
- [x] Server/Channel CRUD, DMs, real-time messaging, reactions, threads, GIFs, typing, file uploads, PWA
- [x] Custom Emojis/Stickers, Share Drive, Storage Requests, Quick Status, Escape Key Nav
- [x] 47-flag permission system, @everyone role, Discord-style Role Editor UI
- [x] **Role assignment per member** (badges + popover add/remove)
- [x] **Debian deployment** (install.sh, uninstall.sh, README.md)
- [x] **Renamed to Shield** (all branding, .env, manifest, service names)
- [x] Admin Dashboard with stats, storage request approval

## Backlog
### P1: P2P Voice/Video (WebRTC), E2E Encryption validation, Read receipts, Extended permission enforcement
### P2: Self-destructing status messages
### P3: Native app skeletons
