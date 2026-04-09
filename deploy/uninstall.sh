#!/usr/bin/env bash
# SecureComm — Uninstall Script
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
INSTALL_DIR="${SECURECOMM_DIR:-/opt/securecomm}"

echo -e "${YELLOW}This will stop and remove SecureComm services.${NC}"
echo -e "${YELLOW}MongoDB data will NOT be deleted (manual step).${NC}"
read -rp "Continue? [y/N]: " CONFIRM
[[ "${CONFIRM,,}" != "y" ]] && echo "Aborted." && exit 0

echo -e "${GREEN}Stopping services...${NC}"
systemctl stop securecomm-backend 2>/dev/null || true
systemctl disable securecomm-backend 2>/dev/null || true
rm -f /etc/systemd/system/securecomm-backend.service
systemctl daemon-reload

echo -e "${GREEN}Removing nginx config...${NC}"
rm -f /etc/nginx/sites-enabled/securecomm
rm -f /etc/nginx/sites-available/securecomm
systemctl restart nginx 2>/dev/null || true

echo -e "${GREEN}Removing application files...${NC}"
rm -rf "${INSTALL_DIR}"

echo ""
echo -e "${GREEN}SecureComm has been uninstalled.${NC}"
echo -e "${YELLOW}MongoDB is still installed. To remove data:${NC}"
echo -e "  mongosh --eval \"use securecomm; db.dropDatabase()\""
echo -e "  sudo apt-get purge mongodb-org*"
