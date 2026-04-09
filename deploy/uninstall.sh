#!/usr/bin/env bash
# Shield — Uninstall Script
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
INSTALL_DIR="${SHIELD_DIR:-/opt/shield}"

echo -e "${YELLOW}This will stop and remove Shield services.${NC}"
echo -e "${YELLOW}MongoDB data will NOT be deleted (manual step).${NC}"
read -rp "Continue? [y/N]: " CONFIRM
[[ "${CONFIRM,,}" != "y" ]] && echo "Aborted." && exit 0

echo -e "${GREEN}Stopping services...${NC}"
systemctl stop shield-backend 2>/dev/null || true
systemctl disable shield-backend 2>/dev/null || true
rm -f /etc/systemd/system/shield-backend.service
systemctl daemon-reload

echo -e "${GREEN}Removing nginx config...${NC}"
rm -f /etc/nginx/sites-enabled/shield
rm -f /etc/nginx/sites-available/shield
systemctl restart nginx 2>/dev/null || true

echo -e "${GREEN}Removing application files...${NC}"
rm -rf "${INSTALL_DIR}"

echo ""
echo -e "${GREEN}Shield has been uninstalled.${NC}"
echo -e "${YELLOW}MongoDB is still installed. To remove data:${NC}"
echo -e "  mongosh --eval \"use shield; db.dropDatabase()\""
echo -e "  sudo apt-get purge mongodb-org*"
