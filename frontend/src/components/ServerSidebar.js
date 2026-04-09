import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../lib/api';
import { useAuth } from '../contexts/AuthContext';
import { MessageCircle, Users, Plus, Shield, Settings, LogOut, BarChart3, Circle, ChevronUp } from 'lucide-react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '../components/ui/dialog';
import { Input } from '../components/ui/input';
import { Button } from '../components/ui/button';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '../components/ui/tooltip';
import { ScrollArea } from '../components/ui/scroll-area';
import { Popover, PopoverContent, PopoverTrigger } from '../components/ui/popover';

export default function ServerSidebar({ servers, activeServer, onSelectServer, onSelectDMs, onSelectFriends, onServerCreated, onOpenSettings }) {
  const navigate = useNavigate();
  const { logout, user, setUser } = useAuth();
  const [showCreate, setShowCreate] = useState(false);
  const [showJoin, setShowJoin] = useState(false);
  const [serverName, setServerName] = useState('');
  const [inviteCode, setInviteCode] = useState('');
  const [creating, setCreating] = useState(false);
  const [statusOpen, setStatusOpen] = useState(false);

  const STATUS_OPTIONS = [
    { value: 'online', label: 'Online', color: 'bg-emerald-500' },
    { value: 'away', label: 'Away', color: 'bg-amber-500' },
    { value: 'busy', label: 'Busy', color: 'bg-red-500' },
    { value: 'invisible', label: 'Invisible', color: 'bg-slate-500' },
  ];

  const currentStatus = STATUS_OPTIONS.find(s => s.value === (user?.status || 'online')) || STATUS_OPTIONS[0];

  const handleStatusChange = async (status) => {
    try {
      await api.put('/users/me/status', { status });
      setUser(prev => ({ ...prev, status }));
      setStatusOpen(false);
    } catch {}
  };

  const handleCreate = async () => {
    if (!serverName.trim()) return;
    setCreating(true);
    try {
      await api.post('/servers', { name: serverName });
      setServerName('');
      setShowCreate(false);
      onServerCreated();
    } catch {}
    setCreating(false);
  };

  const handleJoin = async () => {
    if (!inviteCode.trim()) return;
    try {
      await api.post(`/invites/${inviteCode}/join`);
      setInviteCode('');
      setShowJoin(false);
      onServerCreated();
    } catch {}
  };

  return (
    <TooltipProvider delayDuration={0}>
      <div className="w-[72px] bg-slate-950 flex flex-col items-center py-3 gap-2 border-r border-white/5" data-testid="server-sidebar">
        {/* DMs button */}
        <Tooltip>
          <TooltipTrigger asChild>
            <button
              onClick={onSelectDMs}
              className={`w-12 h-12 rounded-2xl flex items-center justify-center transition-all duration-200 ${
                !activeServer ? 'bg-emerald-500 text-slate-950 rounded-xl' : 'bg-slate-800 text-slate-300 hover:bg-emerald-500 hover:text-slate-950 hover:rounded-xl'
              }`}
              data-testid="dm-nav-btn"
            >
              <MessageCircle className="w-5 h-5" />
            </button>
          </TooltipTrigger>
          <TooltipContent side="right"><p>Direct Messages</p></TooltipContent>
        </Tooltip>

        {/* Friends button */}
        <Tooltip>
          <TooltipTrigger asChild>
            <button
              onClick={onSelectFriends}
              className="w-12 h-12 rounded-2xl bg-slate-800 text-slate-300 hover:bg-emerald-500 hover:text-slate-950 hover:rounded-xl flex items-center justify-center transition-all duration-200"
              data-testid="friends-nav-btn"
            >
              <Users className="w-5 h-5" />
            </button>
          </TooltipTrigger>
          <TooltipContent side="right"><p>Friends</p></TooltipContent>
        </Tooltip>

        <div className="w-8 h-px bg-white/10 my-1" />

        {/* Server list */}
        <ScrollArea className="flex-1 w-full">
          <div className="flex flex-col items-center gap-2 px-3">
            {servers.map(s => (
              <Tooltip key={s.id}>
                <TooltipTrigger asChild>
                  <button
                    onClick={() => onSelectServer(s.id)}
                    className={`w-12 h-12 rounded-2xl flex items-center justify-center transition-all duration-200 text-sm font-medium ${
                      activeServer === s.id
                        ? 'bg-emerald-500 text-slate-950 rounded-xl'
                        : 'bg-slate-800 text-slate-300 hover:bg-emerald-500/20 hover:text-emerald-400 hover:rounded-xl'
                    }`}
                    data-testid={`server-btn-${s.id}`}
                  >
                    {s.icon_url ? (
                      <img src={s.icon_url} alt="" className="w-full h-full rounded-inherit object-cover" />
                    ) : (
                      s.name.slice(0, 2).toUpperCase()
                    )}
                  </button>
                </TooltipTrigger>
                <TooltipContent side="right"><p>{s.name}</p></TooltipContent>
              </Tooltip>
            ))}
          </div>
        </ScrollArea>

        {/* Create / Join server */}
        <div className="flex flex-col items-center gap-2 mt-auto">
          <Dialog open={showCreate} onOpenChange={setShowCreate}>
            <Tooltip>
              <TooltipTrigger asChild>
                <DialogTrigger asChild>
                  <button className="w-12 h-12 rounded-2xl bg-slate-800 text-emerald-500 hover:bg-emerald-500 hover:text-slate-950 hover:rounded-xl flex items-center justify-center transition-all duration-200" data-testid="create-server-btn">
                    <Plus className="w-5 h-5" />
                  </button>
                </DialogTrigger>
              </TooltipTrigger>
              <TooltipContent side="right"><p>Create Server</p></TooltipContent>
            </Tooltip>
            <DialogContent className="bg-slate-900 border-white/10 text-slate-100">
              <DialogHeader>
                <DialogTitle className="font-['Outfit']">Create a Server</DialogTitle>
              </DialogHeader>
              <div className="space-y-4 pt-4">
                <Input
                  value={serverName}
                  onChange={(e) => setServerName(e.target.value)}
                  placeholder="Server name"
                  className="bg-slate-950/50 border-white/10 text-slate-100"
                  data-testid="create-server-name-input"
                />
                <Button onClick={handleCreate} disabled={creating} className="w-full bg-emerald-500 text-slate-950 hover:bg-emerald-400" data-testid="create-server-submit-btn">
                  {creating ? 'Creating...' : 'Create Server'}
                </Button>
              </div>
            </DialogContent>
          </Dialog>

          <Dialog open={showJoin} onOpenChange={setShowJoin}>
            <Tooltip>
              <TooltipTrigger asChild>
                <DialogTrigger asChild>
                  <button className="w-12 h-12 rounded-2xl bg-slate-800 text-slate-300 hover:bg-slate-700 hover:rounded-xl flex items-center justify-center transition-all duration-200" data-testid="join-server-btn">
                    <Shield className="w-5 h-5" />
                  </button>
                </DialogTrigger>
              </TooltipTrigger>
              <TooltipContent side="right"><p>Join Server</p></TooltipContent>
            </Tooltip>
            <DialogContent className="bg-slate-900 border-white/10 text-slate-100">
              <DialogHeader>
                <DialogTitle className="font-['Outfit']">Join a Server</DialogTitle>
              </DialogHeader>
              <div className="space-y-4 pt-4">
                <Input
                  value={inviteCode}
                  onChange={(e) => setInviteCode(e.target.value)}
                  placeholder="Enter invite code"
                  className="bg-slate-950/50 border-white/10 text-slate-100"
                  data-testid="join-server-code-input"
                />
                <Button onClick={handleJoin} className="w-full bg-emerald-500 text-slate-950 hover:bg-emerald-400" data-testid="join-server-submit-btn">
                  Join Server
                </Button>
              </div>
            </DialogContent>
          </Dialog>

          {/* User area with status */}
          <div className="flex flex-col items-center gap-2 pt-2 border-t border-white/5 w-full px-3">
            <Popover open={statusOpen} onOpenChange={setStatusOpen}>
              <PopoverTrigger asChild>
                <button className="w-12 h-12 rounded-2xl bg-slate-800/80 flex items-center justify-center relative group hover:bg-slate-700 transition-colors" data-testid="user-status-btn">
                  <span className="text-sm font-medium text-slate-200">{user?.username?.slice(0, 2).toUpperCase() || '??'}</span>
                  <span className={`absolute -bottom-0.5 -right-0.5 w-3.5 h-3.5 rounded-full border-2 border-slate-950 ${currentStatus.color}`} />
                </button>
              </PopoverTrigger>
              <PopoverContent side="right" align="end" className="bg-slate-900 border-white/10 w-48 p-2" data-testid="status-popover">
                <p className="text-xs font-mono uppercase tracking-widest text-slate-500 px-2 mb-2">Set Status</p>
                {STATUS_OPTIONS.map(s => (
                  <button
                    key={s.value}
                    onClick={() => handleStatusChange(s.value)}
                    className={`w-full flex items-center gap-2.5 px-2 py-2 rounded text-sm transition-colors ${
                      user?.status === s.value ? 'bg-slate-800 text-slate-100' : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
                    }`}
                    data-testid={`status-option-${s.value}`}
                  >
                    <span className={`w-2.5 h-2.5 rounded-full ${s.color}`} />
                    {s.label}
                  </button>
                ))}
              </PopoverContent>
            </Popover>
            <Tooltip>
              <TooltipTrigger asChild>
                <button onClick={() => onOpenSettings && onOpenSettings()} className="w-10 h-10 rounded-full bg-slate-800 text-slate-400 hover:text-slate-200 flex items-center justify-center transition-colors" data-testid="user-settings-btn">
                  <Settings className="w-4 h-4" />
                </button>
              </TooltipTrigger>
              <TooltipContent side="right"><p>User Settings</p></TooltipContent>
            </Tooltip>
            {user?.role === 'admin' && (
              <Tooltip>
                <TooltipTrigger asChild>
                  <button onClick={() => navigate('/admin')} className="w-10 h-10 rounded-full bg-slate-800 text-amber-500 hover:text-amber-400 flex items-center justify-center transition-colors" data-testid="admin-dashboard-btn">
                    <BarChart3 className="w-4 h-4" />
                  </button>
                </TooltipTrigger>
                <TooltipContent side="right"><p>Admin Dashboard</p></TooltipContent>
              </Tooltip>
            )}
            <Tooltip>
              <TooltipTrigger asChild>
                <button onClick={logout} className="w-10 h-10 rounded-full bg-slate-800 text-slate-400 hover:text-red-400 flex items-center justify-center transition-colors" data-testid="logout-btn">
                  <LogOut className="w-4 h-4" />
                </button>
              </TooltipTrigger>
              <TooltipContent side="right"><p>Logout</p></TooltipContent>
            </Tooltip>
          </div>
        </div>
      </div>
    </TooltipProvider>
  );
}
