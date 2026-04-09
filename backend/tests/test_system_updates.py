"""
Test System Updates Feature - Admin Dashboard Update Panel
Tests for:
- GET /api/admin/update/config - Get update configuration
- PUT /api/admin/update/config - Update repo URL
- POST /api/admin/update/check - Check for updates from GitHub
- GET /api/admin/update/status - Get update status
- POST /api/admin/update/apply - Apply update (background task)
- Non-admin access restrictions (403)
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestSystemUpdatesAuth:
    """Test authentication and authorization for update endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup admin session"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login as admin
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@shield.local",
            "password": "SecureAdmin2024!"
        })
        assert login_resp.status_code == 200, f"Admin login failed: {login_resp.text}"
        
        # Store cookies for authenticated requests
        self.admin_cookies = login_resp.cookies
        
    def test_01_get_update_config_returns_repo_url(self):
        """GET /api/admin/update/config returns repo_url and status fields"""
        resp = self.session.get(f"{BASE_URL}/api/admin/update/config", cookies=self.admin_cookies)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        assert "repo_url" in data, "Response should contain repo_url"
        print(f"Current repo_url: {data.get('repo_url')}")
        
        # Verify default repo URL
        assert data["repo_url"] == "https://github.com/Tech-Person/shield", \
            f"Expected default repo URL, got: {data['repo_url']}"
        print("PASS: GET /api/admin/update/config returns correct default repo_url")
        
    def test_02_put_update_config_changes_repo_url(self):
        """PUT /api/admin/update/config with {repo_url: 'https://github.com/test/repo'} updates config"""
        test_repo = "https://github.com/test/repo"
        
        # Update repo URL
        resp = self.session.put(
            f"{BASE_URL}/api/admin/update/config",
            json={"repo_url": test_repo},
            cookies=self.admin_cookies
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        print(f"PUT response: {resp.json()}")
        
        # Verify the change persisted
        get_resp = self.session.get(f"{BASE_URL}/api/admin/update/config", cookies=self.admin_cookies)
        assert get_resp.status_code == 200
        data = get_resp.json()
        assert data["repo_url"] == test_repo, f"Expected {test_repo}, got {data['repo_url']}"
        print(f"PASS: PUT /api/admin/update/config updated repo_url to {test_repo}")
        
        # Restore default repo URL
        restore_resp = self.session.put(
            f"{BASE_URL}/api/admin/update/config",
            json={"repo_url": "https://github.com/Tech-Person/shield"},
            cookies=self.admin_cookies
        )
        assert restore_resp.status_code == 200
        print("Restored default repo URL")
        
    def test_03_post_update_check_returns_commits_or_error(self):
        """POST /api/admin/update/check returns has_updates, remote_commits, or error"""
        resp = self.session.post(f"{BASE_URL}/api/admin/update/check", cookies=self.admin_cookies)
        
        # The repo may not exist, so we expect either 200 with data or 500 with error message
        if resp.status_code == 200:
            data = resp.json()
            assert "has_updates" in data, "Response should contain has_updates"
            print(f"Check updates response: has_updates={data.get('has_updates')}")
            
            if "remote_commits" in data and data["remote_commits"]:
                print(f"Found {len(data['remote_commits'])} remote commits")
                for commit in data["remote_commits"][:3]:
                    print(f"  - {commit.get('sha')}: {commit.get('message')}")
            print("PASS: POST /api/admin/update/check returned update info")
        elif resp.status_code == 500:
            # Expected if repo doesn't exist - verify error is handled gracefully
            data = resp.json()
            assert "detail" in data, "Error response should contain detail"
            print(f"Expected error (repo may not exist): {data.get('detail')}")
            print("PASS: POST /api/admin/update/check handles non-existent repo gracefully")
        else:
            pytest.fail(f"Unexpected status code {resp.status_code}: {resp.text}")
            
    def test_04_get_update_status_returns_status_field(self):
        """GET /api/admin/update/status returns status field"""
        resp = self.session.get(f"{BASE_URL}/api/admin/update/status", cookies=self.admin_cookies)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        assert "status" in data, "Response should contain status field"
        print(f"Update status: {data.get('status')}")
        print(f"Full status response: {data}")
        print("PASS: GET /api/admin/update/status returns status field")
        
    def test_05_post_apply_update_returns_in_progress(self):
        """POST /api/admin/update/apply returns 200 with status 'in_progress'"""
        resp = self.session.post(f"{BASE_URL}/api/admin/update/apply", cookies=self.admin_cookies)
        
        # Should return 200 with in_progress status (background task started)
        # Or 409 if update already in progress
        if resp.status_code == 200:
            data = resp.json()
            assert data.get("status") == "in_progress", f"Expected status 'in_progress', got {data}"
            print(f"Apply update response: {data}")
            print("PASS: POST /api/admin/update/apply started background task")
        elif resp.status_code == 409:
            print("Update already in progress (409) - this is expected behavior")
            print("PASS: POST /api/admin/update/apply handles concurrent updates")
        else:
            pytest.fail(f"Unexpected status code {resp.status_code}: {resp.text}")


class TestNonAdminAccess:
    """Test that non-admin users cannot access update endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup non-admin session"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Create a test user (non-admin)
        import uuid
        self.test_email = f"test_update_{uuid.uuid4().hex[:8]}@test.com"
        self.test_password = "TestPass123!"
        
        # Register non-admin user
        register_resp = self.session.post(f"{BASE_URL}/api/auth/register", json={
            "email": self.test_email,
            "username": f"testuser_{uuid.uuid4().hex[:6]}",
            "password": self.test_password
        })
        
        if register_resp.status_code == 200:
            self.user_cookies = register_resp.cookies
            print(f"Created test user: {self.test_email}")
        else:
            # If registration fails, try login (user might exist)
            login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
                "email": self.test_email,
                "password": self.test_password
            })
            if login_resp.status_code == 200:
                self.user_cookies = login_resp.cookies
            else:
                pytest.skip("Could not create or login test user")
                
    def test_06_non_admin_cannot_get_update_config(self):
        """Non-admin users get 403 on GET /api/admin/update/config"""
        resp = self.session.get(f"{BASE_URL}/api/admin/update/config", cookies=self.user_cookies)
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"
        print("PASS: Non-admin cannot access GET /api/admin/update/config (403)")
        
    def test_07_non_admin_cannot_put_update_config(self):
        """Non-admin users get 403 on PUT /api/admin/update/config"""
        resp = self.session.put(
            f"{BASE_URL}/api/admin/update/config",
            json={"repo_url": "https://github.com/hacker/repo"},
            cookies=self.user_cookies
        )
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"
        print("PASS: Non-admin cannot access PUT /api/admin/update/config (403)")
        
    def test_08_non_admin_cannot_check_updates(self):
        """Non-admin users get 403 on POST /api/admin/update/check"""
        resp = self.session.post(f"{BASE_URL}/api/admin/update/check", cookies=self.user_cookies)
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"
        print("PASS: Non-admin cannot access POST /api/admin/update/check (403)")
        
    def test_09_non_admin_cannot_apply_update(self):
        """Non-admin users get 403 on POST /api/admin/update/apply"""
        resp = self.session.post(f"{BASE_URL}/api/admin/update/apply", cookies=self.user_cookies)
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"
        print("PASS: Non-admin cannot access POST /api/admin/update/apply (403)")
        
    def test_10_non_admin_cannot_get_update_status(self):
        """Non-admin users get 403 on GET /api/admin/update/status"""
        resp = self.session.get(f"{BASE_URL}/api/admin/update/status", cookies=self.user_cookies)
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"
        print("PASS: Non-admin cannot access GET /api/admin/update/status (403)")


class TestUnauthenticatedAccess:
    """Test that unauthenticated users cannot access update endpoints"""
    
    def test_11_unauthenticated_cannot_access_update_config(self):
        """Unauthenticated users get 401 on update endpoints"""
        session = requests.Session()
        
        # GET config
        resp = session.get(f"{BASE_URL}/api/admin/update/config")
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"
        print("PASS: Unauthenticated cannot access GET /api/admin/update/config (401)")
        
        # PUT config
        resp = session.put(f"{BASE_URL}/api/admin/update/config", json={"repo_url": "test"})
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"
        print("PASS: Unauthenticated cannot access PUT /api/admin/update/config (401)")
        
        # POST check
        resp = session.post(f"{BASE_URL}/api/admin/update/check")
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"
        print("PASS: Unauthenticated cannot access POST /api/admin/update/check (401)")
        
        # POST apply
        resp = session.post(f"{BASE_URL}/api/admin/update/apply")
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"
        print("PASS: Unauthenticated cannot access POST /api/admin/update/apply (401)")
        
        # GET status
        resp = session.get(f"{BASE_URL}/api/admin/update/status")
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"
        print("PASS: Unauthenticated cannot access GET /api/admin/update/status (401)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
