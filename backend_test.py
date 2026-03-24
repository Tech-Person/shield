#!/usr/bin/env python3
"""
Backend API Testing for Port Forwarding Manager
Tests all CRUD operations, authentication, and system endpoints
"""

import requests
import sys
import json
from datetime import datetime
from typing import Dict, Any, Optional

class PortForwardAPITester:
    def __init__(self, base_url: str = "https://funny-proskuriakova-2.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.token = None
        self.user_id = None
        self.tests_run = 0
        self.tests_passed = 0
        self.created_rules = []
        self.created_users = []

    def log(self, message: str, level: str = "INFO"):
        """Log test messages"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {level}: {message}")

    def run_test(self, name: str, method: str, endpoint: str, expected_status: int, 
                 data: Optional[Dict] = None, headers: Optional[Dict] = None) -> tuple:
        """Run a single API test"""
        url = f"{self.api_url}/{endpoint}"
        test_headers = {'Content-Type': 'application/json'}
        
        if self.token:
            test_headers['Authorization'] = f'Bearer {self.token}'
        if headers:
            test_headers.update(headers)

        self.tests_run += 1
        self.log(f"Testing {name}...")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=test_headers, timeout=30)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=test_headers, timeout=30)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=test_headers, timeout=30)
            elif method == 'DELETE':
                response = requests.delete(url, headers=test_headers, timeout=30)

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                self.log(f"✅ {name} - Status: {response.status_code}", "PASS")
            else:
                self.log(f"❌ {name} - Expected {expected_status}, got {response.status_code}", "FAIL")
                if response.text:
                    self.log(f"Response: {response.text[:200]}", "ERROR")

            try:
                response_data = response.json() if response.text else {}
            except:
                response_data = {}

            return success, response_data

        except Exception as e:
            self.log(f"❌ {name} - Error: {str(e)}", "ERROR")
            return False, {}

    def test_root_endpoint(self):
        """Test root API endpoint"""
        return self.run_test("Root API", "GET", "", 200)

    def test_login(self, username: str = "admin", password: str = "admin"):
        """Test login and get token"""
        success, response = self.run_test(
            "Admin Login",
            "POST",
            "auth/login",
            200,
            data={"username": username, "password": password}
        )
        
        if success and 'access_token' in response:
            self.token = response['access_token']
            self.user_id = response['user']['id']
            self.log(f"✅ Login successful, token acquired", "PASS")
            return True, response['user']
        return False, {}

    def test_get_current_user(self):
        """Test getting current user info"""
        return self.run_test("Get Current User", "GET", "auth/me", 200)

    def test_change_password(self):
        """Test password change functionality"""
        # First change password
        success, _ = self.run_test(
            "Change Password",
            "POST",
            "auth/change-password",
            200,
            data={"current_password": "admin", "new_password": "newpassword123"}
        )
        
        if not success:
            return False
        
        # Test login with new password
        old_token = self.token
        self.token = None
        login_success, _ = self.test_login("admin", "newpassword123")
        
        if login_success:
            # Change back to original password
            self.run_test(
                "Revert Password",
                "POST", 
                "auth/change-password",
                200,
                data={"current_password": "newpassword123", "new_password": "admin"}
            )
            return True
        else:
            self.token = old_token
            return False

    def test_system_status(self):
        """Test system status endpoint"""
        return self.run_test("System Status", "GET", "system/status", 200)

    def test_system_stats(self):
        """Test system stats endpoint"""
        return self.run_test("System Stats", "GET", "system/stats", 200)

    def test_create_port_rule(self):
        """Test creating a port forwarding rule"""
        rule_data = {
            "name": f"Test Rule {datetime.now().strftime('%H%M%S')}",
            "external_port": 60001,
            "internal_port": 8080,
            "protocol": "both",
            "description": "Test rule for API testing"
        }
        
        success, response = self.run_test(
            "Create Port Rule",
            "POST",
            "rules",
            200,
            data=rule_data
        )
        
        if success and 'id' in response:
            self.created_rules.append(response['id'])
            return True, response
        return False, {}

    def test_list_port_rules(self):
        """Test listing all port rules"""
        return self.run_test("List Port Rules", "GET", "rules", 200)

    def test_get_port_rule(self, rule_id: str):
        """Test getting a specific port rule"""
        return self.run_test(f"Get Port Rule {rule_id[:8]}", "GET", f"rules/{rule_id}", 200)

    def test_update_port_rule(self, rule_id: str):
        """Test updating a port rule"""
        update_data = {
            "name": "Updated Test Rule",
            "description": "Updated description"
        }
        
        return self.run_test(
            f"Update Port Rule {rule_id[:8]}",
            "PUT",
            f"rules/{rule_id}",
            200,
            data=update_data
        )

    def test_toggle_port_rule(self, rule_id: str):
        """Test toggling a port rule on/off"""
        return self.run_test(
            f"Toggle Port Rule {rule_id[:8]}",
            "POST",
            f"rules/{rule_id}/toggle",
            200
        )

    def test_delete_port_rule(self, rule_id: str):
        """Test deleting a port rule"""
        success, _ = self.run_test(
            f"Delete Port Rule {rule_id[:8]}",
            "DELETE",
            f"rules/{rule_id}",
            200
        )
        
        if success and rule_id in self.created_rules:
            self.created_rules.remove(rule_id)
        
        return success

    def test_create_user(self):
        """Test creating a new user (admin only)"""
        user_data = {
            "username": f"testuser_{datetime.now().strftime('%H%M%S')}",
            "password": "testpass123",
            "role": "user"
        }
        
        success, response = self.run_test(
            "Create User",
            "POST",
            "users",
            200,
            data=user_data
        )
        
        if success and 'id' in response:
            self.created_users.append(response['id'])
            return True, response
        return False, {}

    def test_list_users(self):
        """Test listing all users (admin only)"""
        return self.run_test("List Users", "GET", "users", 200)

    def test_delete_user(self, user_id: str):
        """Test deleting a user (admin only)"""
        success, _ = self.run_test(
            f"Delete User {user_id[:8]}",
            "DELETE",
            f"users/{user_id}",
            200
        )
        
        if success and user_id in self.created_users:
            self.created_users.remove(user_id)
        
        return success

    def test_port_conflict(self):
        """Test port conflict detection"""
        # Create first rule
        rule_data = {
            "name": "Conflict Test Rule 1",
            "external_port": 60002,
            "internal_port": 8081,
            "protocol": "tcp"
        }
        
        success1, response1 = self.run_test(
            "Create Rule for Conflict Test",
            "POST",
            "rules",
            200,
            data=rule_data
        )
        
        if success1:
            self.created_rules.append(response1['id'])
            
            # Try to create another rule with same external port
            rule_data2 = {
                "name": "Conflict Test Rule 2",
                "external_port": 60002,  # Same port
                "internal_port": 8082,
                "protocol": "udp"
            }
            
            success2, _ = self.run_test(
                "Test Port Conflict Detection",
                "POST",
                "rules",
                400,  # Should fail with 400
                data=rule_data2
            )
            
            return success2  # Success means it properly detected conflict
        
        return False

    def test_outside_safe_range_warning(self):
        """Test warning for ports outside safe range"""
        rule_data = {
            "name": "Outside Range Test",
            "external_port": 8080,  # Outside 60000-61000 range
            "internal_port": 8080,
            "protocol": "tcp"
        }
        
        success, response = self.run_test(
            "Create Rule Outside Safe Range",
            "POST",
            "rules",
            200,
            data=rule_data
        )
        
        if success and response.get('is_outside_safe_range'):
            self.created_rules.append(response['id'])
            self.log("✅ Outside safe range flag correctly set", "PASS")
            return True
        
        return False

    def cleanup(self):
        """Clean up created test data"""
        self.log("Cleaning up test data...")
        
        # Delete created rules
        for rule_id in self.created_rules[:]:
            self.test_delete_port_rule(rule_id)
        
        # Delete created users
        for user_id in self.created_users[:]:
            self.test_delete_user(user_id)

    def run_all_tests(self):
        """Run all API tests"""
        self.log("Starting Port Forwarding Manager API Tests")
        self.log(f"Testing against: {self.base_url}")
        
        # Basic connectivity
        if not self.test_root_endpoint()[0]:
            self.log("❌ Root endpoint failed, stopping tests", "CRITICAL")
            return False
        
        # Authentication tests
        login_success, user_data = self.test_login()
        if not login_success:
            self.log("❌ Login failed, stopping tests", "CRITICAL")
            return False
        
        self.log(f"Logged in as: {user_data.get('username')} ({user_data.get('role')})")
        
        # User info tests
        self.test_get_current_user()
        
        # System tests
        self.test_system_status()
        self.test_system_stats()
        
        # Port rule CRUD tests
        rule_success, rule_data = self.test_create_port_rule()
        if rule_success:
            rule_id = rule_data['id']
            self.test_get_port_rule(rule_id)
            self.test_update_port_rule(rule_id)
            self.test_toggle_port_rule(rule_id)
            # Don't delete yet, we'll use it for listing
        
        self.test_list_port_rules()
        
        # Advanced rule tests
        self.test_port_conflict()
        self.test_outside_safe_range_warning()
        
        # User management tests (admin only)
        if user_data.get('role') == 'admin':
            user_success, created_user = self.test_create_user()
            self.test_list_users()
            # Don't delete user yet
        
        # Password change test
        self.test_change_password()
        
        # Cleanup
        self.cleanup()
        
        # Print results
        self.log(f"\n📊 Test Results: {self.tests_passed}/{self.tests_run} passed")
        success_rate = (self.tests_passed / self.tests_run) * 100 if self.tests_run > 0 else 0
        self.log(f"Success Rate: {success_rate:.1f}%")
        
        return self.tests_passed == self.tests_run

def main():
    """Main test runner"""
    tester = PortForwardAPITester()
    
    try:
        success = tester.run_all_tests()
        return 0 if success else 1
    except KeyboardInterrupt:
        print("\n⚠️ Tests interrupted by user")
        return 1
    except Exception as e:
        print(f"\n❌ Test runner error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())