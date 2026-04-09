import { useState, useEffect, useCallback } from 'react';
import api from '../lib/api';
import { Plus, Trash2, Shield, ChevronRight, RotateCcw } from 'lucide-react';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Button } from '../components/ui/button';
import { ScrollArea } from '../components/ui/scroll-area';
import { Switch } from '../components/ui/switch';
import { Separator } from '../components/ui/separator';

const CATEGORY_LABELS = {
  general_server: 'General Server Permissions',
  membership: 'Membership Permissions',
  text_channel: 'Text Channel Permissions',
  voice_channel: 'Voice Channel Permissions',
  apps: 'Apps Permissions',
  stage: 'Stage Channel Permissions',
  events: 'Events Permissions',
  advanced: 'Advanced Permissions',
};

export default function RoleEditor({ server, onUpdate }) {
  const [permMap, setPermMap] = useState(null);
  const [defaultPerms, setDefaultPerms] = useState(0);
  const [selectedRoleId, setSelectedRoleId] = useState(null);
  const [editPerms, setEditPerms] = useState(0);
  const [editName, setEditName] = useState('');
  const [editColor, setEditColor] = useState('#99AAB5');
  const [saving, setSaving] = useState(false);
  const [newRoleName, setNewRoleName] = useState('');
  const [newRoleColor, setNewRoleColor] = useState('#10b981');
  const [creating, setCreating] = useState(false);

  const roles = server?.roles || [];
  const selectedRole = roles.find(r => r.id === selectedRoleId);

  const loadPermMap = useCallback(async () => {
    try {
      const { data } = await api.get('/permissions/map');
      setPermMap(data.permissions);
      setDefaultPerms(data.default);
    } catch {}
  }, []);

  useEffect(() => { loadPermMap(); }, [loadPermMap]);

  useEffect(() => {
    if (roles.length > 0 && !selectedRoleId) {
      const everyone = roles.find(r => r.name === '@everyone');
      setSelectedRoleId(everyone?.id || roles[0].id);
    }
  }, [roles, selectedRoleId]);

  useEffect(() => {
    if (selectedRole) {
      setEditPerms(selectedRole.permissions);
      setEditName(selectedRole.name);
      setEditColor(selectedRole.color || '#99AAB5');
    }
  }, [selectedRole]);

  const isEveryone = selectedRole?.name === '@everyone';

  const togglePerm = (bit) => {
    setEditPerms(prev => prev ^ bit);
  };

  const hasPerm = (bit) => (editPerms & bit) === bit;

  const handleSave = async () => {
    if (!selectedRoleId) return;
    setSaving(true);
    try {
      const payload = { permissions: editPerms };
      if (!isEveryone) {
        payload.name = editName;
        payload.color = editColor;
      }
      await api.put(`/servers/${server.id}/roles/${selectedRoleId}`, payload);
      onUpdate();
    } catch {}
    setSaving(false);
  };

  const handleDelete = async () => {
    if (!selectedRoleId || isEveryone) return;
    try {
      await api.delete(`/servers/${server.id}/roles/${selectedRoleId}`);
      setSelectedRoleId(null);
      onUpdate();
    } catch {}
  };

  const handleCreate = async () => {
    if (!newRoleName.trim()) return;
    setCreating(true);
    try {
      await api.post(`/servers/${server.id}/roles`, { name: newRoleName, color: newRoleColor, permissions: 0 });
      setNewRoleName('');
      onUpdate();
    } catch {}
    setCreating(false);
  };

  const clearPermissions = () => setEditPerms(0);

  if (!permMap) return <p className="text-slate-500 text-sm py-4">Loading permissions...</p>;

  return (
    <div className="flex gap-6 min-h-[500px]" data-testid="role-editor">
      {/* Role list */}
      <div className="w-52 flex-shrink-0">
        <p className="text-xs font-mono uppercase tracking-widest text-slate-500 mb-3">Roles — {roles.length}</p>
        <ScrollArea className="h-[380px] mb-3">
          <div className="space-y-0.5 pr-2">
            {roles.map(r => (
              <button
                key={r.id}
                onClick={() => setSelectedRoleId(r.id)}
                className={`w-full flex items-center gap-2.5 px-3 py-2 rounded text-sm transition-colors text-left ${
                  selectedRoleId === r.id
                    ? 'bg-slate-800 text-slate-100'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
                }`}
                data-testid={`role-select-${r.id}`}
              >
                <span className="w-3 h-3 rounded-full flex-shrink-0" style={{ backgroundColor: r.color || '#99AAB5' }} />
                <span className="truncate">{r.name}</span>
                {selectedRoleId === r.id && <ChevronRight className="w-3 h-3 ml-auto flex-shrink-0 text-slate-600" />}
              </button>
            ))}
          </div>
        </ScrollArea>

        {/* Create new role */}
        <div className="border-t border-white/5 pt-3 space-y-2">
          <div className="flex gap-1.5">
            <Input
              value={newRoleName}
              onChange={e => setNewRoleName(e.target.value)}
              placeholder="New role..."
              className="bg-slate-950/50 border-white/10 text-slate-100 text-xs h-8 flex-1"
              data-testid="new-role-name-input"
            />
            <Input
              type="color"
              value={newRoleColor}
              onChange={e => setNewRoleColor(e.target.value)}
              className="bg-slate-950/50 border-white/10 w-8 h-8 p-0.5 cursor-pointer"
            />
          </div>
          <Button
            onClick={handleCreate}
            disabled={creating || !newRoleName.trim()}
            size="sm"
            className="w-full bg-emerald-500 text-slate-950 hover:bg-emerald-400 h-8 text-xs"
            data-testid="create-role-btn"
          >
            <Plus className="w-3 h-3 mr-1" /> {creating ? 'Creating...' : 'Create Role'}
          </Button>
        </div>
      </div>

      {/* Permission editor */}
      {selectedRole ? (
        <div className="flex-1 min-w-0">
          {/* Role header */}
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <Shield className="w-5 h-5 text-emerald-500" />
              {isEveryone ? (
                <div>
                  <p className="text-sm font-medium text-slate-100">@everyone</p>
                  <p className="text-xs text-slate-500">Permissions for all members in this server</p>
                </div>
              ) : (
                <div className="flex items-center gap-2">
                  <Input
                    value={editName}
                    onChange={e => setEditName(e.target.value)}
                    className="bg-slate-900 border-white/10 text-slate-100 text-sm h-8 w-48"
                    data-testid="edit-role-name"
                  />
                  <Input
                    type="color"
                    value={editColor}
                    onChange={e => setEditColor(e.target.value)}
                    className="bg-slate-900 border-white/10 w-8 h-8 p-0.5 cursor-pointer"
                    data-testid="edit-role-color"
                  />
                </div>
              )}
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={clearPermissions}
                className="text-xs text-emerald-400 hover:text-emerald-300 font-medium"
                data-testid="clear-permissions-btn"
              >
                Clear permissions
              </button>
              {!isEveryone && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleDelete}
                  className="text-red-400 hover:text-red-300 hover:bg-red-500/10 h-8"
                  data-testid="delete-role-btn"
                >
                  <Trash2 className="w-3.5 h-3.5 mr-1" /> Delete
                </Button>
              )}
            </div>
          </div>

          {/* Permission toggles */}
          <ScrollArea className="h-[400px]">
            <div className="space-y-6 pr-4">
              {Object.entries(permMap).map(([category, perms]) => (
                <div key={category}>
                  <h3 className="text-sm font-semibold text-slate-200 mb-3 font-['Outfit']">
                    {CATEGORY_LABELS[category] || category}
                  </h3>
                  <div className="space-y-0">
                    {perms.map((perm, i) => (
                      <div key={perm.key}>
                        <div className="flex items-center justify-between py-3 px-1">
                          <div className="flex-1 min-w-0 mr-4">
                            <p className="text-sm font-medium text-slate-200">{perm.name}</p>
                            <p className="text-xs text-slate-500 mt-0.5 leading-relaxed">{perm.description}</p>
                          </div>
                          <Switch
                            checked={hasPerm(perm.bit)}
                            onCheckedChange={() => togglePerm(perm.bit)}
                            data-testid={`perm-toggle-${perm.key}`}
                            className="data-[state=checked]:bg-emerald-500"
                          />
                        </div>
                        {i < perms.length - 1 && <Separator className="bg-white/5" />}
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </ScrollArea>

          {/* Save button */}
          <div className="mt-4 pt-3 border-t border-white/5 flex items-center gap-3">
            <Button
              onClick={handleSave}
              disabled={saving}
              className="bg-emerald-500 text-slate-950 hover:bg-emerald-400"
              data-testid="save-role-btn"
            >
              {saving ? 'Saving...' : 'Save Changes'}
            </Button>
            {selectedRole && editPerms !== selectedRole.permissions && (
              <span className="text-xs text-amber-400 font-mono">Unsaved changes</span>
            )}
          </div>
        </div>
      ) : (
        <div className="flex-1 flex items-center justify-center text-slate-500 text-sm">
          Select a role to edit permissions
        </div>
      )}
    </div>
  );
}
