# Shield - Privacy-Focused Communication Platform (PRD)

## Original Problem Statement
Privacy-focused Discord replacement named "Shield". E2E encrypted (at-rest), servers/roles/channels, DMs, voice/video, share drive, PWA + Debian deployment.

## Implemented Features
- [x] Auth (Login, Register, 2FA/TOTP, Passkeys/WebAuthn)
- [x] Server/Channel CRUD, DMs, real-time messaging, reactions, threads, GIFs, typing, file uploads, PWA
- [x] Custom Emojis/Stickers, Share Drive, Storage Requests, Quick Status, Escape Key Nav
- [x] 47-flag permission system, @everyone role, Discord-style Role Editor, Role Assignment per Member
- [x] Debian deployment (install.sh with interactive prompts, uninstall.sh, README.md)
- [x] Local file storage fallback for self-hosted (no Emergent dependency)
- [x] **UI-Driven Update System** — Admin Dashboard panel: configurable GitHub repo URL, check for updates (shows recent commits), apply update (git pull + pip install + yarn build + service restart), background task with live status/log polling
- [x] Admin Dashboard with stats, storage requests, server list
- [x] Renamed to Shield throughout

## Backlog
### P1: P2P Voice/Video (WebRTC), E2E Encryption validation, Read receipts, Extended permission enforcement
### P2: Self-destructing status messages
### P3: Native app skeletons
