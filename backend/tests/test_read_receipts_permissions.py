"""
Test Read Receipts and Extended Permission Enforcement Features
- Read receipts for channels and DMs
- Permission checks: MANAGE_SERVER, CREATE_INVITE, ADD_REACTIONS, SEND_MESSAGES_IN_THREADS
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@shield.local"
ADMIN_PASSWORD = "SecureAdmin2024!"

class TestSession:
    """Helper class to manage authenticated sessions"""
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        self.user = None
        self.token = None
    
    def login(self, email, password):
        resp = self.session.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password})
        if resp.status_code == 200:
            data = resp.json()
            self.user = data.get("user")
            self.token = data.get("access_token")
            if self.token:
                self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        return resp
    
    def register(self, username, email, password):
        resp = self.session.post(f"{BASE_URL}/api/auth/register", json={
            "username": username, "email": email, "password": password
        })
        if resp.status_code == 200:
            data = resp.json()
            self.user = data.get("user")
            self.token = data.get("access_token")
            if self.token:
                self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        return resp


# ─── READ RECEIPTS TESTS ───

class TestChannelReadReceipts:
    """Test read receipts for server channels"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup: login as admin, create server, get channel"""
        self.admin = TestSession()
        resp = self.admin.login(ADMIN_EMAIL, ADMIN_PASSWORD)
        if resp.status_code != 200:
            pytest.skip("Admin login failed")
        
        # Create a test server
        server_resp = self.admin.session.post(f"{BASE_URL}/api/servers", json={
            "name": f"TEST_ReadReceipts_{uuid.uuid4().hex[:6]}"
        })
        if server_resp.status_code != 200:
            pytest.skip("Failed to create test server")
        
        self.server = server_resp.json()
        
        # Get channels
        server_detail = self.admin.session.get(f"{BASE_URL}/api/servers/{self.server['id']}").json()
        self.channel = next((c for c in server_detail.get("channels", []) if c["channel_type"] == "text"), None)
        if not self.channel:
            pytest.skip("No text channel found")
        
        yield
        
        # Cleanup: delete server
        try:
            self.admin.session.delete(f"{BASE_URL}/api/servers/{self.server['id']}")
        except:
            pass
    
    def test_mark_channel_read_returns_200(self):
        """POST /api/channels/{id}/read with last_message_id returns 200"""
        # First send a message to get a message_id
        msg_resp = self.admin.session.post(f"{BASE_URL}/api/channels/{self.channel['id']}/messages", json={
            "content": "Test message for read receipt"
        })
        assert msg_resp.status_code == 200, f"Failed to send message: {msg_resp.text}"
        message = msg_resp.json()
        
        # Mark as read
        read_resp = self.admin.session.post(f"{BASE_URL}/api/channels/{self.channel['id']}/read", json={
            "last_message_id": message["id"]
        })
        assert read_resp.status_code == 200, f"Expected 200, got {read_resp.status_code}: {read_resp.text}"
        data = read_resp.json()
        assert "message" in data
        print(f"✓ POST /api/channels/{{id}}/read returns 200")
    
    def test_mark_channel_read_requires_last_message_id(self):
        """POST /api/channels/{id}/read without last_message_id returns 400"""
        read_resp = self.admin.session.post(f"{BASE_URL}/api/channels/{self.channel['id']}/read", json={})
        assert read_resp.status_code == 400, f"Expected 400, got {read_resp.status_code}"
        print(f"✓ POST /api/channels/{{id}}/read requires last_message_id")
    
    def test_get_channel_read_receipts_returns_array(self):
        """GET /api/channels/{id}/read-receipts returns array of receipts"""
        # First mark as read
        msg_resp = self.admin.session.post(f"{BASE_URL}/api/channels/{self.channel['id']}/messages", json={
            "content": "Test message for receipts list"
        })
        message = msg_resp.json()
        self.admin.session.post(f"{BASE_URL}/api/channels/{self.channel['id']}/read", json={
            "last_message_id": message["id"]
        })
        
        # Get receipts
        receipts_resp = self.admin.session.get(f"{BASE_URL}/api/channels/{self.channel['id']}/read-receipts")
        assert receipts_resp.status_code == 200, f"Expected 200, got {receipts_resp.status_code}"
        data = receipts_resp.json()
        assert isinstance(data, list), "Expected array of receipts"
        print(f"✓ GET /api/channels/{{id}}/read-receipts returns array (count: {len(data)})")


