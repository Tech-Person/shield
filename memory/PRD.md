# Port Forward Manager - PRD

## Original Problem Statement
Build a web app to manage port forwarding on a Raspberry Pi with:
- WireGuard tunnel forwarding traffic from CA Pi (ports 60000-61000) to Utah game server (10.0.0.2)
- User authentication with password hashing
- Add/modify/remove port forwarding rules via UI
- Execute iptables NAT PREROUTING and UFW commands
- Run as systemd service on boot
- Prevent duplicate rules
- Role-based access (admin/user)

## Architecture
- **Backend**: FastAPI + MongoDB (motor async driver)
- **Frontend**: React + Tailwind CSS + Shadcn UI
- **Auth**: JWT tokens with bcrypt password hashing
- **System Commands**: iptables + UFW (MOCKED in dev, real on Pi)

## User Personas
1. **Admin** - Can manage all port rules, create/delete users
2. **Basic User** - Can manage port rules only

## Core Requirements (Implemented)
- [x] User authentication with JWT + bcrypt password hashing
- [x] Admin must change default password on first login
- [x] Dashboard with stats cards and port rules table
- [x] Add/edit/delete port forwarding rules
- [x] Toggle rules on/off (with visual status indicator)
- [x] Warning for ports outside safe range (60000-61000)
- [x] Account management page
- [x] Admin can create new users
- [x] Password change functionality
- [x] Role-based access control
- [x] Dark theme with blue tech styling
- [x] Raspberry Pi installation script

## What's Been Implemented (Jan 2026)
1. Backend API with all CRUD endpoints for users and rules
2. JWT authentication with role-based access
3. MongoDB models for users and port_rules collections
4. Simulated system commands (iptables/UFW) for dev environment
5. Complete React frontend with:
   - Login page
   - Dashboard with stats and rules table
   - Account management page
   - Change password dialog (forced on first login)
   - Add/edit/delete rule dialogs
6. Installation script for Raspberry Pi deployment

## Prioritized Backlog
### P0 (Critical)
- All implemented ✓

### P1 (Important)
- Activity logging for audit trail
- Rule import/export functionality

### P2 (Nice to Have)
- Connection statistics per rule
- Email notifications for rule changes
- Dark/light theme toggle

## Next Tasks
1. Deploy to actual Raspberry Pi
2. Test with real iptables/UFW commands (set SIMULATION_MODE=false)
3. Configure WireGuard tunnel
4. Add more game server port presets
