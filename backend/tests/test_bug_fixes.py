"""
Test suite for Shield Bug Fixes - Iteration 9
Tests the 18+ bug fixes including:
- DM creation and conversation listing
- Status message saving
- Server invites GET
- Channel CRUD (update/delete)
- Group DM creation
- E2E key management
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestAuth:
    """Authentication tests"""
    
    @pytest.fixture(scope="class")
    def session(self):
        return requests.Session()
    
    @pytest.fixture(scope="class")
    def admin_auth(self, session):
        """Login as admin and return session with cookies"""
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@shield.local",
            "password": "SecureAdmin2024!"
        })
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        return session
    
    def test_admin_login(self, session):
        """Test admin login works"""
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@shield.local",
            "password": "SecureAdmin2024!"
        })
        assert response.status_code == 200
        data = response.json()
        assert "user" in data or "access_token" in data


class TestStatusUpdate:
    """Test status message saving - Bug #4"""
    
    @pytest.fixture(scope="class")
    def session(self):
        return requests.Session()
    
    @pytest.fixture(scope="class")
    def auth_session(self, session):
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@shield.local",
            "password": "SecureAdmin2024!"
        })
        assert response.status_code == 200
        return session
    
    def test_update_status_with_message(self, auth_session):
        """Test PUT /api/users/me/status saves status_message correctly"""
        test_message = f"TEST_status_{uuid.uuid4().hex[:8]}"
        response = auth_session.put(f"{BASE_URL}/api/users/me/status", json={
            "status": "busy",
            "status_message": test_message,
            "status_expires_minutes": 60
        })
        assert response.status_code == 200, f"Status update failed: {response.text}"
        
        # Verify status was saved by fetching user profile
        profile_response = auth_session.get(f"{BASE_URL}/api/users/me")
        assert profile_response.status_code == 200
        profile = profile_response.json()
        assert profile.get("status") == "busy", "Status not updated"
        assert profile.get("status_message") == test_message, "Status message not saved"
    
    def test_update_status_without_message(self, auth_session):
        """Test status update without message"""
        response = auth_session.put(f"{BASE_URL}/api/users/me/status", json={
            "status": "online"
        })
        assert response.status_code == 200


class TestDMConversations:
    """Test DM creation and listing - Bug #1, #8"""
    
    @pytest.fixture(scope="class")
    def session(self):
        return requests.Session()
    
    @pytest.fixture(scope="class")
    def auth_session(self, session):
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@shield.local",
            "password": "SecureAdmin2024!"
        })
        assert response.status_code == 200
        return session
    
    @pytest.fixture(scope="class")
    def test_user(self, session):
        """Create a test user for DM testing"""
        unique_id = uuid.uuid4().hex[:8]
        response = session.post(f"{BASE_URL}/api/auth/register", json={
            "username": f"TEST_dm_user_{unique_id}",
            "email": f"test_dm_{unique_id}@test.local",
            "password": "TestPass123!"
        })
        if response.status_code == 200:
            return response.json().get("user", {})
        # If registration fails, try to find existing user
        return {"id": None}
    
    def test_create_dm_conversation(self, auth_session, test_user):
        """Test POST /api/dm/create creates conversation"""
        if not test_user.get("id"):
            pytest.skip("Test user not available")
        
        response = auth_session.post(f"{BASE_URL}/api/dm/create", json={
            "recipient_id": test_user["id"],
            "content": ""
        })
        assert response.status_code == 200, f"DM create failed: {response.text}"
        data = response.json()
        assert "id" in data, "Conversation ID not returned"
        assert data.get("type") == "dm", "Conversation type should be 'dm'"
        return data["id"]
    
    def test_dm_appears_in_conversations_list(self, auth_session, test_user):
        """Test GET /api/dm/conversations returns created DM without reload"""
        if not test_user.get("id"):
            pytest.skip("Test user not available")
        
        # First create a DM
        create_response = auth_session.post(f"{BASE_URL}/api/dm/create", json={
            "recipient_id": test_user["id"],
            "content": ""
        })
        assert create_response.status_code == 200
        conv_id = create_response.json().get("id")
        
        # Then verify it appears in the list
        list_response = auth_session.get(f"{BASE_URL}/api/dm/conversations")
        assert list_response.status_code == 200
        conversations = list_response.json()
        assert isinstance(conversations, list)
        
        # Check if our conversation is in the list
        conv_ids = [c.get("id") for c in conversations]
        assert conv_id in conv_ids, "Created DM not found in conversations list"


