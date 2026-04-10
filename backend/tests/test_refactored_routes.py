"""
Test suite for Shield API - Verifying refactored modular routes
Tests all 11 route modules: auth, users, friends, keys, dm, servers, channels, roles, files, emojis, admin
"""
import pytest
import requests
import os
import uuid
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@shield.local"
ADMIN_PASSWORD = "SecureAdmin2024!"

class TestAuthRoutes:
    """Auth routes: register, login, logout, refresh, me"""
    
    def test_login_success(self):
        """POST /api/auth/login - Admin login"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "user" in data
        assert "access_token" in data
        assert data["user"]["email"] == ADMIN_EMAIL
        assert data["user"]["role"] == "admin"
        print(f"✓ Login success: {data['user']['username']}")
    
    def test_login_invalid_credentials(self):
        """POST /api/auth/login - Invalid credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "wrong@example.com",
            "password": "wrongpassword"
        })
        assert response.status_code == 401
        print("✓ Invalid credentials rejected")
    
    def test_register_new_user(self):
        """POST /api/auth/register - New user registration"""
        unique_id = str(uuid.uuid4())[:8]
        response = requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": f"TEST_user_{unique_id}@test.com",
            "username": f"TEST_user_{unique_id}",
            "password": "TestPass123!"
        })
        assert response.status_code == 200, f"Registration failed: {response.text}"
        data = response.json()
        assert "user" in data
        assert "access_token" in data
        print(f"✓ Registration success: {data['user']['username']}")
        return data
    
    def test_get_me(self):
        """GET /api/auth/me - Get current user"""
        # Login first
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        token = login_resp.json()["access_token"]
        
        response = requests.get(f"{BASE_URL}/api/auth/me", headers={
            "Authorization": f"Bearer {token}"
        })
        assert response.status_code == 200
        data = response.json()
        assert "user" in data
        assert data["user"]["email"] == ADMIN_EMAIL
        print("✓ Get me success")
    
    def test_logout(self):
        """POST /api/auth/logout"""
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        token = login_resp.json()["access_token"]
        
        response = requests.post(f"{BASE_URL}/api/auth/logout", headers={
            "Authorization": f"Bearer {token}"
        })
        assert response.status_code == 200
        print("✓ Logout success")


