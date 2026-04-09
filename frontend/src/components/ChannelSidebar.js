import { Hash, Volume2, ChevronDown, Plus, Settings, HardDrive, Copy, Check, Settings2 } from 'lucide-react';
import { ScrollArea } from '../components/ui/scroll-area';
import { useState, useCallback } from 'react';
import api from '../lib/api';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '../components/ui/dialog';
import { Input } from '../components/ui/input';
import { Button } from '../components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Popover, PopoverContent, PopoverTrigger } from '../components/ui/popover';

export default function ChannelSidebar({ server, activeChannel, onSelectChannel, onOpenSettings, onOpenDrive, user, onChannelCreated, onOpenChannelSettings }) {
  const [showCreate, setShowCreate] = useState(false);
  const [channelName, setChannelName] = useState('');
  const [channelType, setChannelType] = useState('text');
  const [category, setCategory] = useState('General');
  const [copied, setCopied] = useState(false);

  const isOwner = server?.owner_id === user?.id;
  const member = server?.members?.find(m => m.user_id === user?.id);
  const hasManageChannels = isOwner || (member?.roles || []).some(r => {
    const role = server?.roles?.find(rl => rl.id === r);
    return role && (role.permissions & (1 << 0)) !== 0; // MANAGE_CHANNELS
  });

  const handleCreate = async () => {
    if (!channelName.trim()) return;
    try {
      await api.post(`/servers/${server.id}/channels`, { name: channelName, channel_type: channelType, category });
      setChannelName('');
      setShowCreate(false);
      if (onChannelCreated) onChannelCreated();
    } catch {}
  };

  const handleCopyInvite = useCallback(async () => {
    try {
      const { data } = await api.get(`/servers/${server.id}/invites`);
      const code = data[0]?.code;
      if (code) {
        const base = window.location.origin;
        await navigator.clipboard.writeText(`${base}/invite/${code}`);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      }
    } catch {}
  }, [server?.id]);

  const channels = server?.channels || [];
  const categories = [...new Set(channels.map(c => c.category || 'General'))];

  return (
    <div className="w-60 bg-slate-900/50 border-r border-white/5 flex flex-col h-full" data-testid="channel-sidebar">
      {/* Server header */}
      <div className="h-12 px-4 flex items-center justify-between border-b border-white/5 flex-shrink-0">
        <Popover>
          <PopoverTrigger asChild>
            <button className="flex items-center gap-1 text-slate-100 font-medium text-sm hover:text-white truncate font-['Outfit']" data-testid="server-header">
              {server?.name}
              <ChevronDown className="w-4 h-4 text-slate-500" />
            </button>
          </PopoverTrigger>
          <PopoverContent className="bg-slate-900 border-white/10 p-1.5 w-48" align="start">
            <button
              onClick={handleCopyInvite}
              className="w-full flex items-center gap-2 px-3 py-2 rounded text-sm text-slate-300 hover:bg-slate-800 transition-colors"
              data-testid="copy-invite-btn"
            >
              {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
              <span>{copied ? 'Copied!' : 'Copy Invite Link'}</span>
            </button>
            {isOwner && (
              <button
                onClick={() => { onOpenSettings(); }}
                className="w-full flex items-center gap-2 px-3 py-2 rounded text-sm text-slate-300 hover:bg-slate-800 transition-colors"
                data-testid="server-settings-menu-btn"
              >
                <Settings className="w-3.5 h-3.5" />
                <span>Server Settings</span>
              </button>
            )}
          </PopoverContent>
        </Popover>
        {isOwner && (
          <button onClick={onOpenSettings} className="text-slate-500 hover:text-slate-300" data-testid="server-settings-btn">
            <Settings className="w-4 h-4" />
          </button>
        )}
      </div>

      {/* Channels */}
      <ScrollArea className="flex-1">
        <div className="p-2">
          {categories.map(cat => (
            <div key={cat} className="mb-2">
              <div className="flex items-center justify-between px-2 py-1">
                <span className="text-xs font-mono uppercase tracking-widest text-slate-500">{cat}</span>
                {hasManageChannels && (
                  <Dialog open={showCreate} onOpenChange={setShowCreate}>
                    <DialogTrigger asChild>
                      <button className="text-slate-500 hover:text-slate-300" onClick={() => setCategory(cat)} data-testid="add-channel-btn">
                        <Plus className="w-3 h-3" />
                      </button>
                    </DialogTrigger>
                    <DialogContent className="bg-slate-900 border-white/10 text-slate-100">
                      <DialogHeader><DialogTitle className="font-['Outfit']">Create Channel</DialogTitle></DialogHeader>
                      <div className="space-y-4 pt-4">
                        <Input value={channelName} onChange={e => setChannelName(e.target.value)} placeholder="Channel name" className="bg-slate-950/50 border-white/10 text-slate-100" data-testid="create-channel-name-input" />
                        <Select value={channelType} onValueChange={setChannelType}>
                          <SelectTrigger className="bg-slate-950/50 border-white/10 text-slate-100" data-testid="create-channel-type-select">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent className="bg-slate-900 border-white/10">
                            <SelectItem value="text">Text Channel</SelectItem>
                            <SelectItem value="voice">Voice Channel</SelectItem>
                          </SelectContent>
                        </Select>
                        <Button onClick={handleCreate} className="w-full bg-emerald-500 text-slate-950 hover:bg-emerald-400" data-testid="create-channel-submit-btn">Create Channel</Button>
                      </div>
                    </DialogContent>
                  </Dialog>
                )}
              </div>
              {channels.filter(c => (c.category || 'General') === cat).map(ch => (
                <div key={ch.id} className="group flex items-center">
                  <button
                    onClick={() => onSelectChannel(ch)}
                    className={`flex-1 flex items-center gap-2 px-2 py-1.5 rounded-l text-sm transition-colors ${
                      activeChannel?.id === ch.id
                        ? 'bg-slate-800 text-slate-100'
                        : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
                    }`}
                    data-testid={`channel-btn-${ch.id}`}
                  >
                    {ch.channel_type === 'voice' ? <Volume2 className="w-4 h-4 flex-shrink-0" /> : <Hash className="w-4 h-4 flex-shrink-0" />}
                    <span className="truncate">{ch.name}</span>
                    {ch.slowmode_seconds > 0 && <span className="text-xs text-amber-500 ml-auto font-mono">{ch.slowmode_seconds}s</span>}
                  </button>
                  {hasManageChannels && (
                    <button
                      onClick={() => onOpenChannelSettings && onOpenChannelSettings(ch)}
                      className="p-1 text-slate-600 hover:text-slate-300 opacity-0 group-hover:opacity-100 transition-opacity"
                      data-testid={`channel-settings-${ch.id}`}
                    >
                      <Settings2 className="w-3 h-3" />
                    </button>
                  )}
                </div>
              ))}
            </div>
          ))}
        </div>
      </ScrollArea>

      {/* Share Drive button */}
      <div className="p-2 border-t border-white/5">
        <button
          onClick={onOpenDrive}
          className="w-full flex items-center gap-2 px-3 py-2 rounded text-sm text-slate-400 hover:text-slate-200 hover:bg-slate-800/50 transition-colors"
          data-testid="share-drive-btn"
        >
          <HardDrive className="w-4 h-4" />
          <span>Share Drive</span>
          <span className="ml-auto text-xs font-mono text-slate-600">
            {((server?.storage_used_bytes || 0) / (1024 * 1024 * 1024)).toFixed(1)}GB
          </span>
        </button>
      </div>
    </div>
  );
}