class TestGroupDM:
    """Test Group DM creation - Bug #13"""
    
    @pytest.fixture(scope="class")
    def session(self):
        return requests.Session()
    
    @pytest.fixture(scope="class")
    def auth_session(self, session):
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@shield.local",
            "password": "SecureAdmin2024!"
        })
        assert response.status_code == 200
        return session
    
    @pytest.fixture(scope="class")
    def test_users(self):
        """Create test users for group DM"""
        users = []
        for i in range(2):
            unique_id = uuid.uuid4().hex[:8]
            session = requests.Session()
            response = session.post(f"{BASE_URL}/api/auth/register", json={
                "username": f"TEST_group_user_{i}_{unique_id}",
                "email": f"test_group_{i}_{unique_id}@test.local",
                "password": "TestPass123!"
            })
            if response.status_code == 200:
                users.append(response.json().get("user", {}))
        return users
    
    def test_create_group_dm(self, auth_session, test_users):
        """Test POST /api/dm/group creates a group DM"""
        member_ids = [u.get("id") for u in test_users if u.get("id")]
        if len(member_ids) < 1:
            pytest.skip("Not enough test users available")
        
        response = auth_session.post(f"{BASE_URL}/api/dm/group", json={
            "name": f"TEST_Group_{uuid.uuid4().hex[:6]}",
            "member_ids": member_ids
        })
        assert response.status_code == 200, f"Group DM create failed: {response.text}"
        data = response.json()
        assert data.get("type") == "group_dm", "Type should be 'group_dm'"
        assert "id" in data, "Group DM ID not returned"
        assert "participants" in data, "Participants not returned"


class TestServerInvites:
    """Test server invites GET - Bug #11"""
    
    @pytest.fixture(scope="class")
    def session(self):
        return requests.Session()
    
    @pytest.fixture(scope="class")
    def auth_session(self, session):
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@shield.local",
            "password": "SecureAdmin2024!"
        })
        assert response.status_code == 200
        return session
    
    @pytest.fixture(scope="class")
    def test_server(self, auth_session):
        """Create a test server"""
        response = auth_session.post(f"{BASE_URL}/api/servers", json={
            "name": f"TEST_Server_{uuid.uuid4().hex[:6]}"
        })
        if response.status_code == 200:
            return response.json()
        return None
    
    def test_get_server_invites(self, auth_session, test_server):
        """Test GET /api/servers/{id}/invites returns invite codes"""
        if not test_server:
            pytest.skip("Test server not available")
        
        response = auth_session.get(f"{BASE_URL}/api/servers/{test_server['id']}/invites")
        assert response.status_code == 200, f"Get invites failed: {response.text}"
        invites = response.json()
        assert isinstance(invites, list), "Invites should be a list"
        # Server creation auto-creates an invite
        assert len(invites) >= 1, "Should have at least one invite"
        assert "code" in invites[0], "Invite should have a code"


