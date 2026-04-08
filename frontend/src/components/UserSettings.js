import { useState } from 'react';
import api from '../lib/api';
import { useAuth } from '../contexts/AuthContext';
import { X, Shield, Key, User, Bell, Monitor } from 'lucide-react';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Button } from '../components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Switch } from '../components/ui/switch';

export default function UserSettings({ onClose }) {
  const { user, setUser } = useAuth();
  const [displayName, setDisplayName] = useState(user?.display_name || '');
  const [about, setAbout] = useState(user?.about || '');
  const [status, setStatus] = useState(user?.status || 'online');
  const [statusMessage, setStatusMessage] = useState(user?.status_message || '');
  const [statusExpiry, setStatusExpiry] = useState(60);
  const [saving, setSaving] = useState(false);
  const [show2FA, setShow2FA] = useState(false);
  const [qrCode, setQrCode] = useState('');
  const [totpCode, setTotpCode] = useState('');

  const handleSaveProfile = async () => {
    setSaving(true);
    try {
      const { data } = await api.put('/users/me', { display_name: displayName, about });
      setUser(prev => ({ ...prev, ...data }));
    } catch {}
    setSaving(false);
  };

  const handleStatusChange = async (newStatus) => {
    setStatus(newStatus);
    try {
      await api.put('/users/me/status', {
        status: newStatus,
        status_message: statusMessage || null,
        status_expires_minutes: statusMessage ? statusExpiry : null
      });
    } catch {}
  };

  const handleSetup2FA = async () => {
    try {
      const { data } = await api.post('/auth/setup-2fa');
      setQrCode(data.qr_code);
      setShow2FA(true);
    } catch {}
  };

  const handleConfirm2FA = async () => {
    try {
      await api.post('/auth/confirm-2fa', { code: totpCode });
      setShow2FA(false);
      setUser(prev => ({ ...prev, totp_enabled: true }));
    } catch {}
  };

  return (
    <div className="flex-1 flex flex-col bg-[#020617]" data-testid="user-settings">
      <div className="h-12 px-6 flex items-center justify-between border-b border-white/5 flex-shrink-0">
        <span className="text-sm font-medium text-slate-100 font-['Outfit']">User Settings</span>
        <button onClick={onClose} className="text-slate-400 hover:text-slate-200" data-testid="close-settings-btn">
          <X className="w-5 h-5" />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-8 max-w-2xl">
        {/* Profile */}
        <section className="mb-8">
          <h3 className="text-lg font-medium text-slate-100 mb-4 flex items-center gap-2 font-['Outfit']">
            <User className="w-5 h-5 text-emerald-500" /> Profile
          </h3>
          <div className="space-y-4">
            <div>
              <Label className="text-slate-300 text-sm">Display Name</Label>
              <Input value={displayName} onChange={e => setDisplayName(e.target.value)} className="bg-slate-900 border-white/10 text-slate-100 mt-1.5 max-w-sm" data-testid="settings-display-name" />
            </div>
            <div>
              <Label className="text-slate-300 text-sm">About</Label>
              <Input value={about} onChange={e => setAbout(e.target.value)} className="bg-slate-900 border-white/10 text-slate-100 mt-1.5 max-w-sm" data-testid="settings-about" />
            </div>
            <Button onClick={handleSaveProfile} disabled={saving} className="bg-emerald-500 text-slate-950 hover:bg-emerald-400" data-testid="save-profile-btn">
              {saving ? 'Saving...' : 'Save Profile'}
            </Button>
          </div>
        </section>

        {/* Status */}
        <section className="mb-8">
          <h3 className="text-lg font-medium text-slate-100 mb-4 flex items-center gap-2 font-['Outfit']">
            <Monitor className="w-5 h-5 text-emerald-500" /> Status
          </h3>
          <div className="space-y-4">
            <div>
              <Label className="text-slate-300 text-sm">Status</Label>
              <Select value={status} onValueChange={handleStatusChange}>
                <SelectTrigger className="bg-slate-900 border-white/10 text-slate-100 max-w-sm mt-1.5" data-testid="status-select">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="bg-slate-900 border-white/10">
                  <SelectItem value="online"><span className="flex items-center gap-2"><span className="w-2 h-2 rounded-full bg-emerald-500" /> Online</span></SelectItem>
                  <SelectItem value="away"><span className="flex items-center gap-2"><span className="w-2 h-2 rounded-full bg-amber-500" /> Away</span></SelectItem>
                  <SelectItem value="busy"><span className="flex items-center gap-2"><span className="w-2 h-2 rounded-full bg-red-500" /> Busy</span></SelectItem>
                  <SelectItem value="invisible"><span className="flex items-center gap-2"><span className="w-2 h-2 rounded-full bg-slate-600" /> Invisible</span></SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label className="text-slate-300 text-sm">Status Message</Label>
              <Input value={statusMessage} onChange={e => setStatusMessage(e.target.value)} placeholder="What are you up to?" className="bg-slate-900 border-white/10 text-slate-100 mt-1.5 max-w-sm" data-testid="status-message-input" />
            </div>
            <div>
              <Label className="text-slate-300 text-sm">Expires in (minutes)</Label>
              <Input type="number" value={statusExpiry} onChange={e => setStatusExpiry(parseInt(e.target.value) || 60)} className="bg-slate-900 border-white/10 text-slate-100 mt-1.5 w-32" data-testid="status-expiry-input" />
            </div>
          </div>
        </section>

        {/* 2FA */}
        <section className="mb-8">
          <h3 className="text-lg font-medium text-slate-100 mb-4 flex items-center gap-2 font-['Outfit']">
            <Key className="w-5 h-5 text-emerald-500" /> Two-Factor Authentication
          </h3>
          {user?.totp_enabled ? (
            <div className="flex items-center gap-3 p-4 bg-emerald-500/10 border border-emerald-500/20 rounded">
              <Shield className="w-5 h-5 text-emerald-500" />
              <span className="text-sm text-emerald-400">2FA is enabled</span>
            </div>
          ) : show2FA ? (
            <div className="space-y-4">
              {qrCode && <img src={qrCode} alt="2FA QR Code" className="w-48 h-48 rounded bg-white p-2" data-testid="2fa-qr-code" />}
              <p className="text-sm text-slate-400">Scan this QR code with your authenticator app, then enter the code below.</p>
              <Input value={totpCode} onChange={e => setTotpCode(e.target.value)} placeholder="Enter 6-digit code" className="bg-slate-900 border-white/10 text-slate-100 max-w-xs font-mono tracking-widest text-center" data-testid="2fa-confirm-input" />
              <Button onClick={handleConfirm2FA} className="bg-emerald-500 text-slate-950 hover:bg-emerald-400" data-testid="2fa-confirm-btn">
                Confirm & Enable
              </Button>
            </div>
          ) : (
            <Button onClick={handleSetup2FA} className="bg-slate-800 text-slate-100 border border-white/5 hover:bg-slate-700" data-testid="setup-2fa-btn">
              <Key className="w-4 h-4 mr-2" /> Setup 2FA
            </Button>
          )}
        </section>
      </div>
    </div>
  );
}
