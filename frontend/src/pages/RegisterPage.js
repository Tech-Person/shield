import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { formatApiError } from '../lib/api';
import { Shield, Eye, EyeOff } from 'lucide-react';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';

export default function RegisterPage() {
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const { register } = useAuth();

  const handleRegister = async (e) => {
    e.preventDefault();
    setError('');
    if (password !== confirmPassword) {
      setError('Passwords do not match');
      return;
    }
    setLoading(true);
    try {
      await register(username, email, password);
      navigate('/app');
    } catch (err) {
      setError(formatApiError(err.response?.data?.detail) || err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#020617] flex items-center justify-center px-4" data-testid="register-page">
      <div className="w-full max-w-md">
        <div className="flex items-center justify-center gap-3 mb-8">
          <Shield className="w-8 h-8 text-emerald-500" />
          <span className="text-2xl font-medium tracking-tight text-slate-50 font-['Outfit']">SecureComm</span>
        </div>

        <div className="bg-slate-900/80 backdrop-blur-2xl border border-white/5 rounded-lg p-8">
          <h2 className="text-xl font-medium text-slate-100 mb-1 font-['Outfit']">Create your account</h2>
          <p className="text-sm text-slate-500 mb-6 font-['IBM_Plex_Sans']">Join the secure communication platform</p>

          {error && (
            <div className="bg-red-500/10 border border-red-500/20 text-red-400 text-sm px-4 py-3 rounded-md mb-4" data-testid="register-error">
              {error}
            </div>
          )}

          <form onSubmit={handleRegister} className="space-y-4">
            <div>
              <Label className="text-slate-300 text-sm">Username</Label>
              <Input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="bg-slate-950/50 border-white/10 text-slate-100 mt-1.5 focus:ring-1 focus:ring-emerald-500/50"
                placeholder="Choose a username"
                required
                minLength={3}
                data-testid="register-username-input"
              />
            </div>
            <div>
              <Label className="text-slate-300 text-sm">Email</Label>
              <Input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="bg-slate-950/50 border-white/10 text-slate-100 mt-1.5 focus:ring-1 focus:ring-emerald-500/50"
                placeholder="you@example.com"
                required
                data-testid="register-email-input"
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
                  placeholder="Min 6 characters"
                  required
                  minLength={6}
                  data-testid="register-password-input"
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
            <div>
              <Label className="text-slate-300 text-sm">Confirm Password</Label>
              <Input
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                className="bg-slate-950/50 border-white/10 text-slate-100 mt-1.5 focus:ring-1 focus:ring-emerald-500/50"
                placeholder="Confirm password"
                required
                data-testid="register-confirm-password-input"
              />
            </div>
            <Button
              type="submit"
              className="w-full bg-emerald-500 text-slate-950 font-medium hover:bg-emerald-400 h-11"
              disabled={loading}
              data-testid="register-submit-btn"
            >
              {loading ? 'Creating account...' : 'Create Account'}
            </Button>
          </form>

          <p className="text-sm text-slate-500 mt-6 text-center font-['IBM_Plex_Sans']">
            Already have an account?{' '}
            <Link to="/login" className="text-emerald-500 hover:text-emerald-400" data-testid="register-login-link">
              Sign in
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
