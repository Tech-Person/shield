#!/usr/bin/env python3

import requests
import sys
import json
import uuid
from datetime import datetime

class SecureCommAPITester:
    def __init__(self, base_url="https://shield-msg-1.preview.emergentagent.com"):
        self.base_url = base_url
        self.session = requests.Session()
        self.tests_run = 0
        self.tests_passed = 0
        self.admin_token = None
        self.user_token = None
        self.test_user_id = None
        self.test_server_id = None
        self.test_channel_id = None
        self.test_conversation_id = None
        self.test_friend_id = None
        self.test_invite_code = None

    def log(self, message):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")

    def run_test(self, name, method, endpoint, expected_status, data=None, headers=None, cookies=None):
        """Run a single API test"""
        url = f"{self.base_url}/api/{endpoint}"
        test_headers = {'Content-Type': 'application/json'}
        if headers:
            test_headers.update(headers)

        self.tests_run += 1
        self.log(f"🔍 Testing {name}...")
        
        try:
            if method == 'GET':
                response = self.session.get(url, headers=test_headers, cookies=cookies)
            elif method == 'POST':
                response = self.session.post(url, json=data, headers=test_headers, cookies=cookies)
            elif method == 'PUT':
                response = self.session.put(url, json=data, headers=test_headers, cookies=cookies)
            elif method == 'DELETE':
                response = self.session.delete(url, headers=test_headers, cookies=cookies)

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                self.log(f"✅ {name} - Status: {response.status_code}")
                try:
                    return True, response.json() if response.content else {}
                except:
                    return True, {}
            else:
                self.log(f"❌ {name} - Expected {expected_status}, got {response.status_code}")
                try:
                    error_detail = response.json()
                    self.log(f"   Error: {error_detail}")
                except:
                    self.log(f"   Response: {response.text[:200]}")
                return False, {}

        except Exception as e:
            self.log(f"❌ {name} - Error: {str(e)}")
            return False, {}

    def test_admin_login(self):
        """Test admin login and get token"""
        success, response = self.run_test(
            "Admin Login",
            "POST",
            "auth/login",
            200,
            data={"email": "admin@securecomm.local", "password": "SecureAdmin2024!"}
        )
        if success and 'access_token' in response:
            self.admin_token = response['access_token']
            # Store cookies from session for subsequent requests
            return True
        return False

    def test_user_registration(self):
        """Test user registration"""
        test_username = f"testuser_{datetime.now().strftime('%H%M%S')}"
        test_email = f"test_{datetime.now().strftime('%H%M%S')}@example.com"
        
        success, response = self.run_test(
            "User Registration",
            "POST",
            "auth/register",
            200,
            data={
                "username": test_username,
                "email": test_email,
                "password": "TestPass123!"
            }
        )
        if success and 'user' in response:
            self.test_user_id = response['user']['id']
            self.user_token = response.get('access_token')
            return True
        return False

    def test_user_login(self):
        """Test user login"""
        # Use unique timestamp with microseconds to avoid conflicts
        timestamp = datetime.now().strftime('%H%M%S%f')
        test_email = f"logintest_{timestamp}@example.com"
        test_username = f"loginuser_{timestamp}"
        
        # First register a user
        reg_success, reg_response = self.run_test(
            "User Registration for Login Test",
            "POST",
            "auth/register",
            200,
            data={
                "username": test_username,
                "email": test_email,
                "password": "TestPass123!"
            }
        )
        
        if not reg_success:
            return False
            
        # Now test login
        success, response = self.run_test(
            "User Login",
            "POST",
            "auth/login",
            200,
            data={"email": test_email, "password": "TestPass123!"}
        )
        return success and 'user' in response

    def test_get_current_user(self):
        """Test GET /api/auth/me"""
        success, response = self.run_test(
            "Get Current User",
            "GET",
            "auth/me",
            200
        )
        return success and 'user' in response

    def test_logout(self):
        """Test POST /api/auth/logout"""
        success, response = self.run_test(
            "User Logout",
            "POST",
            "auth/logout",
            200
        )
        return success

    def test_friend_request_flow(self):
        """Test friend request flow"""
        # Create two users for friend testing with unique timestamps
        timestamp1 = datetime.now().strftime('%H%M%S%f')
        timestamp2 = datetime.now().strftime('%H%M%S%f') + "2"
        
        user1_data = {
            "username": f"friend1_{timestamp1}",
            "email": f"friend1_{timestamp1}@example.com",
            "password": "TestPass123!"
        }
        user2_data = {
            "username": f"friend2_{timestamp2}",
            "email": f"friend2_{timestamp2}@example.com",
            "password": "TestPass123!"
        }
        
        # Register user1
        success1, response1 = self.run_test(
            "Register Friend User 1",
            "POST",
            "auth/register",
            200,
            data=user1_data
        )
        if not success1:
            return False
            
        user1_id = response1['user']['id']
        user1_session = requests.Session()
        
        # Register user2 with a new session
        user2_session = requests.Session()
        success2_response = user2_session.post(
            f"{self.base_url}/api/auth/register",
            json=user2_data,
            headers={'Content-Type': 'application/json'}
        )
        
        if success2_response.status_code != 200:
            self.log(f"❌ Register Friend User 2 - Status: {success2_response.status_code}")
            return False
            
        self.log("✅ Register Friend User 2 - Status: 200")
        user2_data_response = success2_response.json()
        user2_id = user2_data_response['user']['id']
        
        # User1 sends friend request to user2
        success3, response3 = self.run_test(
            "Send Friend Request",
            "POST",
            "friends/request",
            200,
            data={"username": user2_data["username"]}
        )
        if not success3:
            return False
            
        # User2 accepts friend request from user1
        # Login as user2 with user2_session
        login_response = user2_session.post(
            f"{self.base_url}/api/auth/login",
            json={"email": user2_data["email"], "password": user2_data["password"]},
            headers={'Content-Type': 'application/json'}
        )
        
        if login_response.status_code != 200:
            self.log(f"❌ Login as User2 for Friend Accept - Status: {login_response.status_code}")
            return False
            
        self.log("✅ Login as User2 for Friend Accept - Status: 200")
        
        # Accept friend request using user2_session
        accept_response = user2_session.post(
            f"{self.base_url}/api/friends/accept/{user1_id}",
            headers={'Content-Type': 'application/json'}
        )
        
        if accept_response.status_code != 200:
            self.log(f"❌ Accept Friend Request - Status: {accept_response.status_code}")
            return False
            
        self.log("✅ Accept Friend Request - Status: 200")
        
        # Get friends list using user2_session
        friends_response = user2_session.get(
            f"{self.base_url}/api/friends",
            headers={'Content-Type': 'application/json'}
        )
        
        if friends_response.status_code != 200:
            self.log(f"❌ Get Friends List - Status: {friends_response.status_code}")
            return False
            
        self.log("✅ Get Friends List - Status: 200")
        friends_data = friends_response.json()
        
        return 'friends' in friends_data

    def test_dm_creation_and_messaging(self):
        """Test DM creation and messaging"""
        # Create two users for DM testing
        timestamp1 = datetime.now().strftime('%H%M%S%f')
        timestamp2 = datetime.now().strftime('%H%M%S%f') + "3"
        
        user1_data = {
            "username": f"dm1_{timestamp1}",
            "email": f"dm1_{timestamp1}@example.com",
            "password": "TestPass123!"
        }
        user2_data = {
            "username": f"dm2_{timestamp2}",
            "email": f"dm2_{timestamp2}@example.com",
            "password": "TestPass123!"
        }
        
        # Register users
        success1, response1 = self.run_test(
            "Register DM User 1",
            "POST",
            "auth/register",
            200,
            data=user1_data
        )
        if not success1:
            return False
            
        success2, response2 = self.run_test(
            "Register DM User 2",
            "POST",
            "auth/register", 
            200,
            data=user2_data
        )
        if not success2:
            return False
            
        user2_id = response2['user']['id']
        
        # Create DM conversation - DMCreate model requires both recipient_id and content
        success3, response3 = self.run_test(
            "Create DM Conversation",
            "POST",
            "dm/create",
            200,
            data={"recipient_id": user2_id, "content": ""}
        )
        if not success3:
            return False
            
        conversation_id = response3['id']
        
        # Send DM message
        success4, response4 = self.run_test(
            "Send DM Message",
            "POST",
            f"dm/{conversation_id}/messages",
            200,
            data={"content": "Hello from DM test!"}
        )
        if not success4:
            return False
            
        # Get DM messages
        success5, response5 = self.run_test(
            "Get DM Messages",
            "GET",
            f"dm/{conversation_id}/messages",
            200
        )
        
        return success5 and isinstance(response5, list)

    def test_dm_search(self):
        """Test DM search functionality"""
        success, response = self.run_test(
            "Search DM Messages",
            "POST",
            "dm/search",
            200,
            data={"query": "test", "limit": 10}
        )
        return success and isinstance(response, list)

    def test_server_creation_and_retrieval(self):
        """Test server creation and retrieval"""
        # Create server
        server_name = f"Test Server {datetime.now().strftime('%H%M%S')}"
        success1, response1 = self.run_test(
            "Create Server",
            "POST",
            "servers",
            200,
            data={"name": server_name, "description": "Test server description"}
        )
        if not success1:
            return False
            
        self.test_server_id = response1['id']
        self.test_invite_code = response1.get('invite_code')
        
        # Get user servers
        success2, response2 = self.run_test(
            "Get User Servers",
            "GET",
            "servers",
            200
        )
        if not success2:
            return False
            
        # Get specific server
        success3, response3 = self.run_test(
            "Get Specific Server",
            "GET",
            f"servers/{self.test_server_id}",
            200
        )
        
        return success3 and 'channels' in response3

    def test_channel_creation_and_messaging(self):
        """Test channel creation and messaging"""
        if not self.test_server_id:
            self.log("❌ No test server available for channel testing")
            return False
            
        # Create channel
        success1, response1 = self.run_test(
            "Create Channel",
            "POST",
            f"servers/{self.test_server_id}/channels",
            200,
            data={
                "name": "test-channel",
                "channel_type": "text",
                "category": "Test Channels",
                "slowmode_seconds": 0
            }
        )
        if not success1:
            return False
            
        self.test_channel_id = response1['id']
        
        # Send channel message
        success2, response2 = self.run_test(
            "Send Channel Message",
            "POST",
            f"channels/{self.test_channel_id}/messages",
            200,
            data={"content": "Hello from channel test!"}
        )
        if not success2:
            return False
            
        # Get channel messages
        success3, response3 = self.run_test(
            "Get Channel Messages",
            "GET",
            f"channels/{self.test_channel_id}/messages",
            200
        )
        
        return success3 and isinstance(response3, list)

    def test_role_management(self):
        """Test role creation and management"""
        if not self.test_server_id:
            self.log("❌ No test server available for role testing")
            return False
            
        success, response = self.run_test(
            "Create Role",
            "POST",
            f"servers/{self.test_server_id}/roles",
            200,
            data={
                "name": "Test Role",
                "color": "#FF5733",
                "permissions": 8  # Basic permissions
            }
        )
        
        return success and 'id' in response

    def test_invite_system(self):
        """Test invite creation and joining"""
        if not self.test_server_id:
            self.log("❌ No test server available for invite testing")
            return False
            
        # Create invite
        success1, response1 = self.run_test(
            "Create Server Invite",
            "POST",
            f"servers/{self.test_server_id}/invites",
            200,
            data={"max_uses": 10, "expires_hours": 24}
        )
        if not success1:
            return False
            
        invite_code = response1['code']
        
        # Create new user to test joining
        new_user_data = {
            "username": f"inviteuser_{datetime.now().strftime('%H%M%S')}",
            "email": f"invite_{datetime.now().strftime('%H%M%S')}@example.com",
            "password": "TestPass123!"
        }
        
        success2, response2 = self.run_test(
            "Register User for Invite Test",
            "POST",
            "auth/register",
            200,
            data=new_user_data
        )
        if not success2:
            return False
            
        # Join server with invite
        success3, response3 = self.run_test(
            "Join Server with Invite",
            "POST",
            f"invites/{invite_code}/join",
            200
        )
        
        return success3 and 'server' in response3

    def test_status_update(self):
        """Test user status update"""
        success, response = self.run_test(
            "Update User Status",
            "PUT",
            "users/me/status",
            200,
            data={
                "status": "busy",
                "status_message": "Testing the app",
                "status_expires_minutes": 60
            }
        )
        
        return success

    def test_admin_stats(self):
        """Test admin stats endpoint"""
        # Create a new session for admin
        admin_session = requests.Session()
        
        # Login as admin
        admin_login_response = admin_session.post(
            f"{self.base_url}/api/auth/login",
            json={"email": "admin@securecomm.local", "password": "SecureAdmin2024!"},
            headers={'Content-Type': 'application/json'}
        )
        
        if admin_login_response.status_code != 200:
            self.log(f"❌ Admin Login for Stats - Status: {admin_login_response.status_code}")
            return False
            
        self.log("✅ Admin Login for Stats - Status: 200")
        
        # Get admin stats using admin session
        stats_response = admin_session.get(
            f"{self.base_url}/api/admin/stats",
            headers={'Content-Type': 'application/json'}
        )
        
        if stats_response.status_code != 200:
            self.log(f"❌ Get Admin Stats - Status: {stats_response.status_code}")
            try:
                error_detail = stats_response.json()
                self.log(f"   Error: {error_detail}")
            except:
                self.log(f"   Response: {stats_response.text[:200]}")
            return False
            
        self.log("✅ Get Admin Stats - Status: 200")
        stats_data = stats_response.json()
        
        return 'users_registered' in stats_data

    def run_all_tests(self):
        """Run all backend API tests"""
        self.log("🚀 Starting SecureComm Backend API Tests")
        self.log(f"📡 Testing against: {self.base_url}")
        
        # Test authentication first
        if not self.test_admin_login():
            self.log("❌ Admin login failed - stopping tests")
            return False
            
        # Run all tests
        tests = [
            self.test_user_registration,
            self.test_user_login,
            self.test_get_current_user,
            self.test_logout,
            self.test_friend_request_flow,
            self.test_dm_creation_and_messaging,
            self.test_dm_search,
            self.test_server_creation_and_retrieval,
            self.test_channel_creation_and_messaging,
            self.test_role_management,
            self.test_invite_system,
            self.test_status_update,
            self.test_admin_stats
        ]
        
        for test in tests:
            try:
                test()
            except Exception as e:
                self.log(f"❌ Test {test.__name__} failed with exception: {e}")
        
        # Print results
        self.log(f"\n📊 Test Results: {self.tests_passed}/{self.tests_run} passed")
        success_rate = (self.tests_passed / self.tests_run * 100) if self.tests_run > 0 else 0
        self.log(f"📈 Success Rate: {success_rate:.1f}%")
        
        return self.tests_passed == self.tests_run

def main():
    tester = SecureCommAPITester()
    success = tester.run_all_tests()
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())