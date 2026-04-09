# Shield TURN Server (coturn) Docker Setup
#
# This runs coturn as a Docker container for WebRTC media relay.
# The Shield admin dashboard provides start/stop controls.
#
# Manual usage (if you prefer not to use the admin UI):
#
#   docker run -d --name shield-coturn --network=host --restart=unless-stopped \
#     coturn/coturn:latest \
#     --listening-port=3478 --tls-listening-port=3479 \
#     --realm=shield.local --use-auth-secret \
#     --static-auth-secret=YOUR_SECRET_HERE \
#     --no-cli --no-tls --no-dtls \
#     --fingerprint --lt-cred-mech \
#     --min-port=49152 --max-port=65535
#
# Required firewall ports:
#   - UDP 3478 (STUN/TURN)
#   - TCP 3478 (TURN TCP fallback)
#   - TCP 3479 (TURNS / TLS)
#   - UDP 49152-65535 (media relay range)
#
# Resource requirements:
#   - ~256MB RAM base + ~2MB per concurrent relay
#   - 1 CPU core handles hundreds of streams
#   - Bandwidth: ~100kbps per audio stream, ~2.5Mbps per 1080p video stream