class TestDMReadReceipts:
    """Test read receipts for DM conversations"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup: create two users and a DM conversation"""
        self.user1 = TestSession()
        self.user2 = TestSession()
        
        # Register two test users
        unique = uuid.uuid4().hex[:6]
        resp1 = self.user1.register(f"TEST_User1_{unique}", f"test1_{unique}@test.local", "TestPass123!")
        resp2 = self.user2.register(f"TEST_User2_{unique}", f"test2_{unique}@test.local", "TestPass123!")
        
        if resp1.status_code != 200 or resp2.status_code != 200:
            pytest.skip("Failed to register test users")
        
        # Create DM conversation
        dm_resp = self.user1.session.post(f"{BASE_URL}/api/dm/create", json={
            "recipient_id": self.user2.user["id"]
        })
        if dm_resp.status_code != 200:
            pytest.skip("Failed to create DM conversation")
        
        self.conversation = dm_resp.json()
        yield
    
    def test_mark_dm_read_returns_200(self):
        """POST /api/dm/{id}/read with last_message_id returns 200"""
        # Send a message
        msg_resp = self.user1.session.post(f"{BASE_URL}/api/dm/{self.conversation['id']}/messages", json={
            "content": "Test DM message for read receipt"
        })
        assert msg_resp.status_code == 200, f"Failed to send DM: {msg_resp.text}"
        message = msg_resp.json()
        
        # User2 marks as read
        read_resp = self.user2.session.post(f"{BASE_URL}/api/dm/{self.conversation['id']}/read", json={
            "last_message_id": message["id"]
        })
        assert read_resp.status_code == 200, f"Expected 200, got {read_resp.status_code}: {read_resp.text}"
        print(f"✓ POST /api/dm/{{id}}/read returns 200")
    
    def test_get_dm_read_receipts_returns_array(self):
        """GET /api/dm/{id}/read-receipts returns array"""
        # Send and mark as read
        msg_resp = self.user1.session.post(f"{BASE_URL}/api/dm/{self.conversation['id']}/messages", json={
            "content": "Test DM for receipts list"
        })
        message = msg_resp.json()
        self.user2.session.post(f"{BASE_URL}/api/dm/{self.conversation['id']}/read", json={
            "last_message_id": message["id"]
        })
        
        # Get receipts
        receipts_resp = self.user1.session.get(f"{BASE_URL}/api/dm/{self.conversation['id']}/read-receipts")
        assert receipts_resp.status_code == 200, f"Expected 200, got {receipts_resp.status_code}"
        data = receipts_resp.json()
        assert isinstance(data, list), "Expected array of receipts"
        print(f"✓ GET /api/dm/{{id}}/read-receipts returns array (count: {len(data)})")


# ─── PERMISSION ENFORCEMENT TESTS ───

