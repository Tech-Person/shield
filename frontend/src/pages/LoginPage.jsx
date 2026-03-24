import { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { toast } from 'sonner';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Network, Shield, Lock, User } from 'lucide-react';

export default function LoginPage() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const { login } = useAuth();

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!username || !password) {
      toast.error('Please enter username and password');
      return;
    }
    
    setIsLoading(true);
    try {
      await login(username, password);
      toast.success('Login successful');
    } catch (error) {
      const message = error.response?.data?.detail || 'Login failed';
      toast.error(message);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen grid-pattern flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* Logo Section */}
        <div className="text-center mb-8 animate-fade-in">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-sm bg-blue-600/20 border border-blue-500/30 mb-4">
            <Network className="w-8 h-8 text-blue-400" />
          </div>
          <h1 className="text-2xl font-semibold text-white mb-1">Port Forward Manager</h1>
          <p className="text-muted-foreground text-sm">Secure network traffic routing</p>
        </div>

        {/* Login Card */}
        <div className="card-tech p-6 animate-fade-in" style={{ animationDelay: '0.1s' }}>
          <div className="flex items-center gap-2 mb-6 pb-4 border-b border-border">
            <Shield className="w-5 h-5 text-blue-400" />
            <span className="text-sm font-medium text-muted-foreground">AUTHENTICATION REQUIRED</span>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="username" className="text-sm text-muted-foreground">
                Username
              </Label>
              <div className="relative">
                <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                <Input
                  id="username"
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  className="pl-10 bg-zinc-900 border-zinc-700 text-white placeholder:text-zinc-500 focus:ring-blue-500 focus:border-blue-500"
                  placeholder="Enter username"
                  data-testid="login-username-input"
                  autoComplete="username"
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="password" className="text-sm text-muted-foreground">
                Password
              </Label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                <Input
                  id="password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="pl-10 bg-zinc-900 border-zinc-700 text-white placeholder:text-zinc-500 focus:ring-blue-500 focus:border-blue-500"
                  placeholder="Enter password"
                  data-testid="login-password-input"
                  autoComplete="current-password"
                />
              </div>
            </div>

            <Button
              type="submit"
              disabled={isLoading}
              className="w-full bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 rounded-sm transition-colors duration-200 btn-glow"
              data-testid="login-submit-button"
            >
              {isLoading ? (
                <span className="font-mono text-sm">AUTHENTICATING...</span>
              ) : (
                <span className="font-mono text-sm">LOGIN</span>
              )}
            </Button>
          </form>

          <div className="mt-6 pt-4 border-t border-border">
            <p className="text-xs text-center text-muted-foreground font-mono">
              Default: admin / admin
            </p>
          </div>
        </div>

        {/* Footer Info */}
        <div className="mt-6 text-center animate-fade-in" style={{ animationDelay: '0.2s' }}>
          <p className="text-xs text-muted-foreground">
            WireGuard Tunnel Management System
          </p>
          <p className="text-xs text-zinc-600 mt-1 font-mono">
            v1.0.0 | Secure Connection
          </p>
        </div>
      </div>
    </div>
  );
}