class TestChannelCRUD:
    """Test channel update and delete - Bug #12"""
    
    @pytest.fixture(scope="class")
    def session(self):
        return requests.Session()
    
    @pytest.fixture(scope="class")
    def auth_session(self, session):
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@shield.local",
            "password": "SecureAdmin2024!"
        })
        assert response.status_code == 200
        return session
    
    @pytest.fixture(scope="class")
    def test_server_with_channel(self, auth_session):
        """Create a test server with a channel"""
        # Create server
        server_response = auth_session.post(f"{BASE_URL}/api/servers", json={
            "name": f"TEST_ChannelCRUD_{uuid.uuid4().hex[:6]}"
        })
        if server_response.status_code != 200:
            return None, None
        server = server_response.json()
        
        # Create a test channel
        channel_response = auth_session.post(f"{BASE_URL}/api/servers/{server['id']}/channels", json={
            "name": f"test-channel-{uuid.uuid4().hex[:6]}",
            "channel_type": "text",
            "category": "Test"
        })
        if channel_response.status_code != 200:
            return server, None
        channel = channel_response.json()
        return server, channel
    
    def test_update_channel(self, auth_session, test_server_with_channel):
        """Test PUT /api/servers/{id}/channels/{id} updates channel"""
        server, channel = test_server_with_channel
        if not server or not channel:
            pytest.skip("Test server/channel not available")
        
        new_name = f"updated-{uuid.uuid4().hex[:6]}"
        response = auth_session.put(
            f"{BASE_URL}/api/servers/{server['id']}/channels/{channel['id']}",
            json={
                "name": new_name,
                "topic": "Updated topic",
                "slowmode_seconds": 5
            }
        )
        assert response.status_code == 200, f"Channel update failed: {response.text}"
    
    def test_delete_channel(self, auth_session, test_server_with_channel):
        """Test DELETE /api/servers/{id}/channels/{id} deletes channel"""
        server, _ = test_server_with_channel
        if not server:
            pytest.skip("Test server not available")
        
        # Create a channel to delete
        create_response = auth_session.post(f"{BASE_URL}/api/servers/{server['id']}/channels", json={
            "name": f"to-delete-{uuid.uuid4().hex[:6]}",
            "channel_type": "text"
        })
        if create_response.status_code != 200:
            pytest.skip("Could not create channel to delete")
        
        channel_to_delete = create_response.json()
        
        # Delete it
        delete_response = auth_session.delete(
            f"{BASE_URL}/api/servers/{server['id']}/channels/{channel_to_delete['id']}"
        )
        assert delete_response.status_code == 200, f"Channel delete failed: {delete_response.text}"


class TestE2EKeyManagement:
    """Test E2E encryption key management endpoints"""
    
    @pytest.fixture(scope="class")
    def session(self):
        return requests.Session()
    
    @pytest.fixture(scope="class")
    def auth_session(self, session):
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@shield.local",
            "password": "SecureAdmin2024!"
        })
        assert response.status_code == 200
        return session
    
    def test_register_device_key(self, auth_session):
        """Test POST /api/keys/register"""
        device_id = f"TEST_device_{uuid.uuid4().hex[:8]}"
        response = auth_session.post(f"{BASE_URL}/api/keys/register", json={
            "device_id": device_id,
            "public_key_jwk": {"kty": "RSA", "n": "test", "e": "AQAB"}
        })
        assert response.status_code == 200, f"Key register failed: {response.text}"
    
    def test_get_devices(self, auth_session):
        """Test GET /api/keys/devices"""
        response = auth_session.get(f"{BASE_URL}/api/keys/devices")
        assert response.status_code == 200
        devices = response.json()
        assert isinstance(devices, list)
    
    def test_get_key_bundle(self, auth_session):
        """Test POST /api/keys/bundle"""
        # Get current user ID
        me_response = auth_session.get(f"{BASE_URL}/api/users/me")
        user_id = me_response.json().get("id")
        
        response = auth_session.post(f"{BASE_URL}/api/keys/bundle", json={
            "user_ids": [user_id]
        })
        assert response.status_code == 200
        bundle = response.json()
        assert isinstance(bundle, dict)


