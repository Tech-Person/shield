import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import api, { formatApiError } from '../lib/api';
import { Shield, Eye, EyeOff, Fingerprint } from 'lucide-react';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { arrayBufferToBase64url, base64urlToArrayBuffer } from '../lib/webauthn';

export default function LoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [passkeyLoading, setPasskeyLoading] = useState(false);
  const [requires2FA, setRequires2FA] = useState(false);
  const [tempToken, setTempToken] = useState('');
  const [totpCode, setTotpCode] = useState('');
  const navigate = useNavigate();
  const { login, verify2FA } = useAuth();

  const handleLogin = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const data = await login(email, password);
      if (data.requires_2fa) {
        setRequires2FA(true);
        setTempToken(data.temp_token);
      } else {
        navigate('/app');
      }
    } catch (err) {
      setError(formatApiError(err.response?.data?.detail) || err.message);
    } finally {
      setLoading(false);
    }
  };

  const handle2FA = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await verify2FA(totpCode, tempToken);
      navigate('/app');
    } catch (err) {
      setError(formatApiError(err.response?.data?.detail) || err.message);
    } finally {
      setLoading(false);
    }
  };

  const handlePasskeyLogin = async () => {
    setError('');
    setPasskeyLoading(true);
    try {
      // Start authentication - username optional for discoverable credentials
      const { data: options } = await api.post('/auth/passkey/authenticate/begin', { username: email || null });
      const publicKey = {
        challenge: base64urlToArrayBuffer(options.challenge),
        timeout: options.timeout,
        rpId: options.rpId,
        userVerification: options.userVerification,
        allowCredentials: (options.allowCredentials || []).map(c => ({
          type: c.type,
          id: base64urlToArrayBuffer(c.id),
          transports: c.transports
        }))
      };
      const credential = await navigator.credentials.get({ publicKey });
      const credData = {
        id: arrayBufferToBase64url(credential.rawId),
        rawId: arrayBufferToBase64url(credential.rawId),
        type: credential.type,
        response: {
          authenticatorData: arrayBufferToBase64url(credential.response.authenticatorData),
          clientDataJSON: arrayBufferToBase64url(credential.response.clientDataJSON),
          signature: arrayBufferToBase64url(credential.response.signature),
          userHandle: credential.response.userHandle ? arrayBufferToBase64url(credential.response.userHandle) : null
        }
      };
      const { data } = await api.post('/auth/passkey/authenticate/complete', {
        username: email,
        credential: credData
      });
      if (data.user && data.access_token) {
        window.location.href = '/app';
      }
    } catch (err) {
      const msg = err?.response?.data?.detail || err?.message || 'Passkey authentication failed';
      setError(typeof msg === 'string' ? msg : 'Passkey authentication failed');
    } finally {
      setPasskeyLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#020617] flex items-center justify-center px-4" data-testid="login-page">
      <div className="w-full max-w-md">
        <div className="flex items-center justify-center gap-3 mb-8">
          <Shield className="w-8 h-8 text-emerald-500" />
          <span className="text-2xl font-medium tracking-tight text-slate-50 font-['Outfit']">SecureComm</span>
        </div>

        <div className="bg-slate-900/80 backdrop-blur-2xl border border-white/5 rounded-lg p-8">
          <h2 className="text-xl font-medium text-slate-100 mb-1 font-['Outfit']">
            {requires2FA ? 'Two-Factor Authentication' : 'Welcome back'}
          </h2>
          <p className="text-sm text-slate-500 mb-6 font-['IBM_Plex_Sans']">
            {requires2FA ? 'Enter your 2FA code to continue' : 'Sign in to your account'}
          </p>

          {error && (
            <div className="bg-red-500/10 border border-red-500/20 text-red-400 text-sm px-4 py-3 rounded-md mb-4" data-testid="login-error">
              {error}
            </div>
          )}

          {!requires2FA ? (
            <form onSubmit={handleLogin} className="space-y-4">
              <div>
                <Label className="text-slate-300 text-sm">Email</Label>
                <Input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="bg-slate-950/50 border-white/10 text-slate-100 mt-1.5 focus:ring-1 focus:ring-emerald-500/50"
                  placeholder="you@example.com"
                  required
                  data-testid="login-email-input"
                />
              </div>
              <div>
                <Label className="text-slate-300 text-sm">Password</Label>
                <div className="relative mt-1.5">
                  <Input
                    type={showPassword ? 'text' : 'password'}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="bg-slate-950/50 border-white/10 text-slate-100 pr-10 focus:ring-1 focus:ring-emerald-500/50"
                    placeholder="Enter password"
                    required
                    data-testid="login-password-input"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300"
                  >
                    {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>
              <Button
                type="submit"
                className="w-full bg-emerald-500 text-slate-950 font-medium hover:bg-emerald-400 h-11"
                disabled={loading}
                data-testid="login-submit-btn"
              >
                {loading ? 'Signing in...' : 'Sign In'}
              </Button>

              <div className="relative my-2">
                <div className="absolute inset-0 flex items-center"><div className="w-full border-t border-white/5" /></div>
                <div className="relative flex justify-center text-xs"><span className="bg-slate-900/80 px-3 text-slate-500">or</span></div>
              </div>

              <Button
                type="button"
                variant="outline"
                className="w-full border-slate-700 text-slate-300 hover:bg-slate-800 hover:text-white h-11"
                onClick={handlePasskeyLogin}
                disabled={passkeyLoading}
                data-testid="login-passkey-btn"
              >
                <Fingerprint className="w-4 h-4 mr-2" />
                {passkeyLoading ? 'Authenticating...' : 'Sign in with Passkey'}
              </Button>
            </form>
          ) : (
            <form onSubmit={handle2FA} className="space-y-4">
              <div>
                <Label className="text-slate-300 text-sm">Authentication Code</Label>
                <Input
                  type="text"
                  value={totpCode}
                  onChange={(e) => setTotpCode(e.target.value)}
                  className="bg-slate-950/50 border-white/10 text-slate-100 mt-1.5 text-center text-2xl tracking-[0.5em] font-mono focus:ring-1 focus:ring-emerald-500/50"
                  placeholder="000000"
                  maxLength={6}
                  required
                  data-testid="login-2fa-input"
                />
              </div>
              <Button
                type="submit"
                className="w-full bg-emerald-500 text-slate-950 font-medium hover:bg-emerald-400 h-11"
                disabled={loading}
                data-testid="login-2fa-submit-btn"
              >
                {loading ? 'Verifying...' : 'Verify'}
              </Button>
            </form>
          )}

          <p className="text-sm text-slate-500 mt-6 text-center font-['IBM_Plex_Sans']">
            Don't have an account?{' '}
            <Link to="/register" className="text-emerald-500 hover:text-emerald-400" data-testid="login-register-link">
              Create one
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
