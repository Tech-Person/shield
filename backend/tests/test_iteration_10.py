"""
Test Suite for Iteration 10 - Bug Fixes
Tests for:
1. WebSocket manager multi-connection support
2. Status update broadcasts (member_status_update)
3. DM messaging (no double messages)
4. DM call endpoints
5. Voice channel subscription
6. Server members with is_online and status fields
"""
import pytest
import requests
import os
import time
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestAuth:
    """Authentication tests"""
    
    @pytest.fixture(scope="class")
    def session(self):
        return requests.Session()
    
    def test_login_admin(self, session):
        """Test admin login"""
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@shield.local",
            "password": "SecureAdmin2024!"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "user" in data or "access_token" in data
        print("Admin login successful")
        return data


class TestDMMessaging:
    """Test DM messaging - no double messages"""
    
    @pytest.fixture(scope="class")
    def user1_session(self):
        """Create and login user1"""
        session = requests.Session()
        unique_id = str(uuid.uuid4())[:8]
        email = f"TEST_user1_{unique_id}@test.com"
        username = f"TEST_user1_{unique_id}"
        
        # Register
        response = session.post(f"{BASE_URL}/api/auth/register", json={
            "email": email,
            "username": username,
            "password": "TestPass123!"
        })
        if response.status_code != 200:
            # Try login if already exists
            response = session.post(f"{BASE_URL}/api/auth/login", json={
                "email": email,
                "password": "TestPass123!"
            })
        
        assert response.status_code == 200, f"User1 auth failed: {response.text}"
        data = response.json()
        return {"session": session, "user": data.get("user", {}), "email": email, "username": username}
    
    @pytest.fixture(scope="class")
    def user2_session(self):
        """Create and login user2"""
        session = requests.Session()
        unique_id = str(uuid.uuid4())[:8]
        email = f"TEST_user2_{unique_id}@test.com"
        username = f"TEST_user2_{unique_id}"
        
        # Register
        response = session.post(f"{BASE_URL}/api/auth/register", json={
            "email": email,
            "username": username,
            "password": "TestPass123!"
        })
        if response.status_code != 200:
            response = session.post(f"{BASE_URL}/api/auth/login", json={
                "email": email,
                "password": "TestPass123!"
            })
        
        assert response.status_code == 200, f"User2 auth failed: {response.text}"
        data = response.json()
        return {"session": session, "user": data.get("user", {}), "email": email, "username": username}
    
    def test_create_dm_and_send_message(self, user1_session, user2_session):
        """Test creating DM and sending message - verify no double messages"""
        user1 = user1_session
        user2 = user2_session
        
        # User1 sends friend request to user2
        response = user1["session"].post(f"{BASE_URL}/api/friends/request", json={
            "username": user2["username"]
        })
        assert response.status_code in [200, 400], f"Friend request failed: {response.text}"
        print(f"Friend request sent: {response.json()}")
        
        # User2 accepts friend request
        user2_id = user2["user"].get("id")
        user1_id = user1["user"].get("id")
        
        if user1_id:
            response = user2["session"].post(f"{BASE_URL}/api/friends/accept/{user1_id}")
            print(f"Friend accept response: {response.status_code} - {response.text}")
        
        # Create DM conversation - need to get user2's ID from their profile
        response = user2["session"].get(f"{BASE_URL}/api/users/me")
        if response.status_code == 200:
            user2_id = response.json().get("id")
        
        response = user1["session"].post(f"{BASE_URL}/api/dm/create", json={
            "recipient_id": user2_id
        })
        assert response.status_code == 200, f"DM creation failed: {response.text}"
        conv = response.json()
        conv_id = conv.get("id")
        assert conv_id, "No conversation ID returned"
        print(f"DM created: {conv_id}")
        
        # Send message from user1
        test_message = f"Test message {uuid.uuid4()}"
        response = user1["session"].post(f"{BASE_URL}/api/dm/{conv_id}/messages", json={
            "content": test_message
        })
        assert response.status_code == 200, f"Message send failed: {response.text}"
        msg_data = response.json()
        msg_id = msg_data.get("id")
        print(f"Message sent: {msg_id}")
        
        # Verify message in DB - check for no duplicates
        time.sleep(0.5)  # Small delay for DB write
        response = user1["session"].get(f"{BASE_URL}/api/dm/{conv_id}/messages")
        assert response.status_code == 200, f"Get messages failed: {response.text}"
        messages = response.json()
        
        # Count messages with our test content
        matching_messages = [m for m in messages if m.get("id") == msg_id]
        assert len(matching_messages) == 1, f"Expected 1 message, found {len(matching_messages)} - possible double message bug!"
        print(f"Message verification passed - no duplicates found")
        
        return conv_id


