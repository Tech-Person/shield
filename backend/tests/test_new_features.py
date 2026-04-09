"""
Backend API tests for SecureComm new features:
1. Custom emoji/sticker upload and management
2. Share Drive text file creation
3. Storage requests
4. Status update
5. Admin storage request management
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestAuth:
    """Authentication tests for admin login"""
    
    @pytest.fixture(scope="class")
    def admin_session(self):
        """Login as admin and return session with cookies"""
        session = requests.Session()
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@securecomm.local",
            "password": "SecureAdmin2024!"
        })
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        data = response.json()
        assert "access_token" in data
        assert "user" in data
        assert data["user"]["role"] == "admin"
        return session
    
    def test_admin_login(self, admin_session):
        """Verify admin login works"""
        response = admin_session.get(f"{BASE_URL}/api/auth/me")
        assert response.status_code == 200
        data = response.json()
        # Response is {"user": {...}} format
        user = data.get("user", data)
        assert user.get("role") == "admin" or user.get("username") == "admin"
        print("✓ Admin login successful")


class TestStatusUpdate:
    """Test user status update functionality"""
    
    @pytest.fixture(scope="class")
    def admin_session(self):
        session = requests.Session()
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@securecomm.local",
            "password": "SecureAdmin2024!"
        })
        assert response.status_code == 200
        return session
    
    def test_update_status_online(self, admin_session):
        """Test setting status to online"""
        response = admin_session.put(f"{BASE_URL}/api/users/me/status", json={"status": "online"})
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "online" or "message" in data
        print("✓ Status update to 'online' successful")
    
    def test_update_status_away(self, admin_session):
        """Test setting status to away"""
        response = admin_session.put(f"{BASE_URL}/api/users/me/status", json={"status": "away"})
        assert response.status_code == 200
        print("✓ Status update to 'away' successful")
    
    def test_update_status_busy(self, admin_session):
        """Test setting status to busy"""
        response = admin_session.put(f"{BASE_URL}/api/users/me/status", json={"status": "busy"})
        assert response.status_code == 200
        print("✓ Status update to 'busy' successful")
    
    def test_update_status_invisible(self, admin_session):
        """Test setting status to invisible"""
        response = admin_session.put(f"{BASE_URL}/api/users/me/status", json={"status": "invisible"})
        assert response.status_code == 200
        print("✓ Status update to 'invisible' successful")


class TestCustomEmojis:
    """Test custom emoji/sticker endpoints"""
    
    @pytest.fixture(scope="class")
    def admin_session(self):
        session = requests.Session()
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@securecomm.local",
            "password": "SecureAdmin2024!"
        })
        assert response.status_code == 200
        return session
    
    def test_get_my_emojis(self, admin_session):
        """Test GET /api/emojis/mine returns owned and saved arrays"""
        response = admin_session.get(f"{BASE_URL}/api/emojis/mine")
        assert response.status_code == 200
        data = response.json()
        assert "owned" in data, "Response should have 'owned' array"
        assert "saved" in data, "Response should have 'saved' array"
        assert isinstance(data["owned"], list)
        assert isinstance(data["saved"], list)
        print(f"✓ GET /api/emojis/mine returns owned ({len(data['owned'])}) and saved ({len(data['saved'])}) arrays")


class TestServerAndDrive:
    """Test server creation and Share Drive functionality"""
    
    @pytest.fixture(scope="class")
    def admin_session(self):
        session = requests.Session()
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@securecomm.local",
            "password": "SecureAdmin2024!"
        })
        assert response.status_code == 200
        return session
    
    @pytest.fixture(scope="class")
    def test_server(self, admin_session):
        """Create a test server for drive tests"""
        response = admin_session.post(f"{BASE_URL}/api/servers", json={
            "name": "TEST_DriveServer"
        })
        assert response.status_code in [200, 201], f"Server creation failed: {response.text}"
        server = response.json()
        assert "id" in server
        print(f"✓ Created test server: {server['name']}")
        yield server
        # Cleanup - delete server
        try:
            admin_session.delete(f"{BASE_URL}/api/servers/{server['id']}")
        except:
            pass
    
    def test_create_text_file(self, admin_session, test_server):
        """Test POST /api/servers/{id}/drive/text creates a text file"""
        server_id = test_server["id"]
        response = admin_session.post(f"{BASE_URL}/api/servers/{server_id}/drive/text", json={
            "filename": "test_notes.txt",
            "content": "This is a test text file content."
        })
        assert response.status_code in [200, 201], f"Text file creation failed: {response.text}"
        data = response.json()
        assert "id" in data
        assert data.get("original_filename") == "test_notes.txt" or data.get("filename") == "test_notes.txt"
        assert data.get("is_text_file") == True
        print(f"✓ POST /api/servers/{server_id}/drive/text creates text file successfully")
        return data
    
    def test_list_drive_files(self, admin_session, test_server):
        """Test GET /api/servers/{id}/drive lists files"""
        server_id = test_server["id"]
        response = admin_session.get(f"{BASE_URL}/api/servers/{server_id}/drive")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ GET /api/servers/{server_id}/drive returns {len(data)} files")
    
    def test_get_text_file_content(self, admin_session, test_server):
        """Test getting text file content"""
        server_id = test_server["id"]
        # First create a file
        create_resp = admin_session.post(f"{BASE_URL}/api/servers/{server_id}/drive/text", json={
            "filename": "content_test.txt",
            "content": "Test content for retrieval"
        })
        assert create_resp.status_code in [200, 201]
        file_data = create_resp.json()
        file_id = file_data["id"]
        
        # Get content
        response = admin_session.get(f"{BASE_URL}/api/servers/{server_id}/drive/{file_id}/content")
        assert response.status_code == 200
        data = response.json()
        assert "content" in data
        assert data["content"] == "Test content for retrieval"
        print(f"✓ GET /api/servers/{server_id}/drive/{file_id}/content returns correct content")


class TestStorageRequests:
    """Test storage request functionality"""
    
    @pytest.fixture(scope="class")
    def admin_session(self):
        session = requests.Session()
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@securecomm.local",
            "password": "SecureAdmin2024!"
        })
        assert response.status_code == 200
        return session
    
    @pytest.fixture(scope="class")
    def test_server(self, admin_session):
        """Create a test server for storage request tests"""
        response = admin_session.post(f"{BASE_URL}/api/servers", json={
            "name": "TEST_StorageServer"
        })
        assert response.status_code in [200, 201]
        server = response.json()
        yield server
        # Cleanup
        try:
            admin_session.delete(f"{BASE_URL}/api/servers/{server['id']}")
        except:
            pass
    
    def test_submit_storage_request(self, admin_session, test_server):
        """Test POST /api/servers/{id}/storage-request"""
        server_id = test_server["id"]
        response = admin_session.post(f"{BASE_URL}/api/servers/{server_id}/storage-request", json={
            "requested_gb": 100,
            "reason": "Need more space for team files"
        })
        assert response.status_code in [200, 201], f"Storage request failed: {response.text}"
        data = response.json()
        assert "id" in data
        assert data.get("requested_gb") == 100
        assert data.get("status") == "pending"
        print(f"✓ POST /api/servers/{server_id}/storage-request returns valid response")
        return data
    
    def test_get_storage_requests(self, admin_session, test_server):
        """Test GET /api/servers/{id}/storage-request"""
        server_id = test_server["id"]
        response = admin_session.get(f"{BASE_URL}/api/servers/{server_id}/storage-request")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ GET /api/servers/{server_id}/storage-request returns {len(data)} requests")


class TestAdminDashboard:
    """Test admin dashboard endpoints"""
    
    @pytest.fixture(scope="class")
    def admin_session(self):
        session = requests.Session()
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@securecomm.local",
            "password": "SecureAdmin2024!"
        })
        assert response.status_code == 200
        return session
    
    def test_admin_stats(self, admin_session):
        """Test GET /api/admin/stats"""
        response = admin_session.get(f"{BASE_URL}/api/admin/stats")
        assert response.status_code == 200
        data = response.json()
        assert "users_registered" in data
        assert "total_servers" in data
        assert "total_messages" in data
        print(f"✓ GET /api/admin/stats returns stats (users: {data['users_registered']}, servers: {data['total_servers']})")
    
    def test_admin_storage_requests(self, admin_session):
        """Test GET /api/admin/storage-requests"""
        response = admin_session.get(f"{BASE_URL}/api/admin/storage-requests")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ GET /api/admin/storage-requests returns {len(data)} pending requests")
    
    def test_admin_servers(self, admin_session):
        """Test GET /api/admin/servers"""
        response = admin_session.get(f"{BASE_URL}/api/admin/servers")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ GET /api/admin/servers returns {len(data)} servers")


class TestChannelMessaging:
    """Test channel creation and messaging"""
    
    @pytest.fixture(scope="class")
    def admin_session(self):
        session = requests.Session()
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@securecomm.local",
            "password": "SecureAdmin2024!"
        })
        assert response.status_code == 200
        return session
    
    @pytest.fixture(scope="class")
    def test_server_with_channel(self, admin_session):
        """Create a test server with a text channel"""
        # Create server
        server_resp = admin_session.post(f"{BASE_URL}/api/servers", json={
            "name": "TEST_ChannelServer"
        })
        assert server_resp.status_code in [200, 201]
        server = server_resp.json()
        
        # Create text channel
        channel_resp = admin_session.post(f"{BASE_URL}/api/servers/{server['id']}/channels", json={
            "name": "test-channel",
            "channel_type": "text"
        })
        assert channel_resp.status_code in [200, 201]
        channel = channel_resp.json()
        
        yield {"server": server, "channel": channel}
        
        # Cleanup
        try:
            admin_session.delete(f"{BASE_URL}/api/servers/{server['id']}")
        except:
            pass
    
    def test_send_message_in_channel(self, admin_session, test_server_with_channel):
        """Test sending a message in a channel"""
        channel_id = test_server_with_channel["channel"]["id"]
        response = admin_session.post(f"{BASE_URL}/api/channels/{channel_id}/messages", json={
            "content": "Test message in channel"
        })
        assert response.status_code in [200, 201], f"Message send failed: {response.text}"
        data = response.json()
        assert "id" in data
        assert data.get("content") == "Test message in channel"
        print(f"✓ Message sent successfully in channel {channel_id}")
    
    def test_get_channel_messages(self, admin_session, test_server_with_channel):
        """Test getting messages from a channel"""
        channel_id = test_server_with_channel["channel"]["id"]
        response = admin_session.get(f"{BASE_URL}/api/channels/{channel_id}/messages")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ GET /api/channels/{channel_id}/messages returns {len(data)} messages")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
