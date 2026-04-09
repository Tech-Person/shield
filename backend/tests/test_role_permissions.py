"""
Test suite for Discord-style Role Permission System
Tests: Role CRUD, Permission toggles, @everyone role protection, Permission enforcement
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@securecomm.local"
ADMIN_PASSWORD = "SecureAdmin2024!"


class TestRolePermissionSystem:
    """Tests for the role permission system feature"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session with authentication"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login as admin
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        self.user = login_resp.json().get("user", {})
        
        # Create a test server for role testing
        server_name = f"TEST_RoleServer_{uuid.uuid4().hex[:6]}"
        server_resp = self.session.post(f"{BASE_URL}/api/servers", json={
            "name": server_name,
            "description": "Test server for role permissions"
        })
        assert server_resp.status_code == 200, f"Server creation failed: {server_resp.text}"
        self.server = server_resp.json()
        self.server_id = self.server["id"]
        
        yield
        
        # Cleanup: Delete test server
        try:
            self.session.delete(f"{BASE_URL}/api/servers/{self.server_id}")
        except:
            pass
    
    # ─── TEST 10: GET /api/permissions/map returns categorized permissions ───
    def test_permissions_map_endpoint(self):
        """Test 10: GET /api/permissions/map returns categorized permissions with correct structure"""
        resp = self.session.get(f"{BASE_URL}/api/permissions/map")
        assert resp.status_code == 200, f"Permissions map failed: {resp.text}"
        
        data = resp.json()
        
        # Verify structure
        assert "permissions" in data, "Response should have 'permissions' key"
        assert "default" in data, "Response should have 'default' key"
        
        permissions = data["permissions"]
        
        # Verify all expected categories exist
        expected_categories = [
            "general_server", "membership", "text_channel", 
            "voice_channel", "apps", "stage", "events", "advanced"
        ]
        for category in expected_categories:
            assert category in permissions, f"Missing category: {category}"
        
        # Verify each permission has required fields
        total_permissions = 0
        for category, perms in permissions.items():
            assert isinstance(perms, list), f"Category {category} should be a list"
            for perm in perms:
                assert "key" in perm, f"Permission missing 'key' in {category}"
                assert "bit" in perm, f"Permission missing 'bit' in {category}"
                assert "name" in perm, f"Permission missing 'name' in {category}"
                assert "description" in perm, f"Permission missing 'description' in {category}"
                total_permissions += 1
        
        # Verify we have 47 total permissions
        assert total_permissions == 47, f"Expected 47 permissions, got {total_permissions}"
        
        # Verify default is a valid integer
        assert isinstance(data["default"], int), "Default should be an integer"
        print(f"✓ Permissions map has {total_permissions} permissions across {len(permissions)} categories")
    
    # ─── TEST: @everyone role exists with default permissions ───
    def test_everyone_role_exists_on_server(self):
        """Test 1: Verify @everyone role exists on server with default permissions"""
        # Get server details
        resp = self.session.get(f"{BASE_URL}/api/servers/{self.server_id}")
        assert resp.status_code == 200, f"Get server failed: {resp.text}"
        
        server = resp.json()
        roles = server.get("roles", [])
        
        # Find @everyone role
        everyone_role = next((r for r in roles if r["name"] == "@everyone"), None)
        assert everyone_role is not None, "@everyone role should exist"
        
        # Verify it has permissions set
        assert "permissions" in everyone_role, "@everyone should have permissions"
        assert everyone_role["permissions"] > 0, "@everyone should have some default permissions"
        
        # Verify VIEW_CHANNELS (bit 1<<1 = 2) is ON by default
        VIEW_CHANNELS = 1 << 1
        has_view_channels = (everyone_role["permissions"] & VIEW_CHANNELS) == VIEW_CHANNELS
        assert has_view_channels, "VIEW_CHANNELS should be ON by default for @everyone"
        
        # Verify MANAGE_CHANNELS (bit 1<<2 = 4) is OFF by default
        MANAGE_CHANNELS = 1 << 2
        has_manage_channels = (everyone_role["permissions"] & MANAGE_CHANNELS) == MANAGE_CHANNELS
        assert not has_manage_channels, "MANAGE_CHANNELS should be OFF by default for @everyone"
        
        print(f"✓ @everyone role exists with permissions: {everyone_role['permissions']}")
    
    # ─── TEST 5: Create new role ───
    def test_create_new_role(self):
        """Test 5: Create a new role via POST /api/servers/{id}/roles"""
        role_name = f"TEST_Moderator_{uuid.uuid4().hex[:4]}"
        resp = self.session.post(f"{BASE_URL}/api/servers/{self.server_id}/roles", json={
            "name": role_name,
            "color": "#FF5733",
            "permissions": 0
        })
        assert resp.status_code == 200, f"Create role failed: {resp.text}"
        
        role = resp.json()
        assert role["name"] == role_name, "Role name should match"
        assert role["color"] == "#FF5733", "Role color should match"
        assert "id" in role, "Role should have an ID"
        
        # Verify role appears in server
        server_resp = self.session.get(f"{BASE_URL}/api/servers/{self.server_id}")
        server = server_resp.json()
        role_names = [r["name"] for r in server.get("roles", [])]
        assert role_name in role_names, "New role should appear in server roles"
        
        print(f"✓ Created role '{role_name}' with ID: {role['id']}")
        return role
    
    # ─── TEST 11: PUT /api/servers/{id}/roles/{roleId} updates permissions ───
    def test_update_role_permissions(self):
        """Test 11: PUT /api/servers/{id}/roles/{roleId} updates permissions correctly"""
        # First create a role
        role_name = f"TEST_UpdateRole_{uuid.uuid4().hex[:4]}"
        create_resp = self.session.post(f"{BASE_URL}/api/servers/{self.server_id}/roles", json={
            "name": role_name,
            "color": "#00FF00",
            "permissions": 0
        })
        assert create_resp.status_code == 200
        role = create_resp.json()
        role_id = role["id"]
        
        # Update permissions - add MANAGE_CHANNELS (1<<2) and KICK_MEMBERS (1<<13)
        MANAGE_CHANNELS = 1 << 2
        KICK_MEMBERS = 1 << 13
        new_permissions = MANAGE_CHANNELS | KICK_MEMBERS
        
        update_resp = self.session.put(f"{BASE_URL}/api/servers/{self.server_id}/roles/{role_id}", json={
            "permissions": new_permissions
        })
        assert update_resp.status_code == 200, f"Update role failed: {update_resp.text}"
        
        # Verify persistence by fetching server
        server_resp = self.session.get(f"{BASE_URL}/api/servers/{self.server_id}")
        server = server_resp.json()
        updated_role = next((r for r in server.get("roles", []) if r["id"] == role_id), None)
        
        assert updated_role is not None, "Role should still exist"
        assert updated_role["permissions"] == new_permissions, f"Permissions should be {new_permissions}, got {updated_role['permissions']}"
        
        print(f"✓ Updated role permissions to {new_permissions}")
    
    # ─── TEST 4: Toggle permission and verify persistence ───
    def test_toggle_permission_persistence(self):
        """Test 4: Toggle a permission, save, verify it persists"""
        # Get @everyone role
        server_resp = self.session.get(f"{BASE_URL}/api/servers/{self.server_id}")
        server = server_resp.json()
        everyone_role = next((r for r in server.get("roles", []) if r["name"] == "@everyone"), None)
        assert everyone_role is not None
        
        original_perms = everyone_role["permissions"]
        
        # Toggle MANAGE_CHANNELS ON (1<<2 = 4)
        MANAGE_CHANNELS = 1 << 2
        new_perms = original_perms | MANAGE_CHANNELS
        
        update_resp = self.session.put(
            f"{BASE_URL}/api/servers/{self.server_id}/roles/{everyone_role['id']}", 
            json={"permissions": new_perms}
        )
        assert update_resp.status_code == 200, f"Update failed: {update_resp.text}"
        
        # Verify persistence
        server_resp2 = self.session.get(f"{BASE_URL}/api/servers/{self.server_id}")
        server2 = server_resp2.json()
        updated_everyone = next((r for r in server2.get("roles", []) if r["name"] == "@everyone"), None)
        
        assert (updated_everyone["permissions"] & MANAGE_CHANNELS) == MANAGE_CHANNELS, \
            "MANAGE_CHANNELS should be ON after toggle"
        
        # Toggle it back OFF
        reverted_perms = updated_everyone["permissions"] ^ MANAGE_CHANNELS
        self.session.put(
            f"{BASE_URL}/api/servers/{self.server_id}/roles/{everyone_role['id']}", 
            json={"permissions": reverted_perms}
        )
        
        print(f"✓ Permission toggle persists correctly")
    
    # ─── TEST 7: Delete custom role ───
    def test_delete_custom_role(self):
        """Test 7: Delete a custom role (not @everyone), verify removal"""
        # Create a role to delete
        role_name = f"TEST_ToDelete_{uuid.uuid4().hex[:4]}"
        create_resp = self.session.post(f"{BASE_URL}/api/servers/{self.server_id}/roles", json={
            "name": role_name,
            "color": "#FF0000",
            "permissions": 0
        })
        assert create_resp.status_code == 200
        role = create_resp.json()
        role_id = role["id"]
        
        # Delete the role
        delete_resp = self.session.delete(f"{BASE_URL}/api/servers/{self.server_id}/roles/{role_id}")
        assert delete_resp.status_code == 200, f"Delete role failed: {delete_resp.text}"
        
        # Verify removal
        server_resp = self.session.get(f"{BASE_URL}/api/servers/{self.server_id}")
        server = server_resp.json()
        role_ids = [r["id"] for r in server.get("roles", [])]
        assert role_id not in role_ids, "Deleted role should not appear in server roles"
        
        print(f"✓ Custom role '{role_name}' deleted successfully")
    
    # ─── TEST 12: DELETE @everyone role should fail ───
    def test_cannot_delete_everyone_role(self):
        """Test 12: DELETE /api/servers/{id}/roles/{roleId} fails for @everyone"""
        # Get @everyone role ID
        server_resp = self.session.get(f"{BASE_URL}/api/servers/{self.server_id}")
        server = server_resp.json()
        everyone_role = next((r for r in server.get("roles", []) if r["name"] == "@everyone"), None)
        assert everyone_role is not None
        
        # Try to delete @everyone - should fail with 400
        delete_resp = self.session.delete(f"{BASE_URL}/api/servers/{self.server_id}/roles/{everyone_role['id']}")
        assert delete_resp.status_code == 400, f"Should fail with 400, got {delete_resp.status_code}"
        
        # Verify @everyone still exists
        server_resp2 = self.session.get(f"{BASE_URL}/api/servers/{self.server_id}")
        server2 = server_resp2.json()
        everyone_still_exists = any(r["name"] == "@everyone" for r in server2.get("roles", []))
        assert everyone_still_exists, "@everyone role should still exist after failed delete"
        
        print(f"✓ @everyone role cannot be deleted (400 returned)")
    
    # ─── TEST: Permission enforcement on create_channel ───
    def test_permission_enforcement_create_channel(self):
        """Test permission enforcement: create_channel requires MANAGE_CHANNELS"""
        # Register a new test user
        test_email = f"test_perm_{uuid.uuid4().hex[:6]}@test.com"
        test_password = "TestPass123!"
        
        new_session = requests.Session()
        new_session.headers.update({"Content-Type": "application/json"})
        
        reg_resp = new_session.post(f"{BASE_URL}/api/auth/register", json={
            "username": f"testuser_{uuid.uuid4().hex[:4]}",
            "email": test_email,
            "password": test_password
        })
        assert reg_resp.status_code == 200, f"Registration failed: {reg_resp.text}"
        new_user = reg_resp.json().get("user", {})
        
        # Get invite code and join server
        invite_resp = self.session.post(f"{BASE_URL}/api/servers/{self.server_id}/invites", json={
            "expires_hours": 1
        })
        assert invite_resp.status_code == 200
        invite_code = invite_resp.json()["code"]
        
        join_resp = new_session.post(f"{BASE_URL}/api/invites/{invite_code}/join")
        assert join_resp.status_code == 200, f"Join failed: {join_resp.text}"
        
        # Try to create channel without MANAGE_CHANNELS permission - should fail
        channel_resp = new_session.post(f"{BASE_URL}/api/servers/{self.server_id}/channels", json={
            "name": "test-channel",
            "channel_type": "text"
        })
        # Should fail with 403 since @everyone doesn't have MANAGE_CHANNELS by default
        assert channel_resp.status_code == 403, f"Should fail with 403, got {channel_resp.status_code}: {channel_resp.text}"
        
        print(f"✓ Permission enforcement works for create_channel")
    
    # ─── TEST: Permission enforcement on kick_member ───
    def test_permission_enforcement_kick(self):
        """Test permission enforcement: kick requires KICK_MEMBERS permission"""
        # Register a new test user
        test_email = f"test_kick_{uuid.uuid4().hex[:6]}@test.com"
        
        new_session = requests.Session()
        new_session.headers.update({"Content-Type": "application/json"})
        
        reg_resp = new_session.post(f"{BASE_URL}/api/auth/register", json={
            "username": f"kicktest_{uuid.uuid4().hex[:4]}",
            "email": test_email,
            "password": "TestPass123!"
        })
        assert reg_resp.status_code == 200
        new_user = reg_resp.json().get("user", {})
        
        # Join server
        invite_resp = self.session.post(f"{BASE_URL}/api/servers/{self.server_id}/invites", json={"expires_hours": 1})
        invite_code = invite_resp.json()["code"]
        new_session.post(f"{BASE_URL}/api/invites/{invite_code}/join")
        
        # Try to kick someone without KICK_MEMBERS permission - should fail
        kick_resp = new_session.post(f"{BASE_URL}/api/servers/{self.server_id}/kick/{self.user['id']}")
        assert kick_resp.status_code == 403, f"Should fail with 403, got {kick_resp.status_code}"
        
        print(f"✓ Permission enforcement works for kick_member")
    
    # ─── TEST: Permission enforcement on ban_member ───
    def test_permission_enforcement_ban(self):
        """Test permission enforcement: ban requires BAN_MEMBERS permission"""
        # Register a new test user
        test_email = f"test_ban_{uuid.uuid4().hex[:6]}@test.com"
        
        new_session = requests.Session()
        new_session.headers.update({"Content-Type": "application/json"})
        
        reg_resp = new_session.post(f"{BASE_URL}/api/auth/register", json={
            "username": f"bantest_{uuid.uuid4().hex[:4]}",
            "email": test_email,
            "password": "TestPass123!"
        })
        assert reg_resp.status_code == 200
        
        # Join server
        invite_resp = self.session.post(f"{BASE_URL}/api/servers/{self.server_id}/invites", json={"expires_hours": 1})
        invite_code = invite_resp.json()["code"]
        new_session.post(f"{BASE_URL}/api/invites/{invite_code}/join")
        
        # Try to ban someone without BAN_MEMBERS permission - should fail
        ban_resp = new_session.post(f"{BASE_URL}/api/servers/{self.server_id}/ban/{self.user['id']}")
        assert ban_resp.status_code == 403, f"Should fail with 403, got {ban_resp.status_code}"
        
        print(f"✓ Permission enforcement works for ban_member")
    
    # ─── TEST: Owner has all permissions ───
    def test_owner_has_all_permissions(self):
        """Test that server owner can perform all actions regardless of role permissions"""
        # Owner should be able to create channel even if @everyone doesn't have MANAGE_CHANNELS
        channel_resp = self.session.post(f"{BASE_URL}/api/servers/{self.server_id}/channels", json={
            "name": "owner-test-channel",
            "channel_type": "text"
        })
        assert channel_resp.status_code == 200, f"Owner should be able to create channel: {channel_resp.text}"
        
        print(f"✓ Owner has all permissions (bypasses role checks)")
    
    # ─── TEST: Large permission bit values (up to 2^46) ───
    def test_large_permission_bits(self):
        """Test that large permission bit values (up to 2^46) work correctly"""
        # Create a role with high bit permissions
        MANAGE_EVENTS = 1 << 46  # Highest permission bit
        CREATE_EVENTS = 1 << 45
        
        role_name = f"TEST_HighBits_{uuid.uuid4().hex[:4]}"
        create_resp = self.session.post(f"{BASE_URL}/api/servers/{self.server_id}/roles", json={
            "name": role_name,
            "color": "#9900FF",
            "permissions": MANAGE_EVENTS | CREATE_EVENTS
        })
        assert create_resp.status_code == 200, f"Create role with high bits failed: {create_resp.text}"
        role = create_resp.json()
        
        # Verify the permissions are stored correctly
        server_resp = self.session.get(f"{BASE_URL}/api/servers/{self.server_id}")
        server = server_resp.json()
        created_role = next((r for r in server.get("roles", []) if r["id"] == role["id"]), None)
        
        assert created_role is not None
        assert (created_role["permissions"] & MANAGE_EVENTS) == MANAGE_EVENTS, "MANAGE_EVENTS bit should be set"
        assert (created_role["permissions"] & CREATE_EVENTS) == CREATE_EVENTS, "CREATE_EVENTS bit should be set"
        
        print(f"✓ Large permission bits (up to 2^46) work correctly")