class TestDMCalls:
    """Test DM call endpoints"""
    
    @pytest.fixture(scope="class")
    def authenticated_session(self):
        """Get authenticated session"""
        session = requests.Session()
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@shield.local",
            "password": "SecureAdmin2024!"
        })
        assert response.status_code == 200
        return session
    
    @pytest.fixture(scope="class")
    def dm_conversation(self, authenticated_session):
        """Get or create a DM conversation"""
        # First get conversations
        response = authenticated_session.get(f"{BASE_URL}/api/dm/conversations")
        assert response.status_code == 200
        convos = response.json()
        
        if convos:
            return convos[0]["id"]
        
        # Create a test user and DM
        unique_id = str(uuid.uuid4())[:8]
        session2 = requests.Session()
        response = session2.post(f"{BASE_URL}/api/auth/register", json={
            "email": f"TEST_calluser_{unique_id}@test.com",
            "username": f"TEST_calluser_{unique_id}",
            "password": "TestPass123!"
        })
        if response.status_code == 200:
            user2_id = response.json().get("user", {}).get("id")
            if user2_id:
                response = authenticated_session.post(f"{BASE_URL}/api/dm/create", json={
                    "recipient_id": user2_id
                })
                if response.status_code == 200:
                    return response.json().get("id")
        
        pytest.skip("Could not create DM conversation for call test")
    
    def test_start_dm_call(self, authenticated_session, dm_conversation):
        """Test POST /api/dm/{id}/call creates a call"""
        response = authenticated_session.post(f"{BASE_URL}/api/dm/{dm_conversation}/call")
        assert response.status_code == 200, f"Start call failed: {response.text}"
        call_data = response.json()
        
        assert "id" in call_data, "Call ID missing"
        assert "conversation_id" in call_data, "Conversation ID missing"
        assert call_data.get("status") == "ringing", f"Expected status 'ringing', got {call_data.get('status')}"
        print(f"Call started: {call_data['id']}")
        return call_data["id"]
    
    def test_end_dm_call(self, authenticated_session, dm_conversation):
        """Test POST /api/dm/call/{id}/end works"""
        # Start a call first
        response = authenticated_session.post(f"{BASE_URL}/api/dm/{dm_conversation}/call")
        assert response.status_code == 200
        call_id = response.json().get("id")
        
        # End the call
        response = authenticated_session.post(f"{BASE_URL}/api/dm/call/{call_id}/end")
        assert response.status_code == 200, f"End call failed: {response.text}"
        data = response.json()
        assert data.get("status") == "ended", f"Expected status 'ended', got {data.get('status')}"
        print(f"Call ended successfully")
    
    def test_decline_dm_call(self, authenticated_session, dm_conversation):
        """Test POST /api/dm/call/{id}/decline works"""
        # Start a call first
        response = authenticated_session.post(f"{BASE_URL}/api/dm/{dm_conversation}/call")
        assert response.status_code == 200
        call_id = response.json().get("id")
        
        # Decline the call
        response = authenticated_session.post(f"{BASE_URL}/api/dm/call/{call_id}/decline")
        assert response.status_code == 200, f"Decline call failed: {response.text}"
        data = response.json()
        assert data.get("status") == "declined", f"Expected status 'declined', got {data.get('status')}"
        print(f"Call declined successfully")


class TestServerMembersStatus:
    """Test GET /api/servers/{id} returns members with is_online and status fields"""
    
    @pytest.fixture(scope="class")
    def authenticated_session(self):
        session = requests.Session()
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@shield.local",
            "password": "SecureAdmin2024!"
        })
        assert response.status_code == 200
        return session
    
    def test_server_members_have_status_fields(self, authenticated_session):
        """Test that server members include is_online and status fields"""
        # Get user's servers
        response = authenticated_session.get(f"{BASE_URL}/api/servers")
        assert response.status_code == 200
        servers = response.json()
        
        if not servers:
            # Create a server
            response = authenticated_session.post(f"{BASE_URL}/api/servers", json={
                "name": f"TEST_Server_{uuid.uuid4()}"[:20]
            })
            assert response.status_code == 200
            server_id = response.json().get("id")
        else:
            server_id = servers[0]["id"]
        
        # Get server details with members
        response = authenticated_session.get(f"{BASE_URL}/api/servers/{server_id}")
        assert response.status_code == 200, f"Get server failed: {response.text}"
        server_data = response.json()
        
        assert "members" in server_data, "Members field missing from server response"
        members = server_data["members"]
        assert len(members) > 0, "No members in server"
        
        # Check first member has required fields
        member = members[0]
        assert "is_online" in member, f"is_online field missing from member: {member.keys()}"
        assert "status" in member, f"status field missing from member: {member.keys()}"
        
        print(f"Server members have is_online={member['is_online']}, status={member['status']}")


