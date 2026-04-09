"""
E2E Encryption and TURN Server Management API Tests
Tests for:
- E2E key management endpoints (/api/keys/*)
- TURN server admin endpoints (/api/admin/turn/*)
- E2E encrypted message sending in DMs and channels
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@shield.local"
ADMIN_PASSWORD = "SecureAdmin2024!"

@pytest.fixture(scope="module")
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session

@pytest.fixture(scope="module")
def admin_auth(api_client):
    """Login as admin and return session with cookies"""
    response = api_client.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    if response.status_code != 200:
        pytest.skip(f"Admin login failed: {response.status_code} - {response.text}")
    return api_client

@pytest.fixture(scope="module")
def test_user(api_client):
    """Create a test user for E2E testing"""
    unique_id = str(uuid.uuid4())[:8]
    user_data = {
        "username": f"TEST_e2e_user_{unique_id}",
        "email": f"test_e2e_{unique_id}@shield.local",
        "password": "TestPass123!"
    }
    response = api_client.post(f"{BASE_URL}/api/auth/register", json=user_data)
    if response.status_code not in [200, 201]:
        pytest.skip(f"Test user creation failed: {response.status_code}")
    return {"session": api_client, "user": response.json().get("user", {}), "credentials": user_data}


class TestE2EKeyManagement:
    """E2E Key Management API Tests"""
    
    def test_register_device_key(self, admin_auth):
        """POST /api/keys/register - Register a device key"""
        device_id = f"test-device-{uuid.uuid4()}"
        public_key_jwk = {
            "kty": "RSA",
            "n": "test_modulus_base64",
            "e": "AQAB",
            "alg": "RSA-OAEP-256",
            "use": "enc"
        }
        response = admin_auth.post(f"{BASE_URL}/api/keys/register", json={
            "device_id": device_id,
            "public_key_jwk": public_key_jwk
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("status") == "ok"
        print(f"✓ Device key registered: {device_id[:16]}...")
    
    def test_get_my_devices(self, admin_auth):
        """GET /api/keys/devices - Get current user's devices"""
        response = admin_auth.get(f"{BASE_URL}/api/keys/devices")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Expected list of devices"
        print(f"✓ Retrieved {len(data)} device(s)")
    
    def test_get_user_keys(self, admin_auth):
        """GET /api/keys/user/{user_id} - Get another user's public keys"""
        # First get admin's user ID
        me_response = admin_auth.get(f"{BASE_URL}/api/auth/me")
        assert me_response.status_code == 200
        user_id = me_response.json().get("user", {}).get("id")
        
        response = admin_auth.get(f"{BASE_URL}/api/keys/user/{user_id}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Expected list of keys"
        print(f"✓ Retrieved {len(data)} key(s) for user {user_id[:8]}...")
    
    def test_get_key_bundle(self, admin_auth):
        """POST /api/keys/bundle - Get key bundle for multiple users"""
        # Get admin's user ID
        me_response = admin_auth.get(f"{BASE_URL}/api/auth/me")
        user_id = me_response.json().get("user", {}).get("id")
        
        response = admin_auth.post(f"{BASE_URL}/api/keys/bundle", json={
            "user_ids": [user_id]
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert isinstance(data, dict), "Expected dict of user_id -> keys"
        print(f"✓ Key bundle retrieved for {len(data)} user(s)")
    
    def test_store_key_backup(self, admin_auth):
        """POST /api/keys/backup - Store encrypted key backup"""
        response = admin_auth.post(f"{BASE_URL}/api/keys/backup", json={
            "encrypted_private_key": "base64_encrypted_key_data_here",
            "salt": "base64_salt_here",
            "iv": "base64_iv_here"
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("status") == "ok"
        print("✓ Key backup stored successfully")
    
    def test_get_key_backup(self, admin_auth):
        """GET /api/keys/backup - Retrieve encrypted key backup"""
        response = admin_auth.get(f"{BASE_URL}/api/keys/backup")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        # Should return backup data or empty dict
        assert isinstance(data, dict), "Expected dict response"
        if data:
            assert "encrypted_private_key" in data or data == {}
        print(f"✓ Key backup retrieved: {'has data' if data else 'empty'}")
    
    def test_delete_device_key(self, admin_auth):
        """DELETE /api/keys/device/{device_id} - Remove a device key"""
        # First register a device to delete
        device_id = f"test-delete-device-{uuid.uuid4()}"
        admin_auth.post(f"{BASE_URL}/api/keys/register", json={
            "device_id": device_id,
            "public_key_jwk": {"kty": "RSA", "n": "test", "e": "AQAB"}
        })
        
        response = admin_auth.delete(f"{BASE_URL}/api/keys/device/{device_id}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("status") == "ok"
        print(f"✓ Device key deleted: {device_id[:16]}...")


class TestTURNServerManagement:
    """TURN Server Admin API Tests"""
    
    def test_get_turn_config_admin(self, admin_auth):
        """GET /api/admin/turn/config - Get TURN config (admin only)"""
        response = admin_auth.get(f"{BASE_URL}/api/admin/turn/config")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "key" in data or "enabled" in data or data == {"key": "turn_server", "enabled": False, "host": "", "port": 3478, "shared_secret": "", "status": "stopped"}
        print(f"✓ TURN config retrieved: enabled={data.get('enabled', False)}")
    
    def test_update_turn_config(self, admin_auth):
        """PUT /api/admin/turn/config - Update TURN config"""
        response = admin_auth.put(f"{BASE_URL}/api/admin/turn/config", json={
            "host": "turn.test.local",
            "port": 3478,
            "shared_secret": "test-secret-123",
            "realm": "test.local"
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("status") == "ok"
        print("✓ TURN config updated successfully")
    
    def test_get_turn_status(self, admin_auth):
        """GET /api/admin/turn/status - Get TURN server status"""
        response = admin_auth.get(f"{BASE_URL}/api/admin/turn/status")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "container_status" in data
        print(f"✓ TURN status: {data.get('container_status')}")
    
    def test_get_turn_credentials_user(self, admin_auth):
        """GET /api/turn/credentials - Get TURN credentials for WebRTC"""
        response = admin_auth.get(f"{BASE_URL}/api/turn/credentials")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "ice_servers" in data
        assert isinstance(data["ice_servers"], list)
        assert len(data["ice_servers"]) > 0
        # Should have at least STUN server
        stun_found = any("stun:" in str(s.get("urls", "")) for s in data["ice_servers"])
        assert stun_found, "Expected at least one STUN server"
        print(f"✓ ICE servers retrieved: {len(data['ice_servers'])} server(s)")
    
    def test_turn_config_requires_admin(self, api_client):
        """Verify TURN admin endpoints require admin role"""
        # Create a non-admin user
        unique_id = str(uuid.uuid4())[:8]
        reg_response = api_client.post(f"{BASE_URL}/api/auth/register", json={
            "username": f"TEST_nonadmin_{unique_id}",
            "email": f"test_nonadmin_{unique_id}@shield.local",
            "password": "TestPass123!"
        })
        if reg_response.status_code not in [200, 201]:
            pytest.skip("Could not create non-admin user")
        
        # Try to access admin endpoint
        response = api_client.get(f"{BASE_URL}/api/admin/turn/config")
        assert response.status_code == 403, f"Expected 403 for non-admin, got {response.status_code}"
        print("✓ TURN config correctly requires admin role")


class TestE2EEncryptedMessages:
    """E2E Encrypted Message Tests"""
    
    def test_send_e2e_dm_message(self, admin_auth):
        """POST /api/dm/{id}/messages - Send E2E encrypted DM"""
        # First create a test user to DM
        unique_id = str(uuid.uuid4())[:8]
        reg_response = admin_auth.post(f"{BASE_URL}/api/auth/register", json={
            "username": f"TEST_dm_recipient_{unique_id}",
            "email": f"test_dm_{unique_id}@shield.local",
            "password": "TestPass123!"
        })
        if reg_response.status_code not in [200, 201]:
            pytest.skip("Could not create DM recipient")
        recipient_id = reg_response.json().get("user", {}).get("id")
        
        # Re-login as admin
        admin_auth.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        
        # Create DM conversation
        dm_response = admin_auth.post(f"{BASE_URL}/api/dm/create", json={
            "recipient_id": recipient_id,
            "content": "init"
        })
        assert dm_response.status_code == 200, f"DM create failed: {dm_response.status_code}"
        conv_id = dm_response.json().get("id")
        
        # Send E2E encrypted message
        response = admin_auth.post(f"{BASE_URL}/api/dm/{conv_id}/messages", json={
            "content": "",
            "e2e": True,
            "encrypted_content": "base64_encrypted_message_content",
            "iv": "base64_initialization_vector",
            "encrypted_keys": {
                "device-1": "base64_wrapped_aes_key_for_device_1",
                "device-2": "base64_wrapped_aes_key_for_device_2"
            }
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("e2e") == True, "Message should have e2e flag"
        assert "encrypted_content" in data, "Message should have encrypted_content"
        assert "iv" in data, "Message should have iv"
        assert "encrypted_keys" in data, "Message should have encrypted_keys"
        print(f"✓ E2E DM message sent: {data.get('id')[:8]}...")
    
    def test_retrieve_e2e_dm_messages(self, admin_auth):
        """GET /api/dm/{id}/messages - Retrieve E2E messages (should pass through encrypted)"""
        # Get conversations
        convos_response = admin_auth.get(f"{BASE_URL}/api/dm/conversations")
        assert convos_response.status_code == 200
        convos = convos_response.json()
        
        if not convos:
            pytest.skip("No DM conversations to test")
        
        conv_id = convos[0].get("id")
        response = admin_auth.get(f"{BASE_URL}/api/dm/{conv_id}/messages")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        messages = response.json()
        assert isinstance(messages, list)
        
        # Check if any E2E messages exist
        e2e_msgs = [m for m in messages if m.get("e2e")]
        print(f"✓ Retrieved {len(messages)} messages, {len(e2e_msgs)} are E2E encrypted")
    
    def test_send_e2e_channel_message(self, admin_auth):
        """POST /api/channels/{id}/messages - Send E2E encrypted channel message"""
        # Get admin's servers
        servers_response = admin_auth.get(f"{BASE_URL}/api/servers")
        if servers_response.status_code != 200 or not servers_response.json():
            pytest.skip("No servers available for channel message test")
        
        server = servers_response.json()[0]
        server_id = server.get("id")
        
        # Get channels
        channels_response = admin_auth.get(f"{BASE_URL}/api/servers/{server_id}/channels")
        if channels_response.status_code != 200 or not channels_response.json():
            pytest.skip("No channels available")
        
        channels = channels_response.json()
        text_channel = next((c for c in channels if c.get("channel_type") == "text"), None)
        if not text_channel:
            pytest.skip("No text channel found")
        
        channel_id = text_channel.get("id")
        
        # Send E2E encrypted channel message
        response = admin_auth.post(f"{BASE_URL}/api/channels/{channel_id}/messages", json={
            "content": "",
            "e2e": True,
            "encrypted_content": "base64_encrypted_channel_message",
            "iv": "base64_iv_for_channel",
            "encrypted_keys": {
                "device-a": "wrapped_key_a",
                "device-b": "wrapped_key_b"
            }
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("e2e") == True, "Channel message should have e2e flag"
        print(f"✓ E2E channel message sent: {data.get('id')[:8]}...")


class TestE2EThreadAndEdit:
    """E2E Thread Replies and Message Edits"""
    
    def test_e2e_thread_reply(self, admin_auth):
        """POST /api/channel-messages/{id}/thread - E2E encrypted thread reply"""
        # Get a channel message to reply to
        servers_response = admin_auth.get(f"{BASE_URL}/api/servers")
        if servers_response.status_code != 200 or not servers_response.json():
            pytest.skip("No servers available")
        
        server = servers_response.json()[0]
        channels_response = admin_auth.get(f"{BASE_URL}/api/servers/{server.get('id')}/channels")
        if channels_response.status_code != 200 or not channels_response.json():
            pytest.skip("No channels available")
        
        channels = channels_response.json()
        text_channel = next((c for c in channels if c.get("channel_type") == "text"), None)
        if not text_channel:
            pytest.skip("No text channel found")
        
        # Get messages
        msgs_response = admin_auth.get(f"{BASE_URL}/api/channels/{text_channel.get('id')}/messages")
        if msgs_response.status_code != 200 or not msgs_response.json():
            # Send a message first
            admin_auth.post(f"{BASE_URL}/api/channels/{text_channel.get('id')}/messages", json={
                "content": "Test message for thread"
            })
            msgs_response = admin_auth.get(f"{BASE_URL}/api/channels/{text_channel.get('id')}/messages")
        
        messages = msgs_response.json()
        if not messages:
            pytest.skip("No messages to reply to")
        
        parent_msg_id = messages[-1].get("id")
        
        # Send E2E thread reply
        response = admin_auth.post(f"{BASE_URL}/api/channel-messages/{parent_msg_id}/thread", json={
            "content": "",
            "e2e": True,
            "encrypted_content": "base64_encrypted_thread_reply",
            "iv": "base64_iv_thread",
            "encrypted_keys": {"device-x": "wrapped_key_x"}
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("e2e") == True, "Thread reply should have e2e flag"
        print(f"✓ E2E thread reply sent: {data.get('id')[:8]}...")
    
    def test_e2e_message_edit(self, admin_auth):
        """PUT /api/channel-messages/{id} - Edit E2E encrypted message"""
        # Get a channel and send a message to edit
        servers_response = admin_auth.get(f"{BASE_URL}/api/servers")
        if servers_response.status_code != 200 or not servers_response.json():
            pytest.skip("No servers available")
        
        server = servers_response.json()[0]
        channels_response = admin_auth.get(f"{BASE_URL}/api/servers/{server.get('id')}/channels")
        if channels_response.status_code != 200 or not channels_response.json():
            pytest.skip("No channels available")
        
        channels = channels_response.json()
        text_channel = next((c for c in channels if c.get("channel_type") == "text"), None)
        if not text_channel:
            pytest.skip("No text channel found")
        
        # Send a message to edit
        send_response = admin_auth.post(f"{BASE_URL}/api/channels/{text_channel.get('id')}/messages", json={
            "content": "Original message to edit"
        })
        if send_response.status_code != 200:
            pytest.skip("Could not send message to edit")
        
        msg_id = send_response.json().get("id")
        
        # Edit with E2E encryption
        response = admin_auth.put(f"{BASE_URL}/api/channel-messages/{msg_id}", json={
            "content": "",
            "e2e": True,
            "encrypted_content": "base64_edited_encrypted_content",
            "iv": "base64_new_iv",
            "encrypted_keys": {"device-y": "new_wrapped_key"}
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("e2e") == True, "Edited message should have e2e flag"
        assert data.get("edited") == True, "Message should be marked as edited"
        print(f"✓ E2E message edited: {msg_id[:8]}...")


class TestE2EKeyManagementUnauth:
    """Test E2E endpoints require authentication"""
    
    def test_keys_register_requires_auth(self, api_client):
        """POST /api/keys/register requires authentication"""
        # Logout first
        api_client.post(f"{BASE_URL}/api/auth/logout")
        
        response = api_client.post(f"{BASE_URL}/api/keys/register", json={
            "device_id": "test",
            "public_key_jwk": {}
        })
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ /api/keys/register correctly requires auth")
    
    def test_keys_devices_requires_auth(self, api_client):
        """GET /api/keys/devices requires authentication"""
        api_client.post(f"{BASE_URL}/api/auth/logout")
        
        response = api_client.get(f"{BASE_URL}/api/keys/devices")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ /api/keys/devices correctly requires auth")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