class TestUserRoutes:
    """User routes: profile, status, search"""
    
    @pytest.fixture
    def auth_token(self):
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        return login_resp.json()["access_token"]
    
    def test_get_user_profile(self, auth_token):
        """GET /api/users/me"""
        response = requests.get(f"{BASE_URL}/api/users/me", headers={
            "Authorization": f"Bearer {auth_token}"
        })
        assert response.status_code == 200
        data = response.json()
        assert "username" in data
        assert "email" in data
        print("✓ Get user profile success")
    
    def test_update_profile(self, auth_token):
        """PUT /api/users/me"""
        response = requests.put(f"{BASE_URL}/api/users/me", 
            headers={"Authorization": f"Bearer {auth_token}"},
            json={"display_name": "Admin User", "about": "Testing profile update"}
        )
        assert response.status_code == 200
        print("✓ Update profile success")
    
    def test_update_status(self, auth_token):
        """PUT /api/users/me/status"""
        response = requests.put(f"{BASE_URL}/api/users/me/status",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={"status": "online", "status_message": "Testing"}
        )
        assert response.status_code == 200
        print("✓ Update status success")
    
    def test_search_users(self, auth_token):
        """GET /api/users/search?q="""
        response = requests.get(f"{BASE_URL}/api/users/search?q=admin",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Search users success: found {len(data)} users")


class TestFriendsRoutes:
    """Friend routes: request, accept, list"""
    
    @pytest.fixture
    def auth_token(self):
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        return login_resp.json()["access_token"]
    
    def test_get_friends_list(self, auth_token):
        """GET /api/friends"""
        response = requests.get(f"{BASE_URL}/api/friends",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "friends" in data
        assert "pending_incoming" in data
        assert "pending_outgoing" in data
        print(f"✓ Get friends list success: {len(data['friends'])} friends")
    
    def test_send_friend_request_nonexistent(self, auth_token):
        """POST /api/friends/request - to nonexistent user"""
        response = requests.post(f"{BASE_URL}/api/friends/request",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={"username": "nonexistent_user_12345"}
        )
        assert response.status_code == 404
        print("✓ Friend request to nonexistent user rejected")


class TestKeysRoutes:
    """E2E key routes: register, devices, backup"""
    
    @pytest.fixture
    def auth_token(self):
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        return login_resp.json()["access_token"]
    
    def test_register_device_key(self, auth_token):
        """POST /api/keys/register"""
        device_id = f"test-device-{uuid.uuid4().hex[:8]}"
        response = requests.post(f"{BASE_URL}/api/keys/register",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "device_id": device_id,
                "public_key_jwk": {"kty": "EC", "crv": "P-256", "x": "test", "y": "test"}
            }
        )
        assert response.status_code == 200
        print("✓ Register device key success")
    
    def test_get_devices(self, auth_token):
        """GET /api/keys/devices"""
        response = requests.get(f"{BASE_URL}/api/keys/devices",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Get devices success: {len(data)} devices")


class TestDMRoutes:
    """DM routes: create, messages, conversations"""
    
    @pytest.fixture
    def auth_token(self):
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        return login_resp.json()["access_token"]
    
    @pytest.fixture
    def admin_user_id(self, auth_token):
        response = requests.get(f"{BASE_URL}/api/users/me",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        return response.json()["id"]
    
    def test_get_conversations(self, auth_token):
        """GET /api/dm/conversations"""
        response = requests.get(f"{BASE_URL}/api/dm/conversations",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Get conversations success: {len(data)} conversations")


class TestServerRoutes:
    """Server routes: CRUD, invites, join"""
    
    @pytest.fixture
    def auth_token(self):
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        return login_resp.json()["access_token"]
    
    def test_create_server(self, auth_token):
        """POST /api/servers"""
        server_name = f"TEST_Server_{uuid.uuid4().hex[:8]}"
        response = requests.post(f"{BASE_URL}/api/servers",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={"name": server_name, "description": "Test server"}
        )
        assert response.status_code == 200, f"Create server failed: {response.text}"
        data = response.json()
        assert data["name"] == server_name
        assert "channels" in data
        assert "members" in data
        print(f"✓ Create server success: {server_name}")
        return data
    
    def test_get_servers(self, auth_token):
        """GET /api/servers"""
        response = requests.get(f"{BASE_URL}/api/servers",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Get servers success: {len(data)} servers")
    
    def test_get_server_details(self, auth_token):
        """GET /api/servers/{id}"""
        # First create a server
        server_name = f"TEST_Detail_{uuid.uuid4().hex[:8]}"
        create_resp = requests.post(f"{BASE_URL}/api/servers",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={"name": server_name}
        )
        server_id = create_resp.json()["id"]
        
        # Get details
        response = requests.get(f"{BASE_URL}/api/servers/{server_id}",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == server_id
        assert "channels" in data
        assert "members" in data
        assert "my_permissions" in data
        print("✓ Get server details success")
    
    def test_update_server(self, auth_token):
        """PUT /api/servers/{id}"""
        # Create server
        create_resp = requests.post(f"{BASE_URL}/api/servers",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={"name": f"TEST_Update_{uuid.uuid4().hex[:8]}"}
        )
        server_id = create_resp.json()["id"]
        
        # Update
        response = requests.put(f"{BASE_URL}/api/servers/{server_id}",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={"name": "Updated Server Name", "description": "Updated description"}
        )
        assert response.status_code == 200
        print("✓ Update server success")
    
    def test_create_invite(self, auth_token):
        """POST /api/servers/{id}/invites"""
        # Create server
        create_resp = requests.post(f"{BASE_URL}/api/servers",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={"name": f"TEST_Invite_{uuid.uuid4().hex[:8]}"}
        )
        server_id = create_resp.json()["id"]
        
        # Create invite
        response = requests.post(f"{BASE_URL}/api/servers/{server_id}/invites",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={"max_uses": 10, "expires_hours": 24}
        )
        assert response.status_code == 200
        data = response.json()
        assert "code" in data
        print(f"✓ Create invite success: {data['code']}")
        return data


class TestChannelRoutes:
    """Channel routes: CRUD, messages"""
    
    @pytest.fixture
    def auth_token(self):
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        return login_resp.json()["access_token"]
    
    @pytest.fixture
    def test_server(self, auth_token):
        create_resp = requests.post(f"{BASE_URL}/api/servers",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={"name": f"TEST_Channel_{uuid.uuid4().hex[:8]}"}
        )
        return create_resp.json()
    
    def test_create_channel(self, auth_token, test_server):
        """POST /api/servers/{id}/channels"""
        response = requests.post(f"{BASE_URL}/api/servers/{test_server['id']}/channels",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={"name": "test-channel", "channel_type": "text", "category": "Text Channels"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "test-channel"
        print("✓ Create channel success")
        return data
    
    def test_send_channel_message(self, auth_token, test_server):
        """POST /api/channels/{id}/messages"""
        # Get the general channel
        channel_id = test_server["channels"][0]["id"]
        
        response = requests.post(f"{BASE_URL}/api/channels/{channel_id}/messages",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={"content": "Test message from pytest"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data["sender_username"] == "admin"
        print("✓ Send channel message success")
    
    def test_get_channel_messages(self, auth_token, test_server):
        """GET /api/channels/{id}/messages"""
        channel_id = test_server["channels"][0]["id"]
        
        response = requests.get(f"{BASE_URL}/api/channels/{channel_id}/messages",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Get channel messages success: {len(data)} messages")
    
    def test_mark_channel_read(self, auth_token, test_server):
        """POST /api/channels/{id}/read"""
        channel_id = test_server["channels"][0]["id"]
        
        # First send a message to get a message_id
        msg_resp = requests.post(f"{BASE_URL}/api/channels/{channel_id}/messages",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={"content": "Test for read receipt"}
        )
        message_id = msg_resp.json()["id"]
        
        response = requests.post(f"{BASE_URL}/api/channels/{channel_id}/read",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={"last_message_id": message_id}
        )
        assert response.status_code == 200
        print("✓ Mark channel read success")


class TestRoleRoutes:
    """Role routes: CRUD, assign"""
    
    @pytest.fixture
    def auth_token(self):
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        return login_resp.json()["access_token"]
    
    @pytest.fixture
    def test_server(self, auth_token):
        create_resp = requests.post(f"{BASE_URL}/api/servers",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={"name": f"TEST_Role_{uuid.uuid4().hex[:8]}"}
        )
        return create_resp.json()
    
    def test_create_role(self, auth_token, test_server):
        """POST /api/servers/{id}/roles"""
        response = requests.post(f"{BASE_URL}/api/servers/{test_server['id']}/roles",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={"name": "Moderator", "color": "#FF5733", "permissions": 8}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Moderator"
        print("✓ Create role success")
        return data
    
    def test_update_role(self, auth_token, test_server):
        """PUT /api/servers/{id}/roles/{id}"""
        # Create role first
        create_resp = requests.post(f"{BASE_URL}/api/servers/{test_server['id']}/roles",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={"name": "TestRole", "permissions": 4}
        )
        role_id = create_resp.json()["id"]
        
        response = requests.put(f"{BASE_URL}/api/servers/{test_server['id']}/roles/{role_id}",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={"name": "UpdatedRole", "color": "#00FF00"}
        )
        assert response.status_code == 200
        print("✓ Update role success")
    
    def test_get_permissions_map(self, auth_token):
        """GET /api/permissions/map"""
        response = requests.get(f"{BASE_URL}/api/permissions/map",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "permissions" in data
        assert "default" in data
        print("✓ Get permissions map success")


class TestAdminRoutes:
    """Admin routes: stats, TURN, servers"""
    
    @pytest.fixture
    def auth_token(self):
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        return login_resp.json()["access_token"]
    
    def test_get_admin_stats(self, auth_token):
        """GET /api/admin/stats"""
        response = requests.get(f"{BASE_URL}/api/admin/stats",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "users_registered" in data
        assert "users_online" in data
        assert "total_servers" in data
        assert "total_messages" in data
        print(f"✓ Admin stats: {data['users_registered']} users, {data['total_servers']} servers")
    
    def test_get_admin_servers(self, auth_token):
        """GET /api/admin/servers"""
        response = requests.get(f"{BASE_URL}/api/admin/servers",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Admin servers: {len(data)} servers")
    
    def test_get_turn_credentials(self, auth_token):
        """GET /api/turn/credentials"""
        response = requests.get(f"{BASE_URL}/api/turn/credentials",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "ice_servers" in data
        print(f"✓ TURN credentials: {len(data['ice_servers'])} ICE servers")
    
    def test_system_update_check(self, auth_token):
        """GET /api/system/update-check"""
        response = requests.get(f"{BASE_URL}/api/system/update-check",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "current_version" in data
        print(f"✓ System update check: v{data['current_version']}")


class TestGIFRoutes:
    """GIF routes: trending, search"""
    
    @pytest.fixture
    def auth_token(self):
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        return login_resp.json()["access_token"]
    
    def test_gif_trending(self, auth_token):
        """GET /api/gifs/trending"""
        response = requests.get(f"{BASE_URL}/api/gifs/trending",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "gifs" in data
        print(f"✓ GIF trending: {len(data['gifs'])} GIFs")
    
    def test_gif_search(self, auth_token):
        """GET /api/gifs/search?q="""
        response = requests.get(f"{BASE_URL}/api/gifs/search?q=hello",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "gifs" in data
        print(f"✓ GIF search: {len(data['gifs'])} GIFs for 'hello'")


class TestEmojiRoutes:
    """Emoji routes: mine"""
    
    @pytest.fixture
    def auth_token(self):
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        return login_resp.json()["access_token"]
    
    def test_get_my_emojis(self, auth_token):
        """GET /api/emojis/mine"""
        response = requests.get(f"{BASE_URL}/api/emojis/mine",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "owned" in data
        assert "saved" in data
        print(f"✓ Get my emojis: {len(data['owned'])} owned, {len(data['saved'])} saved")


class TestDMCallRoutes:
    """DM call routes"""
    
    @pytest.fixture
    def auth_token(self):
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        return login_resp.json()["access_token"]
    
    def test_dm_call_requires_conversation(self, auth_token):
        """POST /api/dm/{id}/call - with invalid conversation"""
        response = requests.post(f"{BASE_URL}/api/dm/invalid-conv-id/call",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 404
        print("✓ DM call with invalid conversation rejected")


class TestDriveRoutes:
    """Share drive routes"""
    
    @pytest.fixture
    def auth_token(self):
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        return login_resp.json()["access_token"]
    
    @pytest.fixture
    def test_server(self, auth_token):
        create_resp = requests.post(f"{BASE_URL}/api/servers",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={"name": f"TEST_Drive_{uuid.uuid4().hex[:8]}"}
        )
        return create_resp.json()
    
    def test_list_drive_files(self, auth_token, test_server):
        """GET /api/servers/{id}/drive"""
        response = requests.get(f"{BASE_URL}/api/servers/{test_server['id']}/drive",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ List drive files: {len(data)} files")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
