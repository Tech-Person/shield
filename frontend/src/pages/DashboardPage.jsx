import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { toast } from 'sonner';
import { useAuth } from '../context/AuthContext';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Switch } from '../components/ui/switch';
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
  Plus, 
  Settings, 
  LogOut, 
  Activity, 
  Server, 
  Shield,
  AlertTriangle,
  Trash2,
  Edit,
  User,
  Wifi,
  WifiOff,
  Clock,
  RefreshCw
} from 'lucide-react';
import ChangePasswordDialog from '../components/ChangePasswordDialog';

// Use relative URL if REACT_APP_BACKEND_URL is not set (for self-hosted deployments)
const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || '';
const API = `${BACKEND_URL}/api`;

export default function DashboardPage() {
  const navigate = useNavigate();
  const { user, logout, getAuthHeaders } = useAuth();
  const [rules, setRules] = useState([]);
  const [stats, setStats] = useState({ total_rules: 0, active_rules: 0, inactive_rules: 0, total_users: 0 });
  const [systemStatus, setSystemStatus] = useState(null);
  const [wireguardStatus, setWireguardStatus] = useState(null);
  const [portRangeSettings, setPortRangeSettings] = useState({ safe_port_min: 60000, safe_port_max: 61000 });
  const [loading, setLoading] = useState(true);
  const [isAddDialogOpen, setIsAddDialogOpen] = useState(false);
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [showPasswordDialog, setShowPasswordDialog] = useState(false);
  const [selectedRule, setSelectedRule] = useState(null);
  const [formData, setFormData] = useState({
    name: '',
    external_port: '',
    internal_port: '',
    protocol: 'both',
    description: ''
  });

  const fetchData = useCallback(async () => {
    try {
      const headers = getAuthHeaders();
      const [rulesRes, statsRes, statusRes, portRangeRes] = await Promise.all([
        axios.get(`${API}/rules`, { headers }),
        axios.get(`${API}/system/stats`, { headers }),
        axios.get(`${API}/system/status`, { headers }),
        axios.get(`${API}/settings/port-range`, { headers })
      ]);
      setRules(rulesRes.data);
      setStats(statsRes.data);
      setSystemStatus(statusRes.data);
      setPortRangeSettings(portRangeRes.data);
    } catch (error) {
      toast.error('Failed to fetch data');
    } finally {
      setLoading(false);
    }
  }, [getAuthHeaders]);

  const fetchWireguardStatus = useCallback(async () => {
    try {
      const headers = getAuthHeaders();
      const response = await axios.get(`${API}/system/wireguard`, { headers });
      setWireguardStatus(response.data);
    } catch (error) {
      console.error('Failed to fetch WireGuard status');
    }
  }, [getAuthHeaders]);

  useEffect(() => {
    fetchData();
    fetchWireguardStatus();
  }, [fetchData, fetchWireguardStatus]);

  // Poll WireGuard status every 10 seconds
  useEffect(() => {
    const interval = setInterval(fetchWireguardStatus, 10000);
    return () => clearInterval(interval);
  }, [fetchWireguardStatus]);

  useEffect(() => {
    // Check if user must change password
    if (user?.must_change_password) {
      setShowPasswordDialog(true);
    }
  }, [user]);

  const handleToggleRule = async (ruleId) => {
    try {
      const response = await axios.post(`${API}/rules/${ruleId}/toggle`, {}, {
        headers: getAuthHeaders()
      });
      toast.success(response.data.message);
      fetchData();
    } catch (error) {
      toast.error('Failed to toggle rule');
    }
  };

  const handleAddRule = async (e) => {
    e.preventDefault();
    
    if (!formData.name || !formData.external_port || !formData.internal_port) {
      toast.error('Please fill all required fields');
      return;
    }

    try {
      await axios.post(`${API}/rules`, {
        ...formData,
        external_port: parseInt(formData.external_port),
        internal_port: parseInt(formData.internal_port)
      }, {
        headers: getAuthHeaders()
      });
      toast.success('Rule added successfully');
      setIsAddDialogOpen(false);
      resetForm();
      fetchData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to add rule');
    }
  };

  const handleEditRule = async (e) => {
    e.preventDefault();
    
    try {
      await axios.put(`${API}/rules/${selectedRule.id}`, {
        ...formData,
        external_port: parseInt(formData.external_port),
        internal_port: parseInt(formData.internal_port)
      }, {
        headers: getAuthHeaders()
      });
      toast.success('Rule updated successfully');
      setIsEditDialogOpen(false);
      resetForm();
      fetchData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to update rule');
    }
  };

  const handleDeleteRule = async () => {
    try {
      await axios.delete(`${API}/rules/${selectedRule.id}`, {
        headers: getAuthHeaders()
      });
      toast.success('Rule deleted successfully');
      setIsDeleteDialogOpen(false);
      setSelectedRule(null);
      fetchData();
    } catch (error) {
      toast.error('Failed to delete rule');
    }
  };

  const openEditDialog = (rule) => {
    setSelectedRule(rule);
    setFormData({
      name: rule.name,
      external_port: rule.external_port.toString(),
      internal_port: rule.internal_port.toString(),
      protocol: rule.protocol,
      description: rule.description
    });
    setIsEditDialogOpen(true);
  };

  const openDeleteDialog = (rule) => {
    setSelectedRule(rule);
    setIsDeleteDialogOpen(true);
  };

  const resetForm = () => {
    setFormData({
      name: '',
      external_port: '',
      internal_port: '',
      protocol: 'both',
      description: ''
    });
    setSelectedRule(null);
  };

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const isOutsideRange = (port) => {
    const p = parseInt(port);
    return p < portRangeSettings.safe_port_min || p > portRangeSettings.safe_port_max;
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="text-muted-foreground font-mono">Loading...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background grid-pattern" data-testid="dashboard-page">
      {/* Header */}
      <header className="border-b border-border bg-card/80 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-sm bg-blue-600/20 border border-blue-500/30 flex items-center justify-center">
                <Network className="w-4 h-4 text-blue-400" />
              </div>
              <span className="font-semibold text-white">Port Forward Manager</span>
              {systemStatus?.simulation_mode && (
                <span className="px-2 py-0.5 text-xs font-mono bg-amber-500/20 text-amber-400 border border-amber-500/30 rounded-sm">
                  SIMULATION
                </span>
              )}
            </div>
            
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <User className="w-4 h-4" />
                <span className="font-mono">{user?.username}</span>
                {user?.role === 'admin' && (
                  <span className="px-1.5 py-0.5 text-xs bg-blue-600/20 text-blue-400 border border-blue-500/30 rounded-sm">
                    ADMIN
                  </span>
                )}
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => navigate('/account')}
                className="text-muted-foreground hover:text-white"
                data-testid="account-nav-button"
              >
                <Settings className="w-4 h-4" />
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={handleLogout}
                className="text-muted-foreground hover:text-white"
                data-testid="logout-button"
              >
                <LogOut className="w-4 h-4" />
              </Button>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
          <div className="card-tech p-4 card-hover">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs text-muted-foreground font-mono uppercase tracking-wide">Total Rules</p>
                <p className="text-2xl font-semibold text-white mt-1">{stats.total_rules}</p>
              </div>
              <div className="w-10 h-10 rounded-sm bg-blue-600/20 flex items-center justify-center">
                <Server className="w-5 h-5 text-blue-400" />
              </div>
            </div>
          </div>
          
          <div className="card-tech p-4 card-hover">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs text-muted-foreground font-mono uppercase tracking-wide">Active Rules</p>
                <p className="text-2xl font-semibold text-emerald-400 mt-1">{stats.active_rules}</p>
              </div>
              <div className="w-10 h-10 rounded-sm bg-emerald-600/20 flex items-center justify-center">
                <Activity className="w-5 h-5 text-emerald-400" />
              </div>
            </div>
          </div>
          
          <div className="card-tech p-4 card-hover">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs text-muted-foreground font-mono uppercase tracking-wide">Inactive Rules</p>
                <p className="text-2xl font-semibold text-red-400 mt-1">{stats.inactive_rules}</p>
              </div>
              <div className="w-10 h-10 rounded-sm bg-red-600/20 flex items-center justify-center">
                <Shield className="w-5 h-5 text-red-400" />
              </div>
            </div>
          </div>
          
          <div className="card-tech p-4 card-hover">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs text-muted-foreground font-mono uppercase tracking-wide">Users</p>
                <p className="text-2xl font-semibold text-white mt-1">{stats.total_users}</p>
              </div>
              <div className="w-10 h-10 rounded-sm bg-cyan-600/20 flex items-center justify-center">
                <User className="w-5 h-5 text-cyan-400" />
              </div>
            </div>
          </div>
        </div>

        {/* System Info with WireGuard Status */}
        <div className="card-tech p-4 mb-8">
          <div className="flex flex-wrap items-center justify-between gap-4">
            {/* Left side - System Info */}
            <div className="flex flex-wrap items-center gap-6 text-sm">
              {systemStatus && (
                <>
                  <div className="flex items-center gap-2">
                    <span className="text-muted-foreground">WireGuard Interface:</span>
                    <span className="font-mono text-cyan-400">{systemStatus.wireguard_interface}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-muted-foreground">Destination IP:</span>
                    <span className="font-mono text-cyan-400">{systemStatus.destination_ip}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-muted-foreground">Safe Port Range:</span>
                    <span className="font-mono text-emerald-400">{portRangeSettings.safe_port_min}-{portRangeSettings.safe_port_max}</span>
                  </div>
                </>
              )}
            </div>
            
            {/* Right side - WireGuard Status */}
            {wireguardStatus && (
              <div className="flex items-center gap-4 px-4 py-2 rounded-sm bg-zinc-900/50 border border-zinc-800">
                <div className="flex items-center gap-2">
                  {wireguardStatus.status === 'up' ? (
                    <Wifi className="w-4 h-4 text-emerald-400" />
                  ) : wireguardStatus.status === 'waiting' ? (
                    <Wifi className="w-4 h-4 text-amber-400" />
                  ) : (
                    <WifiOff className="w-4 h-4 text-red-400" />
                  )}
                  <span className={`text-sm font-medium ${
                    wireguardStatus.status === 'up' ? 'text-emerald-400' : 
                    wireguardStatus.status === 'waiting' ? 'text-amber-400' : 'text-red-400'
                  }`}>
                    WG: {wireguardStatus.status.toUpperCase()}
                  </span>
                </div>
                
                {wireguardStatus.last_handshake && (
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <Clock className="w-3 h-3" />
                    <span className="font-mono text-xs">{wireguardStatus.last_handshake}</span>
                  </div>
                )}
                
                <button 
                  onClick={fetchWireguardStatus}
                  className="p-1 rounded hover:bg-zinc-800 transition-colors"
                  title="Refresh status"
                >
                  <RefreshCw className="w-3 h-3 text-muted-foreground hover:text-white" />
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Rules Table */}
        <div className="card-tech">
          <div className="flex items-center justify-between p-4 border-b border-border">
            <div className="flex items-center gap-2">
              <Server className="w-5 h-5 text-blue-400" />
              <h2 className="font-semibold text-white">Port Forwarding Rules</h2>
            </div>
            <Button
              onClick={() => {
                resetForm();
                setIsAddDialogOpen(true);
              }}
              className="bg-blue-600 hover:bg-blue-700 text-white"
              data-testid="add-rule-button"
            >
              <Plus className="w-4 h-4 mr-2" />
              Add Rule
            </Button>
          </div>
          
          <div className="overflow-x-auto">
            <Table className="port-table">
              <TableHeader>
                <TableRow className="border-border hover:bg-transparent">
                  <TableHead className="text-muted-foreground font-mono text-xs">STATUS</TableHead>
                  <TableHead className="text-muted-foreground font-mono text-xs">NAME</TableHead>
                  <TableHead className="text-muted-foreground font-mono text-xs">EXT PORT</TableHead>
                  <TableHead className="text-muted-foreground font-mono text-xs">INT PORT</TableHead>
                  <TableHead className="text-muted-foreground font-mono text-xs">PROTOCOL</TableHead>
                  <TableHead className="text-muted-foreground font-mono text-xs">DESCRIPTION</TableHead>
                  <TableHead className="text-muted-foreground font-mono text-xs">CREATED BY</TableHead>
                  <TableHead className="text-muted-foreground font-mono text-xs text-right">ACTIONS</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rules.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={8} className="text-center py-12 text-muted-foreground">
                      No port forwarding rules configured
                    </TableCell>
                  </TableRow>
                ) : (
                  rules.map((rule) => (
                    <TableRow key={rule.id} className="border-border table-row-hover" data-testid={`rule-row-${rule.id}`}>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <Switch
                            checked={rule.enabled}
                            onCheckedChange={() => handleToggleRule(rule.id)}
                            className="data-[state=checked]:bg-emerald-500"
                            data-testid={`toggle-rule-${rule.id}`}
                          />
                          <span className={`status-dot ${rule.enabled ? 'status-dot-active' : 'status-dot-inactive'}`} />
                        </div>
                      </TableCell>
                      <TableCell className="font-medium text-white">{rule.name}</TableCell>
                      <TableCell className="font-mono text-cyan-400">
                        <div className="flex items-center gap-2">
                          {rule.external_port}
                          {rule.is_outside_safe_range && (
                            <AlertTriangle className="w-4 h-4 text-amber-400" title="Port outside safe range (60000-61000)" />
                          )}
                        </div>
                      </TableCell>
                      <TableCell className="font-mono text-cyan-400">{rule.internal_port}</TableCell>
                      <TableCell>
                        <span className="px-2 py-0.5 text-xs font-mono bg-zinc-800 text-zinc-300 rounded-sm uppercase">
                          {rule.protocol}
                        </span>
                      </TableCell>
                      <TableCell className="text-muted-foreground max-w-xs truncate">{rule.description || '-'}</TableCell>
                      <TableCell className="text-muted-foreground font-mono text-xs">{rule.created_by}</TableCell>
                      <TableCell className="text-right">
                        <div className="flex items-center justify-end gap-2">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => openEditDialog(rule)}
                            className="text-muted-foreground hover:text-white"
                            data-testid={`edit-rule-${rule.id}`}
                          >
                            <Edit className="w-4 h-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => openDeleteDialog(rule)}
                            className="text-muted-foreground hover:text-red-400"
                            data-testid={`delete-rule-${rule.id}`}
                          >
                            <Trash2 className="w-4 h-4" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>
        </div>
      </main>

      {/* Add Rule Dialog */}
      <Dialog open={isAddDialogOpen} onOpenChange={setIsAddDialogOpen}>
        <DialogContent className="bg-card border-border sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="text-white">Add Port Forwarding Rule</DialogTitle>
            <DialogDescription className="text-muted-foreground">
              Configure a new port forwarding rule for the WireGuard tunnel.
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={handleAddRule} className="space-y-4">
            <div className="space-y-2">
              <Label className="text-muted-foreground">Rule Name *</Label>
              <Input
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                className="bg-zinc-900 border-zinc-700 text-white"
                placeholder="e.g., Terraria Server"
                data-testid="rule-name-input"
              />
            </div>
            
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label className="text-muted-foreground">External Port *</Label>
                <Input
                  type="number"
                  value={formData.external_port}
                  onChange={(e) => setFormData({ ...formData, external_port: e.target.value })}
                  className="bg-zinc-900 border-zinc-700 text-white font-mono"
                  placeholder="60001"
                  data-testid="rule-external-port-input"
                />
                {formData.external_port && isOutsideRange(formData.external_port) && (
                  <p className="text-xs text-amber-400 flex items-center gap-1">
                    <AlertTriangle className="w-3 h-3" />
                    Outside safe range (60000-61000)
                  </p>
                )}
              </div>
              <div className="space-y-2">
                <Label className="text-muted-foreground">Internal Port *</Label>
                <Input
                  type="number"
                  value={formData.internal_port}
                  onChange={(e) => setFormData({ ...formData, internal_port: e.target.value })}
                  className="bg-zinc-900 border-zinc-700 text-white font-mono"
                  placeholder="7777"
                  data-testid="rule-internal-port-input"
                />
              </div>
            </div>
            
            <div className="space-y-2">
              <Label className="text-muted-foreground">Protocol</Label>
              <Select
                value={formData.protocol}
                onValueChange={(value) => setFormData({ ...formData, protocol: value })}
              >
                <SelectTrigger className="bg-zinc-900 border-zinc-700 text-white" data-testid="rule-protocol-select">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="bg-zinc-900 border-zinc-700">
                  <SelectItem value="both">TCP & UDP</SelectItem>
                  <SelectItem value="tcp">TCP Only</SelectItem>
                  <SelectItem value="udp">UDP Only</SelectItem>
                </SelectContent>
              </Select>
            </div>
            
            <div className="space-y-2">
              <Label className="text-muted-foreground">Description</Label>
              <Input
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                className="bg-zinc-900 border-zinc-700 text-white"
                placeholder="Optional description"
                data-testid="rule-description-input"
              />
            </div>
            
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setIsAddDialogOpen(false)} className="border-zinc-700 text-muted-foreground hover:text-white">
                Cancel
              </Button>
              <Button type="submit" className="bg-blue-600 hover:bg-blue-700" data-testid="add-rule-submit-button">
                Add Rule
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Edit Rule Dialog */}
      <Dialog open={isEditDialogOpen} onOpenChange={setIsEditDialogOpen}>
        <DialogContent className="bg-card border-border sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="text-white">Edit Port Forwarding Rule</DialogTitle>
            <DialogDescription className="text-muted-foreground">
              Modify the port forwarding rule configuration.
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={handleEditRule} className="space-y-4">
            <div className="space-y-2">
              <Label className="text-muted-foreground">Rule Name *</Label>
              <Input
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                className="bg-zinc-900 border-zinc-700 text-white"
                data-testid="edit-rule-name-input"
              />
            </div>
            
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label className="text-muted-foreground">External Port *</Label>
                <Input
                  type="number"
                  value={formData.external_port}
                  onChange={(e) => setFormData({ ...formData, external_port: e.target.value })}
                  className="bg-zinc-900 border-zinc-700 text-white font-mono"
                  data-testid="edit-rule-external-port-input"
                />
                {formData.external_port && isOutsideRange(formData.external_port) && (
                  <p className="text-xs text-amber-400 flex items-center gap-1">
                    <AlertTriangle className="w-3 h-3" />
                    Outside safe range (60000-61000)
                  </p>
                )}
              </div>
              <div className="space-y-2">
                <Label className="text-muted-foreground">Internal Port *</Label>
                <Input
                  type="number"
                  value={formData.internal_port}
                  onChange={(e) => setFormData({ ...formData, internal_port: e.target.value })}
                  className="bg-zinc-900 border-zinc-700 text-white font-mono"
                  data-testid="edit-rule-internal-port-input"
                />
              </div>
            </div>
            
            <div className="space-y-2">
              <Label className="text-muted-foreground">Protocol</Label>
              <Select
                value={formData.protocol}
                onValueChange={(value) => setFormData({ ...formData, protocol: value })}
              >
                <SelectTrigger className="bg-zinc-900 border-zinc-700 text-white" data-testid="edit-rule-protocol-select">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="bg-zinc-900 border-zinc-700">
                  <SelectItem value="both">TCP & UDP</SelectItem>
                  <SelectItem value="tcp">TCP Only</SelectItem>
                  <SelectItem value="udp">UDP Only</SelectItem>
                </SelectContent>
              </Select>
            </div>
            
            <div className="space-y-2">
              <Label className="text-muted-foreground">Description</Label>
              <Input
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                className="bg-zinc-900 border-zinc-700 text-white"
                data-testid="edit-rule-description-input"
              />
            </div>
            
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setIsEditDialogOpen(false)} className="border-zinc-700 text-muted-foreground hover:text-white">
                Cancel
              </Button>
              <Button type="submit" className="bg-blue-600 hover:bg-blue-700" data-testid="edit-rule-submit-button">
                Save Changes
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <Dialog open={isDeleteDialogOpen} onOpenChange={setIsDeleteDialogOpen}>
        <DialogContent className="bg-card border-border sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="text-white">Delete Rule</DialogTitle>
            <DialogDescription className="text-muted-foreground">
              Are you sure you want to delete "{selectedRule?.name}"? This will also remove the associated firewall rules.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setIsDeleteDialogOpen(false)} className="border-zinc-700 text-muted-foreground hover:text-white">
              Cancel
            </Button>
            <Button onClick={handleDeleteRule} className="bg-red-600 hover:bg-red-700" data-testid="confirm-delete-button">
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Password Change Dialog (forced on first login) */}
      <ChangePasswordDialog 
        open={showPasswordDialog} 
        onOpenChange={setShowPasswordDialog}
        forced={user?.must_change_password}
      />
    </div>
  );
}
