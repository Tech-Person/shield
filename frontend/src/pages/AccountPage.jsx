import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { toast } from 'sonner';
import { useAuth } from '../context/AuthContext';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { 
  Dialog, 
  DialogContent, 
  DialogHeader, 
  DialogTitle, 
  DialogDescription,
  DialogFooter 
} from '../components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/select';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../components/ui/table';
import { 
  Network, 
  ArrowLeft, 
  User, 
  Shield, 
  Key,
  Plus,
  Trash2,
  Users,
  Settings,
  Save
} from 'lucide-react';
import ChangePasswordDialog from '../components/ChangePasswordDialog';

// Use relative URL if REACT_APP_BACKEND_URL is not set (for self-hosted deployments)
const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || '';
const API = `${BACKEND_URL}/api`;

export default function AccountPage() {
  const navigate = useNavigate();
  const { user, isAdmin, getAuthHeaders, logout } = useAuth();
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showPasswordDialog, setShowPasswordDialog] = useState(false);
  const [showAddUserDialog, setShowAddUserDialog] = useState(false);
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [selectedUser, setSelectedUser] = useState(null);
  const [newUserData, setNewUserData] = useState({
    username: '',
    password: '',
    role: 'user'
  });
  const [portRangeSettings, setPortRangeSettings] = useState({
    safe_port_min: 60000,
    safe_port_max: 61000
  });
  const [isSavingPortRange, setIsSavingPortRange] = useState(false);

  const fetchUsers = useCallback(async () => {
    if (!isAdmin) {
      setLoading(false);
      return;
    }
    
    try {
      const response = await axios.get(`${API}/users`, {
        headers: getAuthHeaders()
      });
      setUsers(response.data);
    } catch (error) {
      toast.error('Failed to fetch users');
    } finally {
      setLoading(false);
    }
  }, [isAdmin, getAuthHeaders]);

  const fetchPortRangeSettings = useCallback(async () => {
    try {
      const response = await axios.get(`${API}/settings/port-range`, {
        headers: getAuthHeaders()
      });
      setPortRangeSettings(response.data);
    } catch (error) {
      console.error('Failed to fetch port range settings');
    }
  }, [getAuthHeaders]);

  useEffect(() => {
    fetchUsers();
    fetchPortRangeSettings();
  }, [fetchUsers, fetchPortRangeSettings]);

  const handleSavePortRange = async () => {
    if (portRangeSettings.safe_port_min >= portRangeSettings.safe_port_max) {
      toast.error('Minimum port must be less than maximum port');
      return;
    }
    
    setIsSavingPortRange(true);
    try {
      await axios.put(`${API}/settings/port-range`, portRangeSettings, {
        headers: getAuthHeaders()
      });
      toast.success('Port range settings saved');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to save port range settings');
    } finally {
      setIsSavingPortRange(false);
    }
  };

  const handleAddUser = async (e) => {
    e.preventDefault();
    
    if (!newUserData.username || !newUserData.password) {
      toast.error('Please fill all required fields');
      return;
    }

    try {
      await axios.post(`${API}/users`, newUserData, {
        headers: getAuthHeaders()
      });
      toast.success('User created successfully');
      setShowAddUserDialog(false);
      setNewUserData({ username: '', password: '', role: 'user' });
      fetchUsers();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to create user');
    }
  };

  const handleDeleteUser = async () => {
    try {
      await axios.delete(`${API}/users/${selectedUser.id}`, {
        headers: getAuthHeaders()
      });
      toast.success('User deleted successfully');
      setShowDeleteDialog(false);
      setSelectedUser(null);
      fetchUsers();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to delete user');
    }
  };

  const formatDate = (dateString) => {
    if (!dateString) return 'Never';
    return new Date(dateString).toLocaleString();
  };

  return (
    <div className="min-h-screen bg-background grid-pattern" data-testid="account-page">
      {/* Header */}
      <header className="border-b border-border bg-card/80 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-3">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => navigate('/dashboard')}
                className="text-muted-foreground hover:text-white"
                data-testid="back-to-dashboard-button"
              >
                <ArrowLeft className="w-4 h-4 mr-2" />
                Dashboard
              </Button>
            </div>
            <div className="flex items-center gap-2">
              <Network className="w-5 h-5 text-blue-400" />
              <span className="font-semibold text-white">Account Settings</span>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* User Info Card */}
        <div className="card-tech p-6 mb-8">
          <div className="flex items-center gap-4 mb-6">
            <div className="w-12 h-12 rounded-sm bg-blue-600/20 border border-blue-500/30 flex items-center justify-center">
              <User className="w-6 h-6 text-blue-400" />
            </div>
            <div>
              <h2 className="text-xl font-semibold text-white">{user?.username}</h2>
              <div className="flex items-center gap-2 mt-1">
                <span className={`px-2 py-0.5 text-xs font-mono rounded-sm ${
                  user?.role === 'admin' 
                    ? 'bg-blue-600/20 text-blue-400 border border-blue-500/30' 
                    : 'bg-zinc-700 text-zinc-300'
                }`}>
                  {user?.role?.toUpperCase()}
                </span>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4 mb-6">
            <div>
              <p className="text-xs text-muted-foreground font-mono uppercase tracking-wide">Account Created</p>
              <p className="text-sm text-white mt-1">{formatDate(user?.created_at)}</p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground font-mono uppercase tracking-wide">Last Login</p>
              <p className="text-sm text-white mt-1">{formatDate(user?.last_login)}</p>
            </div>
          </div>

          <div className="flex items-center gap-4 pt-4 border-t border-border">
            <Button
              onClick={() => setShowPasswordDialog(true)}
              className="bg-zinc-800 hover:bg-zinc-700 border border-zinc-700"
              data-testid="change-password-button"
            >
              <Key className="w-4 h-4 mr-2" />
              Change Password
            </Button>
            <Button
              variant="outline"
              onClick={() => {
                logout();
                navigate('/login');
              }}
              className="border-zinc-700 text-red-400 hover:text-red-300 hover:bg-red-500/10"
              data-testid="logout-account-button"
            >
              Logout
            </Button>
          </div>
        </div>

        {/* Port Range Settings (Admin Only) */}
        {isAdmin && (
          <div className="card-tech p-6 mb-8">
            <div className="flex items-center gap-2 mb-6">
              <Settings className="w-5 h-5 text-blue-400" />
              <h2 className="font-semibold text-white">Port Range Settings</h2>
            </div>
            
            <p className="text-sm text-muted-foreground mb-4">
              Define the safe port range for forwarding rules. Ports outside this range will show a warning.
            </p>
            
            <div className="flex flex-wrap items-end gap-4">
              <div className="space-y-2">
                <Label className="text-muted-foreground text-xs">Minimum Port</Label>
                <Input
                  type="number"
                  value={portRangeSettings.safe_port_min}
                  onChange={(e) => setPortRangeSettings(prev => ({ ...prev, safe_port_min: parseInt(e.target.value) || 0 }))}
                  className="w-32 bg-zinc-900 border-zinc-700 text-white font-mono"
                  min="1"
                  max="65534"
                  data-testid="port-range-min-input"
                />
              </div>
              
              <span className="text-muted-foreground pb-2">to</span>
              
              <div className="space-y-2">
                <Label className="text-muted-foreground text-xs">Maximum Port</Label>
                <Input
                  type="number"
                  value={portRangeSettings.safe_port_max}
                  onChange={(e) => setPortRangeSettings(prev => ({ ...prev, safe_port_max: parseInt(e.target.value) || 0 }))}
                  className="w-32 bg-zinc-900 border-zinc-700 text-white font-mono"
                  min="2"
                  max="65535"
                  data-testid="port-range-max-input"
                />
              </div>
              
              <Button
                onClick={handleSavePortRange}
                disabled={isSavingPortRange}
                className="bg-blue-600 hover:bg-blue-700 text-white"
                data-testid="save-port-range-button"
              >
                <Save className="w-4 h-4 mr-2" />
                {isSavingPortRange ? 'Saving...' : 'Save'}
              </Button>
            </div>
          </div>
        )}

        {/* User Management (Admin Only) */}
        {isAdmin && (
          <div className="card-tech">
            <div className="flex items-center justify-between p-4 border-b border-border">
              <div className="flex items-center gap-2">
                <Users className="w-5 h-5 text-blue-400" />
                <h2 className="font-semibold text-white">User Management</h2>
              </div>
              <Button
                onClick={() => setShowAddUserDialog(true)}
                className="bg-blue-600 hover:bg-blue-700 text-white"
                data-testid="add-user-button"
              >
                <Plus className="w-4 h-4 mr-2" />
                Add User
              </Button>
            </div>
            
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow className="border-border hover:bg-transparent">
                    <TableHead className="text-muted-foreground font-mono text-xs">USERNAME</TableHead>
                    <TableHead className="text-muted-foreground font-mono text-xs">ROLE</TableHead>
                    <TableHead className="text-muted-foreground font-mono text-xs">CREATED</TableHead>
                    <TableHead className="text-muted-foreground font-mono text-xs">LAST LOGIN</TableHead>
                    <TableHead className="text-muted-foreground font-mono text-xs text-right">ACTIONS</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {loading ? (
                    <TableRow>
                      <TableCell colSpan={5} className="text-center py-8 text-muted-foreground">
                        Loading...
                      </TableCell>
                    </TableRow>
                  ) : users.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={5} className="text-center py-8 text-muted-foreground">
                        No users found
                      </TableCell>
                    </TableRow>
                  ) : (
                    users.map((u) => (
                      <TableRow key={u.id} className="border-border table-row-hover" data-testid={`user-row-${u.id}`}>
                        <TableCell className="font-medium text-white">
                          <div className="flex items-center gap-2">
                            {u.username}
                            {u.id === user.id && (
                              <span className="text-xs text-muted-foreground">(you)</span>
                            )}
                          </div>
                        </TableCell>
                        <TableCell>
                          <span className={`px-2 py-0.5 text-xs font-mono rounded-sm ${
                            u.role === 'admin' 
                              ? 'bg-blue-600/20 text-blue-400 border border-blue-500/30' 
                              : 'bg-zinc-700 text-zinc-300'
                          }`}>
                            {u.role.toUpperCase()}
                          </span>
                        </TableCell>
                        <TableCell className="text-muted-foreground text-sm">
                          {formatDate(u.created_at)}
                        </TableCell>
                        <TableCell className="text-muted-foreground text-sm">
                          {formatDate(u.last_login)}
                        </TableCell>
                        <TableCell className="text-right">
                          {u.id !== user.id && (
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => {
                                setSelectedUser(u);
                                setShowDeleteDialog(true);
                              }}
                              className="text-muted-foreground hover:text-red-400"
                              data-testid={`delete-user-${u.id}`}
                            >
                              <Trash2 className="w-4 h-4" />
                            </Button>
                          )}
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </div>
          </div>
        )}

        {/* Non-admin notice */}
        {!isAdmin && (
          <div className="card-tech p-6">
            <div className="flex items-center gap-3 text-muted-foreground">
              <Shield className="w-5 h-5" />
              <p>User management is only available to administrators.</p>
            </div>
          </div>
        )}
      </main>

      {/* Change Password Dialog */}
      <ChangePasswordDialog 
        open={showPasswordDialog} 
        onOpenChange={setShowPasswordDialog}
        forced={false}
      />

      {/* Add User Dialog */}
      <Dialog open={showAddUserDialog} onOpenChange={setShowAddUserDialog}>
        <DialogContent className="bg-card border-border sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="text-white">Add New User</DialogTitle>
            <DialogDescription className="text-muted-foreground">
              Create a new user account.
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={handleAddUser} className="space-y-4">
            <div className="space-y-2">
              <Label className="text-muted-foreground">Username *</Label>
              <Input
                value={newUserData.username}
                onChange={(e) => setNewUserData({ ...newUserData, username: e.target.value })}
                className="bg-zinc-900 border-zinc-700 text-white"
                placeholder="Enter username"
                data-testid="new-user-username-input"
              />
            </div>
            
            <div className="space-y-2">
              <Label className="text-muted-foreground">Password *</Label>
              <Input
                type="password"
                value={newUserData.password}
                onChange={(e) => setNewUserData({ ...newUserData, password: e.target.value })}
                className="bg-zinc-900 border-zinc-700 text-white"
                placeholder="Enter password"
                data-testid="new-user-password-input"
              />
            </div>
            
            <div className="space-y-2">
              <Label className="text-muted-foreground">Role</Label>
              <Select
                value={newUserData.role}
                onValueChange={(value) => setNewUserData({ ...newUserData, role: value })}
              >
                <SelectTrigger className="bg-zinc-900 border-zinc-700 text-white" data-testid="new-user-role-select">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="bg-zinc-900 border-zinc-700">
                  <SelectItem value="user">User</SelectItem>
                  <SelectItem value="admin">Admin</SelectItem>
                </SelectContent>
              </Select>
            </div>
            
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setShowAddUserDialog(false)} className="border-zinc-700 text-muted-foreground hover:text-white">
                Cancel
              </Button>
              <Button type="submit" className="bg-blue-600 hover:bg-blue-700" data-testid="add-user-submit-button">
                Create User
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Delete User Confirmation Dialog */}
      <Dialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
        <DialogContent className="bg-card border-border sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="text-white">Delete User</DialogTitle>
            <DialogDescription className="text-muted-foreground">
              Are you sure you want to delete user "{selectedUser?.username}"? This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setShowDeleteDialog(false)} className="border-zinc-700 text-muted-foreground hover:text-white">
              Cancel
            </Button>
            <Button onClick={handleDeleteUser} className="bg-red-600 hover:bg-red-700" data-testid="confirm-delete-user-button">
              Delete User
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
