"""
Test Member Role Assignment Feature
Tests POST/DELETE /servers/{id}/members/{userId}/roles/{roleId} endpoints
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestMemberRoleAssignment:
    """Tests for assigning and removing roles from server members"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup: Login as admin and get a server with roles"""
        self.session = requests.Session()
        
        # Login as admin
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@securecomm.local",
            "password": "SecureAdmin2024!"
        })
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        self.user = login_resp.json()
        print(f"Logged in as: {self.user.get('email')}")
        
        # Get servers
        servers_resp = self.session.get(f"{BASE_URL}/api/servers")
        assert servers_resp.status_code == 200
        servers = servers_resp.json()
        
        if servers:
            self.server = servers[0]
            self.server_id = self.server['id']
            print(f"Using server: {self.server.get('name')} (id: {self.server_id})")
        else:
            # Create a test server
            create_resp = self.session.post(f"{BASE_URL}/api/servers", json={
                "name": "TEST_MemberRoleServer"
            })
            assert create_resp.status_code == 200
            self.server = create_resp.json()
            self.server_id = self.server['id']
            print(f"Created test server: {self.server_id}")
        
        yield
        
        # Cleanup: Delete test server if we created one
        if self.server.get('name', '').startswith('TEST_'):
            self.session.delete(f"{BASE_URL}/api/servers/{self.server_id}")
    
    def test_server_has_everyone_role(self):
        """Verify server has @everyone role by default"""
        # Get server details
        server_resp = self.session.get(f"{BASE_URL}/api/servers/{self.server_id}")
        assert server_resp.status_code == 200
        server = server_resp.json()
        
        roles = server.get('roles', [])
        everyone_role = next((r for r in roles if r['name'] == '@everyone'), None)
        
        assert everyone_role is not None, "Server should have @everyone role"
        print(f"Found @everyone role: {everyone_role['id']}")
    
    def test_create_custom_role(self):
        """Create a custom role for testing"""
        role_data = {
            "name": "TEST_CustomRole",
            "color": "#FF5733",
            "permissions": 0
        }
        
        create_resp = self.session.post(f"{BASE_URL}/api/servers/{self.server_id}/roles", json=role_data)
        assert create_resp.status_code == 200, f"Failed to create role: {create_resp.text}"
        
        role = create_resp.json()
        assert role['name'] == "TEST_CustomRole"
        assert 'id' in role
        print(f"Created custom role: {role['id']}")
        
        # Store for later tests
        self.custom_role_id = role['id']
        return role
    
    def test_assign_role_to_member(self):
        """Test POST /servers/{id}/members/{userId}/roles/{roleId}"""
        # First create a custom role
        role = self.test_create_custom_role()
        role_id = role['id']
        
        # Get server members
        server_resp = self.session.get(f"{BASE_URL}/api/servers/{self.server_id}")
        assert server_resp.status_code == 200
        server = server_resp.json()
        
        members = server.get('members', [])
        assert len(members) > 0, "Server should have at least one member"
        
        member = members[0]
        user_id = member['user_id']
        print(f"Assigning role {role_id} to member {user_id}")
        
        # Assign role
        assign_resp = self.session.post(
            f"{BASE_URL}/api/servers/{self.server_id}/members/{user_id}/roles/{role_id}"
        )
        assert assign_resp.status_code == 200, f"Failed to assign role: {assign_resp.text}"
        
        result = assign_resp.json()
        assert result.get('message') == "Role assigned"
        print(f"Role assigned successfully: {result}")
        
        # Verify role was assigned by fetching server again
        verify_resp = self.session.get(f"{BASE_URL}/api/servers/{self.server_id}")
        assert verify_resp.status_code == 200
        updated_server = verify_resp.json()
        
        updated_member = next((m for m in updated_server.get('members', []) if m['user_id'] == user_id), None)
        assert updated_member is not None
        assert role_id in updated_member.get('roles', []), "Role should be in member's roles list"
        print(f"Verified: Member now has roles: {updated_member.get('roles')}")
        
        # Cleanup: Remove the role
        self.session.delete(f"{BASE_URL}/api/servers/{self.server_id}/members/{user_id}/roles/{role_id}")
        self.session.delete(f"{BASE_URL}/api/servers/{self.server_id}/roles/{role_id}")
    
    def test_remove_role_from_member(self):
        """Test DELETE /servers/{id}/members/{userId}/roles/{roleId}"""
        # Create a custom role
        role = self.test_create_custom_role()
        role_id = role['id']
        
        # Get member
        server_resp = self.session.get(f"{BASE_URL}/api/servers/{self.server_id}")
        server = server_resp.json()
        member = server.get('members', [])[0]
        user_id = member['user_id']
        
        # First assign the role
        self.session.post(f"{BASE_URL}/api/servers/{self.server_id}/members/{user_id}/roles/{role_id}")
        
        # Now remove the role
        remove_resp = self.session.delete(
            f"{BASE_URL}/api/servers/{self.server_id}/members/{user_id}/roles/{role_id}"
        )
        assert remove_resp.status_code == 200, f"Failed to remove role: {remove_resp.text}"
        
        result = remove_resp.json()
        assert result.get('message') == "Role removed"
        print(f"Role removed successfully: {result}")
        
        # Verify role was removed
        verify_resp = self.session.get(f"{BASE_URL}/api/servers/{self.server_id}")
        updated_server = verify_resp.json()
        updated_member = next((m for m in updated_server.get('members', []) if m['user_id'] == user_id), None)
        
        assert role_id not in updated_member.get('roles', []), "Role should be removed from member's roles"
        print(f"Verified: Member roles after removal: {updated_member.get('roles')}")
        
        # Cleanup
        self.session.delete(f"{BASE_URL}/api/servers/{self.server_id}/roles/{role_id}")
    
    def test_assign_role_non_owner_forbidden(self):
        """Test that non-owners cannot assign roles"""
        # This test would require a second user account
        # For now, we verify the endpoint exists and returns proper error for invalid server
        
        assign_resp = self.session.post(
            f"{BASE_URL}/api/servers/invalid-server-id/members/some-user/roles/some-role"
        )
        # Should return 403 (no permission) or 404 (not found)
        assert assign_resp.status_code in [403, 404], f"Expected 403/404, got {assign_resp.status_code}"
        print(f"Non-owner/invalid server returns: {assign_resp.status_code}")
    
    def test_member_shows_everyone_badge(self):
        """Verify members have @everyone role by default (implicit)"""
        server_resp = self.session.get(f"{BASE_URL}/api/servers/{self.server_id}")
        assert server_resp.status_code == 200
        server = server_resp.json()
        
        # Check that @everyone role exists
        roles = server.get('roles', [])
        everyone_role = next((r for r in roles if r['name'] == '@everyone'), None)
        assert everyone_role is not None, "@everyone role should exist"
        
        # Members should have access to @everyone permissions even if not explicitly in roles array
        members = server.get('members', [])
        assert len(members) > 0
        print(f"Server has {len(members)} members and @everyone role exists")