class TestPermissionMapStructure:
    """Additional tests for permission map structure"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert login_resp.status_code == 200
    
    def test_permission_categories_content(self):
        """Verify each category has expected permissions"""
        resp = self.session.get(f"{BASE_URL}/api/permissions/map")
        assert resp.status_code == 200
        
        permissions = resp.json()["permissions"]
        
        # Check specific permissions exist in correct categories
        general_keys = [p["key"] for p in permissions["general_server"]]
        assert "VIEW_CHANNELS" in general_keys
        assert "MANAGE_CHANNELS" in general_keys
        assert "MANAGE_ROLES" in general_keys
        assert "MANAGE_SERVER" in general_keys
        
        membership_keys = [p["key"] for p in permissions["membership"]]
        assert "KICK_MEMBERS" in membership_keys
        assert "BAN_MEMBERS" in membership_keys
        assert "CREATE_INVITE" in membership_keys
        
        text_keys = [p["key"] for p in permissions["text_channel"]]
        assert "SEND_MESSAGES" in text_keys
        assert "MANAGE_MESSAGES" in text_keys
        assert "READ_MESSAGE_HISTORY" in text_keys
        
        voice_keys = [p["key"] for p in permissions["voice_channel"]]
        assert "CONNECT" in voice_keys
        assert "SPEAK" in voice_keys
        assert "MUTE_MEMBERS" in voice_keys
        
        advanced_keys = [p["key"] for p in permissions["advanced"]]
        assert "ADMINISTRATOR" in advanced_keys
        
        print(f"✓ All expected permissions exist in correct categories")
    
    def test_default_permissions_include_view_channels(self):
        """Verify default permissions include VIEW_CHANNELS"""
        resp = self.session.get(f"{BASE_URL}/api/permissions/map")
        default = resp.json()["default"]
        
        VIEW_CHANNELS = 1 << 1
        assert (default & VIEW_CHANNELS) == VIEW_CHANNELS, "Default should include VIEW_CHANNELS"
        
        SEND_MESSAGES = 1 << 16
        assert (default & SEND_MESSAGES) == SEND_MESSAGES, "Default should include SEND_MESSAGES"
        
        print(f"✓ Default permissions include expected bits")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
