import { useState } from 'react';
import api from '../lib/api';
import { X, Hash, Volume2, Trash2 } from 'lucide-react';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Button } from '../components/ui/button';

export default function ChannelSettings({ channel, server, onClose, onUpdate }) {
  const [name, setName] = useState(channel?.name || '');
  const [topic, setTopic] = useState(channel?.topic || '');
  const [slowmode, setSlowmode] = useState(channel?.slowmode_seconds || 0);
  const [saving, setSaving] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const handleSave = async () => {
    setSaving(true);
    try {
      await api.put(`/servers/${server.id}/channels/${channel.id}`, {
        name: name.trim(),
        topic,
        slowmode_seconds: parseInt(slowmode) || 0
      });
      if (onUpdate) onUpdate();
      onClose();
    } catch {}
    setSaving(false);
  };

  const handleDelete = async () => {
    try {
      await api.delete(`/servers/${server.id}/channels/${channel.id}`);
      if (onUpdate) onUpdate();
      onClose();
    } catch {}
  };

  return (
    <div className="flex-1 bg-[#020617] overflow-y-auto" data-testid="channel-settings">
      <div className="max-w-2xl mx-auto p-8">
        <div className="flex items-center justify-between mb-8">
          <div className="flex items-center gap-3">
            {channel?.channel_type === 'voice' ? <Volume2 className="w-5 h-5 text-emerald-500" /> : <Hash className="w-5 h-5 text-emerald-500" />}
            <h2 className="text-xl font-medium text-slate-100 font-['Outfit']">Channel Settings — {channel?.name}</h2>
          </div>
          <button onClick={onClose} className="p-2 text-slate-400 hover:text-slate-200 rounded" data-testid="close-channel-settings">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="space-y-6">
          <div>
            <Label className="text-slate-300 text-sm">Channel Name</Label>
            <Input
              value={name}
              onChange={e => setName(e.target.value)}
              className="bg-slate-900 border-white/10 text-slate-100 mt-1.5 max-w-sm"
              data-testid="channel-name-input"
            />
          </div>

          <div>
            <Label className="text-slate-300 text-sm">Topic</Label>
            <Input
              value={topic}
              onChange={e => setTopic(e.target.value)}
              placeholder="Describe this channel..."
              className="bg-slate-900 border-white/10 text-slate-100 mt-1.5 max-w-md"
              data-testid="channel-topic-input"
            />
          </div>

          {channel?.channel_type === 'text' && (
            <div>
              <Label className="text-slate-300 text-sm">Slowmode (seconds)</Label>
              <Input
                type="number"
                value={slowmode}
                onChange={e => setSlowmode(e.target.value)}
                className="bg-slate-900 border-white/10 text-slate-100 mt-1.5 w-32"
                data-testid="channel-slowmode-input"
              />
              <p className="text-xs text-slate-500 mt-1">0 = disabled. Users must wait this many seconds between messages.</p>
            </div>
          )}

          <div className="flex items-center gap-3 pt-4">
            <Button
              onClick={handleSave}
              disabled={saving}
              className="bg-emerald-500 text-slate-950 hover:bg-emerald-400"
              data-testid="save-channel-settings-btn"
            >
              {saving ? 'Saving...' : 'Save Changes'}
            </Button>
            <Button variant="ghost" onClick={onClose} className="text-slate-400">Cancel</Button>
          </div>

          {/* Danger zone */}
          <div className="pt-8 mt-8 border-t border-white/5">
            <h3 className="text-sm font-medium text-red-400 mb-4 font-['Outfit']">Danger Zone</h3>
            {!confirmDelete ? (
              <Button
                variant="outline"
                onClick={() => setConfirmDelete(true)}
                className="border-red-500/30 text-red-400 hover:bg-red-500/10"
                data-testid="delete-channel-btn"
              >
                <Trash2 className="w-4 h-4 mr-2" /> Delete Channel
              </Button>
            ) : (
              <div className="flex items-center gap-3">
                <span className="text-sm text-red-400">Are you sure? This cannot be undone.</span>
                <Button onClick={handleDelete} className="bg-red-500 text-white hover:bg-red-600" data-testid="confirm-delete-channel-btn">
                  Delete
                </Button>
                <Button variant="ghost" onClick={() => setConfirmDelete(false)} className="text-slate-400">Cancel</Button>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
