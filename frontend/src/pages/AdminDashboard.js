import { useState, useEffect, useCallback, useRef } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useNavigate } from 'react-router-dom';
import api from '../lib/api';
import { Shield, Users, MessageCircle, Server, HardDrive, Mic, ArrowLeft, RefreshCw, Download, GitBranch, Check, AlertCircle, Loader2, Settings2, Radio, Play, Square } from 'lucide-react';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { ScrollArea } from '../components/ui/scroll-area';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts';

export default function AdminDashboard() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [stats, setStats] = useState(null);
  const [servers, setServers] = useState([]);
  const [storageRequests, setStorageRequests] = useState([]);
  const [loading, setLoading] = useState(true);

  // Update system state
  const [updateConfig, setUpdateConfig] = useState(null);
  const [updateCheck, setUpdateCheck] = useState(null);
  const [updateStatus, setUpdateStatus] = useState(null);
  const [checking, setChecking] = useState(false);
  const [applying, setApplying] = useState(false);
  const [editRepo, setEditRepo] = useState(false);
  const [repoInput, setRepoInput] = useState('');
  const pollRef = useRef(null);

  // TURN server state
  const [turnConfig, setTurnConfig] = useState(null);
  const [turnStatus, setTurnStatus] = useState(null);
  const [turnLoading, setTurnLoading] = useState(false);
  const [editTurn, setEditTurn] = useState(false);
  const [turnHost, setTurnHost] = useState('');
  const [turnPort, setTurnPort] = useState('3478');
  const [turnSecret, setTurnSecret] = useState('');
  const [turnRealm, setTurnRealm] = useState('');

  const loadStats = useCallback(async () => {
    try {
      const [statsRes, serversRes, storageRes] = await Promise.all([
        api.get('/admin/stats'),
        api.get('/admin/servers'),
        api.get('/admin/storage-requests')
      ]);
      setStats(statsRes.data);
      setServers(serversRes.data);
      setStorageRequests(storageRes.data);
    } catch {}
    setLoading(false);
  }, []);

  useEffect(() => {
    if (user?.role !== 'admin') {
      navigate('/app');
      return;
    }
    loadStats();
  }, [user, navigate, loadStats]);

  const formatBytes = (bytes) => {
    if (!bytes) return '0 B';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
  };

  const handleApproveStorage = async (requestId, requestedGb) => {
    try {
      await api.post(`/admin/storage-requests/${requestId}/approve`, { approved_gb: requestedGb });
      loadStats();
    } catch {}
  };

  const handleDenyStorage = async (requestId) => {
    try {
      await api.post(`/admin/storage-requests/${requestId}/deny`, { note: 'Denied by admin' });
      loadStats();
    } catch {}
  };

  // ── Update system functions ──
  const loadUpdateConfig = useCallback(async () => {
    try {
      const { data } = await api.get('/admin/update/config');
      setUpdateConfig(data);
      setRepoInput(data.repo_url || '');
    } catch {}
  }, []);

  useEffect(() => {
    if (user?.role === 'admin') loadUpdateConfig();
  }, [user, loadUpdateConfig]);

  // Load TURN config
  const loadTurnConfig = useCallback(async () => {
    try {
      const [configRes, statusRes] = await Promise.all([
        api.get('/admin/turn/config'),
        api.get('/admin/turn/status')
      ]);
      setTurnConfig(configRes.data);
      setTurnStatus(statusRes.data);
      setTurnHost(configRes.data.host || '');
      setTurnPort(String(configRes.data.port || 3478));
      setTurnSecret(configRes.data.shared_secret || '');
      setTurnRealm(configRes.data.realm || '');
    } catch {}
  }, []);

  useEffect(() => {
    if (user?.role === 'admin') loadTurnConfig();
  }, [user, loadTurnConfig]);

  const handleStartTurn = async () => {
    setTurnLoading(true);
    try {
      await api.post('/admin/turn/start');
      await loadTurnConfig();
    } catch {}
    setTurnLoading(false);
  };

  const handleStopTurn = async () => {
    setTurnLoading(true);
    try {
      await api.post('/admin/turn/stop');
      await loadTurnConfig();
    } catch {}
    setTurnLoading(false);
  };

  const handleSaveTurnConfig = async () => {
    try {
      await api.put('/admin/turn/config', {
        host: turnHost.trim(),
        port: parseInt(turnPort) || 3478,
        shared_secret: turnSecret.trim(),
        realm: turnRealm.trim()
      });
      setEditTurn(false);
      await loadTurnConfig();
    } catch {}
  };

  // Poll update status while in-progress
  useEffect(() => {
    if (applying) {
      pollRef.current = setInterval(async () => {
        try {
          const { data } = await api.get('/admin/update/status');
          setUpdateStatus(data);
          if (data.status !== 'in_progress') {
            setApplying(false);
            clearInterval(pollRef.current);
            loadUpdateConfig();
          }
        } catch {}
      }, 3000);
      return () => clearInterval(pollRef.current);
    }
  }, [applying, loadUpdateConfig]);

  const handleCheckUpdates = async () => {
    setChecking(true);
    try {
      const { data } = await api.post('/admin/update/check');
      setUpdateCheck(data);
    } catch {}
    setChecking(false);
  };

  const handleApplyUpdate = async () => {
    setApplying(true);
    setUpdateStatus({ status: 'in_progress', log: '' });
    try {
      await api.post('/admin/update/apply');
    } catch {
      setApplying(false);
    }
  };

  const handleSaveRepo = async () => {
    try {
      await api.put('/admin/update/config', { repo_url: repoInput.trim() });
      setEditRepo(false);
      loadUpdateConfig();
    } catch {}
  };

  if (loading) {
    return <div className="min-h-screen bg-[#020617] flex items-center justify-center text-slate-500">Loading...</div>;
  }

  const messageData = [
    { name: 'Today', count: stats?.messages_today || 0 },
    { name: 'This Week', count: stats?.messages_this_week || 0 },
    { name: 'This Month', count: stats?.messages_this_month || 0 },
    { name: 'Total', count: stats?.total_messages || 0 }
  ];

  return (
    <div className="min-h-screen bg-[#020617] text-slate-100" data-testid="admin-dashboard">
      {/* Header */}
      <div className="h-14 px-6 flex items-center justify-between border-b border-white/5 bg-slate-950/60 backdrop-blur-2xl sticky top-0 z-10">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="sm" onClick={() => navigate('/app')} className="text-slate-400 hover:text-white" data-testid="admin-back-btn">
            <ArrowLeft className="w-4 h-4 mr-1" /> Back
          </Button>
          <Shield className="w-5 h-5 text-emerald-500" />
          <span className="text-sm font-medium font-['Outfit']">Admin Dashboard</span>
        </div>
        <Button variant="ghost" size="sm" onClick={loadStats} className="text-slate-400 hover:text-white" data-testid="admin-refresh-btn">
          <RefreshCw className="w-4 h-4 mr-1" /> Refresh
        </Button>
      </div>

      <div className="p-6 max-w-7xl mx-auto">
        {/* Stat cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          {[
            { icon: Users, label: 'Registered Users', value: stats?.users_registered || 0, color: 'text-emerald-500' },
            { icon: Users, label: 'Online Now', value: stats?.users_online || 0, color: 'text-emerald-400' },
            { icon: Mic, label: 'Active Voice', value: stats?.voice_chats_active || 0, color: 'text-amber-500' },
            { icon: Server, label: 'Total Servers', value: stats?.total_servers || 0, color: 'text-blue-500' },
            { icon: MessageCircle, label: 'Total Messages', value: stats?.total_messages || 0, color: 'text-purple-400' },
            { icon: MessageCircle, label: 'Messages Today', value: stats?.messages_today || 0, color: 'text-emerald-500' },
            { icon: HardDrive, label: 'Attachment Storage', value: formatBytes(stats?.message_attachment_storage_bytes), color: 'text-amber-400' },
            { icon: HardDrive, label: 'Drive Storage', value: formatBytes(stats?.drive_storage_bytes), color: 'text-red-400' }
          ].map((stat, i) => (
            <div key={i} className="p-4 bg-slate-900/50 border border-white/5 rounded-lg" data-testid={`stat-card-${i}`}>
              <div className="flex items-center gap-2 mb-2">
                <stat.icon className={`w-4 h-4 ${stat.color}`} />
                <span className="text-xs font-mono uppercase tracking-widest text-slate-500">{stat.label}</span>
              </div>
              <p className="text-2xl font-medium font-['Outfit']">{stat.value}</p>
            </div>
          ))}
        </div>

        {/* Messages chart */}
        <div className="mb-8 p-6 bg-slate-900/50 border border-white/5 rounded-lg">
          <h3 className="text-sm font-medium text-slate-200 mb-4 font-['Outfit']">Messages Over Time</h3>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={messageData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis dataKey="name" tick={{ fill: '#64748b', fontSize: 12 }} />
                <YAxis tick={{ fill: '#64748b', fontSize: 12 }} />
                <Tooltip
                  contentStyle={{ backgroundColor: '#0f172a', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px' }}
                  labelStyle={{ color: '#e2e8f0' }}
                  itemStyle={{ color: '#10b981' }}
                />
                <Bar dataKey="count" fill="#10b981" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Storage Requests */}
        {storageRequests.length > 0 && (
          <div className="mb-8 p-6 bg-slate-900/50 border border-white/5 rounded-lg">
            <div className="flex items-center gap-2 mb-4">
              <HardDrive className="w-4 h-4 text-amber-500" />
              <h3 className="text-sm font-medium text-slate-200 font-['Outfit']">Pending Storage Requests</h3>
              <span className="ml-auto text-xs font-mono bg-amber-500/20 text-amber-400 px-2 py-0.5 rounded-full">{storageRequests.length}</span>
            </div>
            <div className="space-y-2">
              {storageRequests.map(req => (
                <div key={req.id} className="flex items-center justify-between px-4 py-3 bg-slate-800/30 rounded border border-white/5" data-testid={`admin-storage-request-${req.id}`}>
                  <div>
                    <p className="text-sm text-slate-200">{req.server_name}</p>
                    <p className="text-xs text-slate-500">
                      Requested by {req.requester_username} — {req.requested_gb} GB (current: {req.current_limit_gb?.toFixed(1)} GB)
                    </p>
                    {req.reason && <p className="text-xs text-slate-400 mt-0.5">{req.reason}</p>}
                  </div>
                  <div className="flex gap-2">
                    <Button size="sm" onClick={() => handleApproveStorage(req.id, req.requested_gb)} className="bg-emerald-500 text-slate-950 hover:bg-emerald-400 h-8 text-xs" data-testid={`approve-storage-${req.id}`}>
                      Approve
                    </Button>
                    <Button size="sm" variant="outline" onClick={() => handleDenyStorage(req.id)} className="border-red-500/30 text-red-400 hover:bg-red-500/10 h-8 text-xs" data-testid={`deny-storage-${req.id}`}>
                      Deny
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* TURN Server Management */}
        <div className="mb-8 p-6 bg-slate-900/50 border border-white/5 rounded-lg" data-testid="turn-panel">
          <div className="flex items-center gap-2 mb-5">
            <Radio className="w-4 h-4 text-emerald-500" />
            <h3 className="text-sm font-medium text-slate-200 font-['Outfit']">TURN Server (Voice/Video Relay)</h3>
            <span className={`ml-auto text-xs font-mono px-2 py-0.5 rounded-full ${
              turnStatus?.container_status === 'running'
                ? 'bg-emerald-500/20 text-emerald-400'
                : 'bg-slate-700/50 text-slate-500'
            }`} data-testid="turn-status-badge">
              {turnStatus?.container_status || 'unknown'}
            </span>
          </div>

          {/* Config display/edit */}
          {editTurn ? (
            <div className="space-y-3 mb-4 p-3 bg-slate-800/30 rounded border border-white/5">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-mono text-slate-500 block mb-1">Host / IP</label>
                  <Input value={turnHost} onChange={e => setTurnHost(e.target.value)} placeholder="0.0.0.0 or your public IP" className="bg-slate-900 border-white/10 text-slate-100 text-sm h-8" data-testid="turn-host-input" />
                </div>
                <div>
                  <label className="text-xs font-mono text-slate-500 block mb-1">Port</label>
                  <Input value={turnPort} onChange={e => setTurnPort(e.target.value)} placeholder="3478" className="bg-slate-900 border-white/10 text-slate-100 text-sm h-8" data-testid="turn-port-input" />
                </div>
                <div>
                  <label className="text-xs font-mono text-slate-500 block mb-1">Shared Secret</label>
                  <Input value={turnSecret} onChange={e => setTurnSecret(e.target.value)} placeholder="your-secret" className="bg-slate-900 border-white/10 text-slate-100 text-sm h-8" data-testid="turn-secret-input" />
                </div>
                <div>
                  <label className="text-xs font-mono text-slate-500 block mb-1">Realm</label>
                  <Input value={turnRealm} onChange={e => setTurnRealm(e.target.value)} placeholder="shield.local" className="bg-slate-900 border-white/10 text-slate-100 text-sm h-8" data-testid="turn-realm-input" />
                </div>
              </div>
              <div className="flex gap-2">
                <Button size="sm" onClick={handleSaveTurnConfig} className="bg-emerald-500 text-slate-950 hover:bg-emerald-400 h-8 text-xs" data-testid="save-turn-config-btn">Save Config</Button>
                <Button size="sm" variant="ghost" onClick={() => setEditTurn(false)} className="text-slate-400 h-8 text-xs">Cancel</Button>
              </div>
            </div>
          ) : (
            <div className="mb-4 p-3 bg-slate-800/30 rounded border border-white/5">
              <div className="flex items-center justify-between">
                <div className="text-xs text-slate-400 space-y-1">
                  <div><span className="text-slate-600 font-mono">Host:</span> {turnConfig?.host || 'Not configured'}</div>
                  <div><span className="text-slate-600 font-mono">Port:</span> {turnConfig?.port || 3478}</div>
                  <div><span className="text-slate-600 font-mono">Realm:</span> {turnConfig?.realm || 'N/A'}</div>
                </div>
                <button onClick={() => setEditTurn(true)} className="text-slate-500 hover:text-slate-300 transition-colors" data-testid="edit-turn-btn">
                  <Settings2 className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          )}

          {/* Actions */}
          <div className="flex items-center gap-3">
            {turnStatus?.container_status !== 'running' ? (
              <Button onClick={handleStartTurn} disabled={turnLoading} size="sm" className="bg-emerald-500 text-slate-950 hover:bg-emerald-400 h-9" data-testid="start-turn-btn">
                {turnLoading ? <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> : <Play className="w-3.5 h-3.5 mr-1.5" />}
                Start TURN Server
              </Button>
            ) : (
              <Button onClick={handleStopTurn} disabled={turnLoading} size="sm" variant="outline" className="border-red-500/30 text-red-400 hover:bg-red-500/10 h-9" data-testid="stop-turn-btn">
                {turnLoading ? <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> : <Square className="w-3.5 h-3.5 mr-1.5" />}
                Stop TURN Server
              </Button>
            )}
            <Button onClick={loadTurnConfig} size="sm" variant="ghost" className="text-slate-400 h-9" data-testid="refresh-turn-btn">
              <RefreshCw className="w-3.5 h-3.5" />
            </Button>
          </div>

          <p className="text-[10px] text-slate-600 mt-4 font-mono">
            Requires Docker installed on host. TURN relays encrypted media for clients behind strict NATs.
            Open UDP ports 3478 and 49152-65535 in your firewall.
          </p>
        </div>

        {/* Update System */}
        <div className="mb-8 p-6 bg-slate-900/50 border border-white/5 rounded-lg" data-testid="update-panel">
          <div className="flex items-center gap-2 mb-5">
            <Download className="w-4 h-4 text-emerald-500" />
            <h3 className="text-sm font-medium text-slate-200 font-['Outfit']">System Updates</h3>
          </div>

          {/* Repo config */}
          <div className="flex items-center gap-3 mb-4 p-3 bg-slate-800/30 rounded border border-white/5">
            <GitBranch className="w-4 h-4 text-slate-500 flex-shrink-0" />
            {editRepo ? (
              <div className="flex items-center gap-2 flex-1">
                <Input
                  value={repoInput}
                  onChange={e => setRepoInput(e.target.value)}
                  className="bg-slate-900 border-white/10 text-slate-100 text-sm h-8 flex-1"
                  placeholder="https://github.com/user/repo"
                  data-testid="repo-url-input"
                />
                <Button size="sm" onClick={handleSaveRepo} className="bg-emerald-500 text-slate-950 hover:bg-emerald-400 h-8 text-xs" data-testid="save-repo-btn">Save</Button>
                <Button size="sm" variant="ghost" onClick={() => { setEditRepo(false); setRepoInput(updateConfig?.repo_url || ''); }} className="text-slate-400 h-8 text-xs">Cancel</Button>
              </div>
            ) : (
              <>
                <span className="text-sm text-slate-300 font-mono truncate flex-1" data-testid="repo-url-display">{updateConfig?.repo_url || 'Not configured'}</span>
                <button onClick={() => setEditRepo(true)} className="text-slate-500 hover:text-slate-300 transition-colors" data-testid="edit-repo-btn">
                  <Settings2 className="w-3.5 h-3.5" />
                </button>
              </>
            )}
          </div>

          {/* Current version */}
          {updateConfig?.current_commit && (
            <div className="flex items-center gap-2 mb-4 text-xs">
              <span className="text-slate-500">Current:</span>
              <span className="font-mono bg-slate-800 px-2 py-0.5 rounded text-emerald-400" data-testid="current-commit">{updateConfig.current_commit}</span>
              {updateConfig.current_commit_message && <span className="text-slate-400 truncate">{updateConfig.current_commit_message}</span>}
            </div>
          )}

          {/* Actions */}
          <div className="flex items-center gap-3 mb-4">
            <Button
              onClick={handleCheckUpdates}
              disabled={checking}
              size="sm"
              className="bg-slate-800 text-slate-200 hover:bg-slate-700 border border-white/10 h-9"
              data-testid="check-updates-btn"
            >
              {checking ? <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5 mr-1.5" />}
              Check for Updates
            </Button>
            {updateCheck?.has_updates && !applying && (
              <Button
                onClick={handleApplyUpdate}
                size="sm"
                className="bg-emerald-500 text-slate-950 hover:bg-emerald-400 h-9"
                data-testid="apply-update-btn"
              >
                <Download className="w-3.5 h-3.5 mr-1.5" /> Apply Update
              </Button>
            )}
            {updateCheck && !updateCheck.has_updates && (
              <span className="flex items-center gap-1.5 text-xs text-emerald-400">
                <Check className="w-3.5 h-3.5" /> Up to date
              </span>
            )}
          </div>

          {/* Update in progress */}
          {applying && (
            <div className="p-4 bg-amber-500/10 border border-amber-500/20 rounded mb-4" data-testid="update-progress">
              <div className="flex items-center gap-2 mb-2">
                <Loader2 className="w-4 h-4 text-amber-400 animate-spin" />
                <span className="text-sm text-amber-400 font-medium">Update in progress...</span>
              </div>
              {updateStatus?.log && (
                <pre className="text-xs text-slate-400 font-mono whitespace-pre-wrap bg-slate-950/50 rounded p-3 max-h-48 overflow-y-auto" data-testid="update-log">{updateStatus.log}</pre>
              )}
            </div>
          )}

          {/* Update result */}
          {!applying && updateStatus?.status === 'success' && (
            <div className="p-3 bg-emerald-500/10 border border-emerald-500/20 rounded mb-4 flex items-start gap-2" data-testid="update-success">
              <Check className="w-4 h-4 text-emerald-400 mt-0.5 flex-shrink-0" />
              <div>
                <p className="text-sm text-emerald-400 font-medium">Update applied successfully</p>
                {updateStatus.log && <pre className="text-xs text-slate-400 font-mono mt-2 whitespace-pre-wrap bg-slate-950/50 rounded p-3 max-h-32 overflow-y-auto">{updateStatus.log}</pre>}
              </div>
            </div>
          )}
          {!applying && updateStatus?.status === 'failed' && (
            <div className="p-3 bg-red-500/10 border border-red-500/20 rounded mb-4 flex items-start gap-2" data-testid="update-failed">
              <AlertCircle className="w-4 h-4 text-red-400 mt-0.5 flex-shrink-0" />
              <div>
                <p className="text-sm text-red-400 font-medium">Update failed</p>
                {updateStatus.log && <pre className="text-xs text-slate-400 font-mono mt-2 whitespace-pre-wrap bg-slate-950/50 rounded p-3 max-h-32 overflow-y-auto">{updateStatus.log}</pre>}
              </div>
            </div>
          )}

          {/* Recent commits from remote */}
          {updateCheck?.remote_commits?.length > 0 && (
            <div>
              <p className="text-xs font-mono uppercase tracking-widest text-slate-600 mb-2">Recent Commits</p>
              <div className="space-y-1">
                {updateCheck.remote_commits.map((c, i) => (
                  <div key={c.sha} className={`flex items-center gap-3 px-3 py-2 rounded text-xs ${
                    c.sha === updateConfig?.current_commit ? 'bg-emerald-500/10 border border-emerald-500/20' : 'bg-slate-800/30 border border-white/5'
                  }`} data-testid={`commit-${c.sha}`}>
                    <span className="font-mono text-slate-400 w-14 flex-shrink-0">{c.sha}</span>
                    <span className="text-slate-200 truncate flex-1">{c.message}</span>
                    <span className="text-slate-500 flex-shrink-0">{c.author}</span>
                    {c.sha === updateConfig?.current_commit && <span className="text-emerald-400 text-[10px] font-mono flex-shrink-0">CURRENT</span>}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Server list */}
        <div className="p-6 bg-slate-900/50 border border-white/5 rounded-lg">
          <h3 className="text-sm font-medium text-slate-200 mb-4 font-['Outfit']">Servers</h3>
          <ScrollArea className="max-h-96">
            <div className="space-y-2">
              {servers.map(s => (
                <div key={s.id} className="flex items-center justify-between px-4 py-3 bg-slate-800/30 rounded border border-white/5" data-testid={`admin-server-${s.id}`}>
                  <div>
                    <p className="text-sm text-slate-200">{s.name}</p>
                    <p className="text-xs text-slate-500">{s.member_count || 0} members</p>
                  </div>
                  <div className="text-right">
                    <p className="text-xs font-mono text-slate-400">Drive: {formatBytes(s.drive_storage_used)}</p>
                    <p className="text-xs font-mono text-slate-500">Limit: {formatBytes(s.storage_limit_bytes)}</p>
                  </div>
                </div>
              ))}
              {servers.length === 0 && <p className="text-slate-500 text-sm text-center py-4">No servers yet</p>}
            </div>
          </ScrollArea>
        </div>
      </div>
    </div>
  );
}
