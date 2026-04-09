import { Shield, Lock, MessageCircle, Users, ArrowRight } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Button } from '../components/ui/button';

export default function LandingPage() {
  const navigate = useNavigate();
  const { user } = useAuth();

  if (user) {
    navigate('/app');
    return null;
  }

  return (
    <div className="min-h-screen bg-[#020617] text-slate-50 overflow-hidden" data-testid="landing-page">
      <div className="absolute inset-0 bg-[url('https://images.unsplash.com/photo-1761078739436-ccee01f3d89c?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NTYxOTJ8MHwxfHNlYXJjaHwyfHxhYnN0cmFjdCUyMGRhcmslMjB0ZXh0dXJlfGVufDB8fHx8MTc3NTY1MTIwOXww&ixlib=rb-4.1.0&q=85')] bg-cover bg-center opacity-20" />
      <div className="absolute inset-0 bg-gradient-to-b from-[#020617]/80 via-[#020617]/90 to-[#020617]" />

      <div className="relative z-10">
        <nav className="flex items-center justify-between px-8 py-6 max-w-7xl mx-auto">
          <div className="flex items-center gap-3">
            <Shield className="w-8 h-8 text-emerald-500" />
            <span className="text-xl font-medium tracking-tight font-['Outfit']">Shield</span>
          </div>
          <div className="flex items-center gap-4">
            <Button variant="ghost" className="text-slate-300 hover:text-white hover:bg-slate-800/50" onClick={() => navigate('/login')} data-testid="nav-login-btn">
              Sign In
            </Button>
            <Button className="bg-emerald-500 text-slate-950 font-medium hover:bg-emerald-400" onClick={() => navigate('/register')} data-testid="nav-register-btn">
              Get Started
            </Button>
          </div>
        </nav>

        <main className="max-w-7xl mx-auto px-8 pt-24 pb-32">
          <div className="max-w-3xl">
            <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full border border-emerald-500/30 bg-emerald-500/10 text-emerald-400 text-xs font-mono uppercase tracking-widest mb-8">
              <Lock className="w-3 h-3" />
              End-to-End Encrypted
            </div>
            <h1 className="text-4xl sm:text-5xl lg:text-6xl font-medium tracking-tighter text-slate-50 leading-[1.1] mb-6 font-['Outfit']">
              Communication that
              <br />
              <span className="text-emerald-500">respects your privacy</span>
            </h1>
            <p className="text-base sm:text-lg text-slate-400 max-w-xl mb-10 leading-relaxed font-['IBM_Plex_Sans']">
              A self-hosted, encrypted communication platform. Create servers, chat in channels, make calls, and share files — all with zero-knowledge encryption.
            </p>
            <div className="flex items-center gap-4">
              <Button
                className="bg-emerald-500 text-slate-950 font-medium hover:bg-emerald-400 h-12 px-8 text-base"
                onClick={() => navigate('/register')}
                data-testid="hero-get-started-btn"
              >
                Get Started <ArrowRight className="w-4 h-4 ml-2" />
              </Button>
              <Button
                variant="outline"
                className="border-slate-700 text-slate-300 hover:bg-slate-800 hover:text-white h-12 px-8 text-base"
                onClick={() => navigate('/login')}
                data-testid="hero-sign-in-btn"
              >
                Sign In
              </Button>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mt-32">
            {[
              { icon: Lock, title: 'Encrypted at Rest', desc: 'All messages and files are encrypted using AES-256 before storage. Your data stays private.' },
              { icon: MessageCircle, title: 'Real-time Messaging', desc: 'Instant messaging via WebSocket. DMs, group chats, and server channels with full history.' },
              { icon: Users, title: 'Self-Hosted Servers', desc: 'Create and manage your own servers with roles, permissions, channels, and shared drives.' }
            ].map((f, i) => (
              <div key={i} className="p-6 bg-slate-900/50 border border-white/5 rounded-lg hover:border-emerald-500/20 transition-colors group">
                <f.icon className="w-8 h-8 text-emerald-500 mb-4 group-hover:scale-110 transition-transform" />
                <h3 className="text-lg font-medium text-slate-100 mb-2 font-['Outfit']">{f.title}</h3>
                <p className="text-sm text-slate-400 leading-relaxed font-['IBM_Plex_Sans']">{f.desc}</p>
              </div>
            ))}
          </div>
        </main>
      </div>
    </div>
  );
}