class TestPermissionEnforcement:
    """Test extended permission checks on endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup: create server with owner and non-owner member"""
        self.owner = TestSession()
        self.member = TestSession()
        
        # Login as admin (owner)
        resp = self.owner.login(ADMIN_EMAIL, ADMIN_PASSWORD)
        if resp.status_code != 200:
            pytest.skip("Admin login failed")
        
        # Register a non-owner member
        unique = uuid.uuid4().hex[:6]
        resp = self.member.register(f"TEST_Member_{unique}", f"member_{unique}@test.local", "TestPass123!")
        if resp.status_code != 200:
            pytest.skip("Failed to register member")
        
        # Create a test server
        server_resp = self.owner.session.post(f"{BASE_URL}/api/servers", json={
            "name": f"TEST_Perms_{unique}"
        })
        if server_resp.status_code != 200:
            pytest.skip("Failed to create test server")
        
        self.server = server_resp.json()
        
        # Get invite code and have member join
        invites_resp = self.owner.session.get(f"{BASE_URL}/api/servers/{self.server['id']}")
        server_detail = invites_resp.json()
        
        # Create invite for member
        invite_resp = self.owner.session.post(f"{BASE_URL}/api/servers/{self.server['id']}/invites", json={})
        if invite_resp.status_code == 200:
            invite = invite_resp.json()
            join_resp = self.member.session.post(f"{BASE_URL}/api/invites/{invite['code']}/join")
        
        # Get channel for message tests
        self.channel = next((c for c in server_detail.get("channels", []) if c["channel_type"] == "text"), None)
        
        yield
        
        # Cleanup
        try:
            self.owner.session.delete(f"{BASE_URL}/api/servers/{self.server['id']}")
        except:
            pass
    
    def test_update_server_requires_manage_server_permission(self):
        """PUT /api/servers/{id} requires MANAGE_SERVER permission (non-owner gets 403)"""
        # Non-owner member tries to update server
        update_resp = self.member.session.put(f"{BASE_URL}/api/servers/{self.server['id']}", json={
            "name": "Unauthorized Update"
        })
        assert update_resp.status_code == 403, f"Expected 403, got {update_resp.status_code}: {update_resp.text}"
        print(f"✓ PUT /api/servers/{{id}} returns 403 for non-owner without MANAGE_SERVER")
    
    def test_owner_can_update_server(self):
        """Owner can always update server (has all permissions)"""
        update_resp = self.owner.session.put(f"{BASE_URL}/api/servers/{self.server['id']}", json={
            "description": "Updated by owner"
        })
        assert update_resp.status_code == 200, f"Expected 200, got {update_resp.status_code}: {update_resp.text}"
        print(f"✓ Owner can update server (bypasses permission check)")
    
    def test_create_invite_requires_create_invite_permission(self):
        """POST /api/servers/{id}/invites requires CREATE_INVITE permission"""
        # First, we need to remove CREATE_INVITE from @everyone role
        # Get server details to find @everyone role
        server_detail = self.owner.session.get(f"{BASE_URL}/api/servers/{self.server['id']}").json()
        everyone_role = next((r for r in server_detail.get("roles", []) if r["name"] == "@everyone"), None)
        
        if everyone_role:
            # Remove CREATE_INVITE (bit 10) from @everyone
            # Default permissions include CREATE_INVITE, so we need to remove it
            new_perms = everyone_role["permissions"] & ~(1 << 10)  # Remove CREATE_INVITE
            self.owner.session.put(f"{BASE_URL}/api/servers/{self.server['id']}/roles/{everyone_role['id']}", json={
                "permissions": new_perms
            })
        
        # Now member should get 403
        invite_resp = self.member.session.post(f"{BASE_URL}/api/servers/{self.server['id']}/invites", json={})
        assert invite_resp.status_code == 403, f"Expected 403, got {invite_resp.status_code}: {invite_resp.text}"
        print(f"✓ POST /api/servers/{{id}}/invites returns 403 without CREATE_INVITE permission")
    
    def test_owner_can_create_invite(self):
        """Owner can always create invites"""
        invite_resp = self.owner.session.post(f"{BASE_URL}/api/servers/{self.server['id']}/invites", json={})
        assert invite_resp.status_code == 200, f"Expected 200, got {invite_resp.status_code}: {invite_resp.text}"
        data = invite_resp.json()
        assert "code" in data
        print(f"✓ Owner can create invites (bypasses permission check)")
    
    def test_add_reaction_requires_add_reactions_permission(self):
        """POST /api/channel-messages/{id}/reactions requires ADD_REACTIONS permission"""
        if not self.channel:
            pytest.skip("No channel available")
        
        # Owner sends a message
        msg_resp = self.owner.session.post(f"{BASE_URL}/api/channels/{self.channel['id']}/messages", json={
            "content": "Test message for reaction permission"
        })
        assert msg_resp.status_code == 200
        message = msg_resp.json()
        
        # Remove ADD_REACTIONS from @everyone
        server_detail = self.owner.session.get(f"{BASE_URL}/api/servers/{self.server['id']}").json()
        everyone_role = next((r for r in server_detail.get("roles", []) if r["name"] == "@everyone"), None)
        
        if everyone_role:
            new_perms = everyone_role["permissions"] & ~(1 << 21)  # Remove ADD_REACTIONS
            self.owner.session.put(f"{BASE_URL}/api/servers/{self.server['id']}/roles/{everyone_role['id']}", json={
                "permissions": new_perms
            })
        
        # Member tries to add reaction
        react_resp = self.member.session.post(f"{BASE_URL}/api/channel-messages/{message['id']}/reactions", json={
            "emoji": "👍"
        })
        assert react_resp.status_code == 403, f"Expected 403, got {react_resp.status_code}: {react_resp.text}"
        print(f"✓ POST /api/channel-messages/{{id}}/reactions returns 403 without ADD_REACTIONS permission")
    
    def test_owner_can_add_reaction(self):
        """Owner can always add reactions"""
        if not self.channel:
            pytest.skip("No channel available")
        
        # Owner sends a message
        msg_resp = self.owner.session.post(f"{BASE_URL}/api/channels/{self.channel['id']}/messages", json={
            "content": "Test message for owner reaction"
        })
        message = msg_resp.json()
        
        # Owner adds reaction
        react_resp = self.owner.session.post(f"{BASE_URL}/api/channel-messages/{message['id']}/reactions", json={
            "emoji": "🎉"
        })
        assert react_resp.status_code == 200, f"Expected 200, got {react_resp.status_code}: {react_resp.text}"
        print(f"✓ Owner can add reactions (bypasses permission check)")
    
    def test_reply_thread_requires_send_messages_in_threads_permission(self):
        """POST /api/channel-messages/{id}/thread requires SEND_MESSAGES_IN_THREADS permission"""
        if not self.channel:
            pytest.skip("No channel available")
        
        # Owner sends a message
        msg_resp = self.owner.session.post(f"{BASE_URL}/api/channels/{self.channel['id']}/messages", json={
            "content": "Test message for thread permission"
        })
        message = msg_resp.json()
        
        # Remove SEND_MESSAGES_IN_THREADS from @everyone
        server_detail = self.owner.session.get(f"{BASE_URL}/api/servers/{self.server['id']}").json()
        everyone_role = next((r for r in server_detail.get("roles", []) if r["name"] == "@everyone"), None)
        
        if everyone_role:
            new_perms = everyone_role["permissions"] & ~(1 << 17)  # Remove SEND_MESSAGES_IN_THREADS
            self.owner.session.put(f"{BASE_URL}/api/servers/{self.server['id']}/roles/{everyone_role['id']}", json={
                "permissions": new_perms
            })
        
        # Member tries to reply in thread
        thread_resp = self.member.session.post(f"{BASE_URL}/api/channel-messages/{message['id']}/thread", json={
            "content": "Unauthorized thread reply"
        })
        assert thread_resp.status_code == 403, f"Expected 403, got {thread_resp.status_code}: {thread_resp.text}"
        print(f"✓ POST /api/channel-messages/{{id}}/thread returns 403 without SEND_MESSAGES_IN_THREADS permission")
    
    def test_owner_can_reply_thread(self):
        """Owner can always reply in threads"""
        if not self.channel:
            pytest.skip("No channel available")
        
        # Owner sends a message
        msg_resp = self.owner.session.post(f"{BASE_URL}/api/channels/{self.channel['id']}/messages", json={
            "content": "Test message for owner thread reply"
        })
        message = msg_resp.json()
        
        # Owner replies in thread
        thread_resp = self.owner.session.post(f"{BASE_URL}/api/channel-messages/{message['id']}/thread", json={
            "content": "Owner thread reply"
        })
        assert thread_resp.status_code == 200, f"Expected 200, got {thread_resp.status_code}: {thread_resp.text}"
        print(f"✓ Owner can reply in threads (bypasses permission check)")


