import { useState } from 'react';
import api from '../lib/api';
import { X, Plus, Trash2, Copy, UserPlus, ShieldCheck } from 'lucide-react';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Button } from '../components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { ScrollArea } from '../components/ui/scroll-area';

export default function ServerSettings({ server, onClose, onUpdate }) {
  const [serverName, setServerName] = useState(server?.name || '');
  const [description, setDescription] = useState(server?.description || '');
  const [storageLimit, setStorageLimit] = useState((server?.storage_limit_bytes || 0) / (1024 * 1024 * 1024));
  const [saving, setSaving] = useState(false);
  const [roleName, setRoleName] = useState('');
  const [roleColor, setRoleColor] = useState('#10b981');
  const [inviteCode, setInviteCode] = useState('');

  const handleSave = async () => {
    setSaving(true);
    try {
      await api.put(`/servers/${server.id}`, { name: serverName, description, storage_limit_gb: storageLimit });
      onUpdate();
    } catch {}
    setSaving(false);
  };

  const handleCreateRole = async () => {
    if (!roleName.trim()) return;
    try {
      await api.post(`/servers/${server.id}/roles`, { name: roleName, color: roleColor, permissions: 0 });
      setRoleName('');
      onUpdate();
    } catch {}
  };

  const handleCreateInvite = async () => {
    try {
      const { data } = await api.post(`/servers/${server.id}/invites`, { expires_hours: 24 });
      setInviteCode(data.code);
    } catch {}
  };

  const handleKick = async (userId) => {
    try {
      await api.post(`/servers/${server.id}/kick/${userId}`);
      onUpdate();
    } catch {}
  };

  return (
    <div className="flex-1 flex flex-col bg-[#020617]" data-testid="server-settings">
      <div className="h-12 px-6 flex items-center justify-between border-b border-white/5 flex-shrink-0">
        <span className="text-sm font-medium text-slate-100 font-['Outfit']">Server Settings — {server?.name}</span>
        <button onClick={onClose} className="text-slate-400 hover:text-slate-200" data-testid="close-server-settings-btn">
          <X className="w-5 h-5" />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-8 max-w-3xl">
        <Tabs defaultValue="general">
          <TabsList className="bg-slate-900/50 border border-white/5 mb-6">
            <TabsTrigger value="general" className="data-[state=active]:bg-slate-800 text-slate-400 data-[state=active]:text-slate-100">General</TabsTrigger>
            <TabsTrigger value="roles" className="data-[state=active]:bg-slate-800 text-slate-400 data-[state=active]:text-slate-100">Roles</TabsTrigger>
            <TabsTrigger value="members" className="data-[state=active]:bg-slate-800 text-slate-400 data-[state=active]:text-slate-100">Members</TabsTrigger>
            <TabsTrigger value="invites" className="data-[state=active]:bg-slate-800 text-slate-400 data-[state=active]:text-slate-100">Invites</TabsTrigger>
          </TabsList>

          <TabsContent value="general">
            <div className="space-y-4">
              <div>
                <Label className="text-slate-300 text-sm">Server Name</Label>
                <Input value={serverName} onChange={e => setServerName(e.target.value)} className="bg-slate-900 border-white/10 text-slate-100 mt-1.5 max-w-sm" data-testid="server-name-input" />
              </div>
              <div>
                <Label className="text-slate-300 text-sm">Description</Label>
                <Input value={description} onChange={e => setDescription(e.target.value)} className="bg-slate-900 border-white/10 text-slate-100 mt-1.5 max-w-sm" data-testid="server-description-input" />
              </div>
              <div>
                <Label className="text-slate-300 text-sm">Storage Limit (GB)</Label>
                <Input type="number" value={storageLimit} onChange={e => setStorageLimit(parseFloat(e.target.value) || 25)} className="bg-slate-900 border-white/10 text-slate-100 mt-1.5 w-32" data-testid="server-storage-limit-input" />
                <p className="text-xs text-slate-500 mt-1 font-mono">
                  Used: {((server?.storage_used_bytes || 0) / (1024 * 1024 * 1024)).toFixed(2)} GB
                </p>
              </div>
              <Button onClick={handleSave} disabled={saving} className="bg-emerald-500 text-slate-950 hover:bg-emerald-400" data-testid="save-server-btn">
                {saving ? 'Saving...' : 'Save Changes'}
              </Button>
            </div>
          </TabsContent>

          <TabsContent value="roles">
            <div className="space-y-4">
              <div className="flex items-end gap-2">
                <div>
                  <Label className="text-slate-300 text-sm">Role Name</Label>
                  <Input value={roleName} onChange={e => setRoleName(e.target.value)} className="bg-slate-900 border-white/10 text-slate-100 mt-1.5" data-testid="role-name-input" />
                </div>
                <div>
                  <Label className="text-slate-300 text-sm">Color</Label>
                  <Input type="color" value={roleColor} onChange={e => setRoleColor(e.target.value)} className="bg-slate-900 border-white/10 mt-1.5 w-16 h-10 p-1" />
                </div>
                <Button onClick={handleCreateRole} className="bg-emerald-500 text-slate-950 hover:bg-emerald-400" data-testid="create-role-btn">
                  <Plus className="w-4 h-4 mr-1" /> Create
                </Button>
              </div>
              <ScrollArea className="max-h-64">
                <div className="space-y-1">
                  {server?.roles?.map(r => (
                    <div key={r.id} className="flex items-center gap-3 px-3 py-2 bg-slate-900/30 rounded border border-white/5">
                      <div className="w-3 h-3 rounded-full" style={{ backgroundColor: r.color }} />
                      <span className="text-sm text-slate-200">{r.name}</span>
                      <span className="text-xs text-slate-500 font-mono ml-auto">perms: {r.permissions}</span>
                    </div>
                  ))}
                </div>
              </ScrollArea>
            </div>
          </TabsContent>

          <TabsContent value="members">
            <ScrollArea className="max-h-96">
              <div className="space-y-1">
                {server?.members?.map(m => (
                  <div key={m.id} className="flex items-center justify-between px-3 py-2 bg-slate-900/30 rounded border border-white/5" data-testid={`settings-member-${m.user_id}`}>
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-full bg-slate-800 flex items-center justify-center text-xs text-slate-300">
                        {m.display_name?.slice(0, 2).toUpperCase()}
                      </div>
                      <div>
                        <p className="text-sm text-slate-200">{m.display_name || m.username}</p>
                        <p className="text-xs text-slate-500">{m.is_owner ? 'Owner' : 'Member'}</p>
                      </div>
                    </div>
                    {!m.is_owner && (
                      <button onClick={() => handleKick(m.user_id)} className="p-2 text-slate-400 hover:text-red-400 rounded" data-testid={`kick-member-${m.user_id}`}>
                        <Trash2 className="w-4 h-4" />
                      </button>
                    )}
                  </div>
                ))}
              </div>
            </ScrollArea>
          </TabsContent>

          <TabsContent value="invites">
            <div className="space-y-4">
              <Button onClick={handleCreateInvite} className="bg-emerald-500 text-slate-950 hover:bg-emerald-400" data-testid="create-invite-btn">
                <UserPlus className="w-4 h-4 mr-2" /> Generate Invite Link
              </Button>
              {inviteCode && (
                <div className="flex items-center gap-2 p-4 bg-slate-900/50 rounded border border-white/5">
                  <span className="text-sm text-slate-200 font-mono flex-1" data-testid="invite-code">{inviteCode}</span>
                  <button
                    onClick={() => navigator.clipboard.writeText(inviteCode)}
                    className="p-2 text-slate-400 hover:text-emerald-400 rounded"
                    data-testid="copy-invite-btn"
                  >
                    <Copy className="w-4 h-4" />
                  </button>
                </div>
              )}
            </div>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}
