"""
Test DM Call API Endpoints - Iteration 14
Tests: POST /api/dm/{id}/call, POST /api/dm/call/{id}/answer, 
       POST /api/dm/call/{id}/decline, POST /api/dm/call/{id}/end
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestDMCallEndpoints:
    """DM Call API tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login as admin
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@shield.local",
            "password": "SecureAdmin2024!"
        })
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        data = login_resp.json()
        self.token = data.get("access_token")
        self.user = data.get("user")
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        
    def test_start_call_invalid_conversation(self):
        """Test starting call with invalid conversation ID returns 404"""
        resp = self.session.post(f"{BASE_URL}/api/dm/invalid-conv-id/call")
        assert resp.status_code == 404
        
    def test_start_call_nonexistent_conversation(self):
        """Test starting call with non-existent UUID returns 404"""
        fake_id = str(uuid.uuid4())
        resp = self.session.post(f"{BASE_URL}/api/dm/{fake_id}/call")
        assert resp.status_code == 404
        
    def test_answer_call_nonexistent(self):
        """Test answering non-existent call returns 404"""
        fake_call_id = str(uuid.uuid4())
        resp = self.session.post(f"{BASE_URL}/api/dm/call/{fake_call_id}/answer")
        assert resp.status_code == 404
        
    def test_decline_call_nonexistent(self):
        """Test declining non-existent call returns 404"""
        fake_call_id = str(uuid.uuid4())
        resp = self.session.post(f"{BASE_URL}/api/dm/call/{fake_call_id}/decline")
        assert resp.status_code == 404
        
    def test_end_call_nonexistent(self):
        """Test ending non-existent call returns 404"""
        fake_call_id = str(uuid.uuid4())
        resp = self.session.post(f"{BASE_URL}/api/dm/call/{fake_call_id}/end")
        assert resp.status_code == 404


class TestDMCallWithConversation:
    """DM Call tests with actual conversation"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and create test conversation"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login as admin
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@shield.local",
            "password": "SecureAdmin2024!"
        })
        assert login_resp.status_code == 200
        data = login_resp.json()
        self.token = data.get("access_token")
        self.user = data.get("user")
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        
        # Get existing conversations
        conv_resp = self.session.get(f"{BASE_URL}/api/dm/conversations")
        assert conv_resp.status_code == 200
        self.conversations = conv_resp.json()
        
    def test_get_conversations(self):
        """Test getting DM conversations"""
        resp = self.session.get(f"{BASE_URL}/api/dm/conversations")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        
    def test_start_call_with_valid_conversation(self):
        """Test starting call with valid conversation (if exists)"""
        if not self.conversations:
            pytest.skip("No conversations available for testing")
            
        conv = self.conversations[0]
        conv_id = conv.get("id")
        
        resp = self.session.post(f"{BASE_URL}/api/dm/{conv_id}/call")
        # Should succeed or fail based on conversation type
        assert resp.status_code in [200, 201, 400, 403]
        
        if resp.status_code == 200:
            data = resp.json()
            assert "id" in data
            assert data.get("status") == "ringing"
            assert data.get("initiator_id") == self.user["id"]
            
            # Test ending the call we just started
            call_id = data["id"]
            end_resp = self.session.post(f"{BASE_URL}/api/dm/call/{call_id}/end")
            assert end_resp.status_code == 200
            assert end_resp.json().get("status") == "ended"


class TestBackendRegressionSpotCheck:
    """Quick spot-check of key backend endpoints (regression from iteration 13)"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@shield.local",
            "password": "SecureAdmin2024!"
        })
        assert login_resp.status_code == 200
        data = login_resp.json()
        self.token = data.get("access_token")
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        
    def test_auth_me(self):
        """Test GET /api/auth/me"""
        resp = self.session.get(f"{BASE_URL}/api/auth/me")
        assert resp.status_code == 200
        data = resp.json()
        # Response is {"user": {...}}
        assert "user" in data
        assert "id" in data["user"]
        assert "username" in data["user"]
        
    def test_servers_list(self):
        """Test GET /api/servers"""
        resp = self.session.get(f"{BASE_URL}/api/servers")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
        
    def test_friends_list(self):
        """Test GET /api/friends"""
        resp = self.session.get(f"{BASE_URL}/api/friends")
        assert resp.status_code == 200
        
    def test_turn_credentials(self):
        """Test GET /api/turn/credentials"""
        resp = self.session.get(f"{BASE_URL}/api/turn/credentials")
        assert resp.status_code == 200
        data = resp.json()
        assert "ice_servers" in data
        
    def test_admin_stats(self):
        """Test GET /api/admin/stats"""
        resp = self.session.get(f"{BASE_URL}/api/admin/stats")
        assert resp.status_code == 200
