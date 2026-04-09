import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useNavigate } from 'react-router-dom';
import api from '../lib/api';
import { Shield, Users, MessageCircle, Server, HardDrive, Mic, ArrowLeft, RefreshCw } from 'lucide-react';
import { Button } from '../components/ui/button';
import { ScrollArea } from '../components/ui/scroll-area';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts';

export default function AdminDashboard() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [stats, setStats] = useState(null);
  const [servers, setServers] = useState([]);
  const [storageRequests, setStorageRequests] = useState([]);
  const [loading, setLoading] = useState(true);

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
