Port Forward Manager - Deployment Package
==========================================

Files included:
- server.py          - The FastAPI backend
- index.html         - Frontend entry point
- static/            - Frontend CSS and JS files
- requirements.txt   - Python dependencies
- install-raspberry-pi.sh - Installation script

INSTALLATION STEPS:
-------------------

1. Copy ALL files to your Raspberry Pi:
   scp -r * pi@<your-pi-ip>:/tmp/port-forward/

2. SSH into your Pi:
   ssh pi@<your-pi-ip>

3. Run the installer as root:
   cd /tmp/port-forward
   sudo bash install-raspberry-pi.sh

4. Start the service:
   sudo systemctl start port-forward-manager
   sudo systemctl enable port-forward-manager

5. Access the web UI:
   http://<your-pi-ip>:5005

Default login: admin / admin
(You will be asked to change password on first login)

TROUBLESHOOTING:
----------------
- Check service status: sudo systemctl status port-forward-manager
- View logs: sudo journalctl -u port-forward-manager -f
- Restart service: sudo systemctl restart port-forward-manager