# ─── INTEGRATION TEST: OWNER HAS ALL PERMISSIONS ───

class TestOwnerFullPermissions:
    """Verify owner always has full permissions for all operations"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.owner = TestSession()
        resp = self.owner.login(ADMIN_EMAIL, ADMIN_PASSWORD)
        if resp.status_code != 200:
            pytest.skip("Admin login failed")
        
        # Create server
        unique = uuid.uuid4().hex[:6]
        server_resp = self.owner.session.post(f"{BASE_URL}/api/servers", json={
            "name": f"TEST_OwnerPerms_{unique}"
        })
        if server_resp.status_code != 200:
            pytest.skip("Failed to create server")
        
        self.server = server_resp.json()
        server_detail = self.owner.session.get(f"{BASE_URL}/api/servers/{self.server['id']}").json()
        self.channel = next((c for c in server_detail.get("channels", []) if c["channel_type"] == "text"), None)
        
        yield
        
        try:
            self.owner.session.delete(f"{BASE_URL}/api/servers/{self.server['id']}")
        except:
            pass
    
    def test_owner_has_all_permissions(self):
        """Owner can perform all permission-gated operations"""
        # 1. Update server (MANAGE_SERVER)
        resp = self.owner.session.put(f"{BASE_URL}/api/servers/{self.server['id']}", json={
            "description": "Owner test"
        })
        assert resp.status_code == 200, "Owner should be able to update server"
        
        # 2. Create invite (CREATE_INVITE)
        resp = self.owner.session.post(f"{BASE_URL}/api/servers/{self.server['id']}/invites", json={})
        assert resp.status_code == 200, "Owner should be able to create invite"
        
        if self.channel:
            # 3. Send message and add reaction (ADD_REACTIONS)
            msg_resp = self.owner.session.post(f"{BASE_URL}/api/channels/{self.channel['id']}/messages", json={
                "content": "Owner permission test"
            })
            assert msg_resp.status_code == 200
            message = msg_resp.json()
            
            react_resp = self.owner.session.post(f"{BASE_URL}/api/channel-messages/{message['id']}/reactions", json={
                "emoji": "✅"
            })
            assert react_resp.status_code == 200, "Owner should be able to add reactions"
            
            # 4. Reply in thread (SEND_MESSAGES_IN_THREADS)
            thread_resp = self.owner.session.post(f"{BASE_URL}/api/channel-messages/{message['id']}/thread", json={
                "content": "Owner thread test"
            })
            assert thread_resp.status_code == 200, "Owner should be able to reply in threads"
        
        print(f"✓ Owner has full permissions for all operations")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