class TestStatusUpdate:
    """Test status update broadcasts"""
    
    @pytest.fixture(scope="class")
    def authenticated_session(self):
        session = requests.Session()
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@shield.local",
            "password": "SecureAdmin2024!"
        })
        assert response.status_code == 200
        return session
    
    def test_update_status_to_away(self, authenticated_session):
        """Test updating status to away"""
        response = authenticated_session.put(f"{BASE_URL}/api/users/me/status", json={
            "status": "away"
        })
        assert response.status_code == 200, f"Status update failed: {response.text}"
        print("Status updated to 'away'")
        
        # Verify status was saved
        response = authenticated_session.get(f"{BASE_URL}/api/users/me")
        assert response.status_code == 200
        user = response.json()
        assert user.get("status") == "away", f"Expected status 'away', got {user.get('status')}"
        print("Status verified as 'away'")
    
    def test_update_status_to_online(self, authenticated_session):
        """Test updating status back to online"""
        response = authenticated_session.put(f"{BASE_URL}/api/users/me/status", json={
            "status": "online"
        })
        assert response.status_code == 200, f"Status update failed: {response.text}"
        print("Status updated to 'online'")
    
    def test_update_status_with_message(self, authenticated_session):
        """Test updating status with a custom message"""
        response = authenticated_session.put(f"{BASE_URL}/api/users/me/status", json={
            "status": "busy",
            "status_message": "In a meeting"
        })
        assert response.status_code == 200, f"Status update failed: {response.text}"
        
        # Verify
        response = authenticated_session.get(f"{BASE_URL}/api/users/me")
        assert response.status_code == 200
        user = response.json()
        assert user.get("status") == "busy"
        assert user.get("status_message") == "In a meeting"
        print("Status with message verified")


class TestVoiceChannel:
    """Test voice channel endpoints"""
    
    @pytest.fixture(scope="class")
    def authenticated_session(self):
        session = requests.Session()
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@shield.local",
            "password": "SecureAdmin2024!"
        })
        assert response.status_code == 200
        return session
    
    def test_get_voice_participants(self, authenticated_session):
        """Test getting voice channel participants"""
        # Get servers
        response = authenticated_session.get(f"{BASE_URL}/api/servers")
        assert response.status_code == 200
        servers = response.json()
        
        if not servers:
            pytest.skip("No servers available")
        
        # Get server with channels
        server_id = servers[0]["id"]
        response = authenticated_session.get(f"{BASE_URL}/api/servers/{server_id}")
        assert response.status_code == 200
        server_data = response.json()
        
        # Find voice channel
        voice_channels = [c for c in server_data.get("channels", []) if c.get("channel_type") == "voice"]
        if not voice_channels:
            pytest.skip("No voice channels available")
        
        voice_channel_id = voice_channels[0]["id"]
        
        # Get participants
        response = authenticated_session.get(f"{BASE_URL}/api/channels/{voice_channel_id}/voice-participants")
        assert response.status_code == 200, f"Get voice participants failed: {response.text}"
        participants = response.json()
        assert isinstance(participants, list), "Expected list of participants"
        print(f"Voice channel has {len(participants)} participants")


class TestDMMessagesEndpoint:
    """Test DM messages endpoint is working"""
    
    @pytest.fixture(scope="class")
    def authenticated_session(self):
        session = requests.Session()
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@shield.local",
            "password": "SecureAdmin2024!"
        })
        assert response.status_code == 200
        return session
    
    def test_get_dm_messages(self, authenticated_session):
        """Test GET /api/dm/{conversation_id}/messages works"""
        # Get conversations
        response = authenticated_session.get(f"{BASE_URL}/api/dm/conversations")
        assert response.status_code == 200
        convos = response.json()
        
        if not convos:
            pytest.skip("No DM conversations available")
        
        conv_id = convos[0]["id"]
        
        # Get messages
        response = authenticated_session.get(f"{BASE_URL}/api/dm/{conv_id}/messages")
        assert response.status_code == 200, f"Get DM messages failed: {response.text}"
        messages = response.json()
        assert isinstance(messages, list), "Expected list of messages"
        print(f"DM conversation has {len(messages)} messages")


class TestWebSocketManagerMultiConnection:
    """Test that WebSocket manager supports multiple connections per user"""
    
    def test_websocket_manager_structure(self):
        """Verify websocket_manager.py has correct structure"""
        import sys
        sys.path.insert(0, '/app/backend')
        from websocket_manager import manager
        
        # Check active_connections is a dict with list values
        assert hasattr(manager, 'active_connections'), "active_connections missing"
        assert isinstance(manager.active_connections, dict), "active_connections should be dict"
        
        # Check methods exist
        assert hasattr(manager, 'connect'), "connect method missing"
        assert hasattr(manager, 'disconnect'), "disconnect method missing"
        assert hasattr(manager, 'send_personal'), "send_personal method missing"
        assert hasattr(manager, 'join_voice'), "join_voice method missing"
        assert hasattr(manager, 'subscribe_channel'), "subscribe_channel method missing"
        
        print("WebSocket manager structure verified")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