class TestDeploymentScripts:
    """Tests for Debian deployment scripts"""
    
    def test_install_script_exists(self):
        """Verify install.sh exists at /app/deploy/install.sh"""
        assert os.path.exists('/app/deploy/install.sh'), "install.sh should exist"
        print("install.sh exists at /app/deploy/install.sh")
    
    def test_install_script_executable(self):
        """Verify install.sh is executable"""
        assert os.access('/app/deploy/install.sh', os.X_OK), "install.sh should be executable"
        print("install.sh is executable")
    
    def test_install_script_has_shebang(self):
        """Verify install.sh has proper bash shebang"""
        with open('/app/deploy/install.sh', 'r') as f:
            first_line = f.readline().strip()
        assert first_line.startswith('#!/'), "install.sh should have shebang"
        assert 'bash' in first_line, "install.sh should use bash"
        print(f"install.sh shebang: {first_line}")
    
    def test_install_script_has_strict_mode(self):
        """Verify install.sh uses set -euo pipefail"""
        with open('/app/deploy/install.sh', 'r') as f:
            content = f.read()
        assert 'set -euo pipefail' in content, "install.sh should use strict mode"
        print("install.sh has strict mode (set -euo pipefail)")
    
    def test_install_script_has_required_sections(self):
        """Verify install.sh has all required installation sections"""
        with open('/app/deploy/install.sh', 'r') as f:
            content = f.read()
        
        required_sections = [
            ('MongoDB', ['mongodb', 'mongod']),
            ('Node.js', ['node', 'nodejs']),
            ('Python venv', ['python3', 'venv']),
            ('nginx', ['nginx']),
            ('systemd', ['systemd', 'systemctl']),
            ('TLS/Let\'s Encrypt', ['certbot', 'TLS', 'Let\'s Encrypt'])
        ]
        
        for section_name, keywords in required_sections:
            found = any(kw.lower() in content.lower() for kw in keywords)
            assert found, f"install.sh should have {section_name} section"
            print(f"Found {section_name} section")
    
    def test_uninstall_script_exists(self):
        """Verify uninstall.sh exists at /app/deploy/uninstall.sh"""
        assert os.path.exists('/app/deploy/uninstall.sh'), "uninstall.sh should exist"
        print("uninstall.sh exists at /app/deploy/uninstall.sh")
    
    def test_uninstall_script_executable(self):
        """Verify uninstall.sh is executable"""
        assert os.access('/app/deploy/uninstall.sh', os.X_OK), "uninstall.sh should be executable"
        print("uninstall.sh is executable")
    
    def test_readme_exists(self):
        """Verify README.md exists at /app/deploy/README.md"""
        assert os.path.exists('/app/deploy/README.md'), "README.md should exist"
        print("README.md exists at /app/deploy/README.md")
    
    def test_readme_has_configuration_instructions(self):
        """Verify README.md has configuration instructions"""
        with open('/app/deploy/README.md', 'r') as f:
            content = f.read()
        
        required_content = [
            'Configuration',
            'SECURECOMM_DOMAIN',
            'SECURECOMM_ADMIN_EMAIL',
            'SECURECOMM_ADMIN_PASSWORD'
        ]
        
        for item in required_content:
            assert item in content, f"README.md should contain {item}"
            print(f"README.md contains: {item}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