class TestFriendsEndpoints:
    """Test friends-related endpoints"""
    
    @pytest.fixture(scope="class")
    def session(self):
        return requests.Session()
    
    @pytest.fixture(scope="class")
    def auth_session(self, session):
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@shield.local",
            "password": "SecureAdmin2024!"
        })
        assert response.status_code == 200
        return session
    
    def test_get_friends(self, auth_session):
        """Test GET /api/friends returns friends list"""
        response = auth_session.get(f"{BASE_URL}/api/friends")
        assert response.status_code == 200
        data = response.json()
        assert "friends" in data
        assert "pending_incoming" in data
        assert "pending_outgoing" in data
        assert "blocked" in data


class TestServerEndpoints:
    """Test server-related endpoints"""
    
    @pytest.fixture(scope="class")
    def session(self):
        return requests.Session()
    
    @pytest.fixture(scope="class")
    def auth_session(self, session):
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@shield.local",
            "password": "SecureAdmin2024!"
        })
        assert response.status_code == 200
        return session
    
    def test_get_servers(self, auth_session):
        """Test GET /api/servers returns user's servers"""
        response = auth_session.get(f"{BASE_URL}/api/servers")
        assert response.status_code == 200
        servers = response.json()
        assert isinstance(servers, list)
    
    def test_get_server_details(self, auth_session):
        """Test GET /api/servers/{id} returns server with channels and members"""
        # First get list of servers
        list_response = auth_session.get(f"{BASE_URL}/api/servers")
        servers = list_response.json()
        
        if not servers:
            pytest.skip("No servers available")
        
        server_id = servers[0]["id"]
        response = auth_session.get(f"{BASE_URL}/api/servers/{server_id}")
        assert response.status_code == 200
        server = response.json()
        assert "channels" in server
        assert "members" in server


class TestAdminEndpoints:
    """Test admin-only endpoints"""
    
    @pytest.fixture(scope="class")
    def session(self):
        return requests.Session()
    
    @pytest.fixture(scope="class")
    def admin_session(self, session):
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@shield.local",
            "password": "SecureAdmin2024!"
        })
        assert response.status_code == 200
        return session
    
    def test_admin_stats(self, admin_session):
        """Test GET /api/admin/stats"""
        response = admin_session.get(f"{BASE_URL}/api/admin/stats")
        assert response.status_code == 200
        stats = response.json()
        assert "users_registered" in stats
        assert "total_servers" in stats
    
    def test_admin_turn_config(self, admin_session):
        """Test GET /api/admin/turn/config"""
        response = admin_session.get(f"{BASE_URL}/api/admin/turn/config")
        assert response.status_code == 200
        config = response.json()
        assert "enabled" in config or "key" in config


class TestMessageEndpoints:
    """Test message-related endpoints"""
    
    @pytest.fixture(scope="class")
    def session(self):
        return requests.Session()
    
    @pytest.fixture(scope="class")
    def auth_session(self, session):
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@shield.local",
            "password": "SecureAdmin2024!"
        })
        assert response.status_code == 200
        return session
    
    def test_send_channel_message(self, auth_session):
        """Test sending a message to a channel"""
        # Get servers
        servers_response = auth_session.get(f"{BASE_URL}/api/servers")
        servers = servers_response.json()
        
        if not servers:
            pytest.skip("No servers available")
        
        # Get server details to find a text channel
        server_response = auth_session.get(f"{BASE_URL}/api/servers/{servers[0]['id']}")
        server = server_response.json()
        
        text_channels = [c for c in server.get("channels", []) if c.get("channel_type") == "text"]
        if not text_channels:
            pytest.skip("No text channels available")
        
        channel_id = text_channels[0]["id"]
        
        # Send message
        response = auth_session.post(f"{BASE_URL}/api/channels/{channel_id}/messages", json={
            "content": f"TEST_message_{uuid.uuid4().hex[:8]}"
        })
        assert response.status_code == 200, f"Send message failed: {response.text}"
        message = response.json()
        assert "id" in message
        assert "content" in message


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
