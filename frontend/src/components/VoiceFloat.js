import { Mic, MicOff, Volume2, VolumeX, PhoneOff } from 'lucide-react';

export default function VoiceFloat({ voiceManager, onNavigateToChannel }) {
  const { joined, channelInfo, muted, deafened, speaking, toggleMute, toggleDeafen, leaveChannel } = voiceManager;

  if (!joined || !channelInfo) return null;

  return (
    <div
      className="fixed bottom-4 left-20 z-50 bg-slate-900/95 backdrop-blur-xl border border-white/10 rounded-xl shadow-2xl shadow-black/50 overflow-hidden"
      data-testid="voice-float"
      style={{ width: '240px' }}
    >
      {/* Connection status */}
      <div
        className="px-3 py-2 flex items-center gap-2 cursor-pointer hover:bg-white/5 transition-colors"
        onClick={onNavigateToChannel}
        data-testid="voice-float-channel-link"
      >
        <div className={`w-2 h-2 rounded-full flex-shrink-0 ${speaking ? 'bg-emerald-400 animate-pulse' : 'bg-emerald-500'}`} />
        <div className="flex-1 min-w-0">
          <p className="text-xs font-medium text-emerald-400 font-['IBM_Plex_Sans'] truncate">Voice Connected</p>
          <p className="text-[11px] text-slate-400 truncate">{channelInfo.name}</p>
        </div>
      </div>

      {/* Controls */}
      <div className="px-3 py-2 flex items-center justify-between border-t border-white/5">
        <div className="flex items-center gap-1">
          <button
            onClick={toggleMute}
            className={`p-1.5 rounded-md transition-colors ${muted ? 'bg-red-500/20 text-red-400' : 'text-slate-400 hover:text-slate-200 hover:bg-white/5'}`}
            data-testid="voice-float-mute-btn"
            title={muted ? 'Unmute' : 'Mute'}
          >
            {muted ? <MicOff className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
          </button>
          <button
            onClick={toggleDeafen}
            className={`p-1.5 rounded-md transition-colors ${deafened ? 'bg-orange-500/20 text-orange-400' : 'text-slate-400 hover:text-slate-200 hover:bg-white/5'}`}
            data-testid="voice-float-deafen-btn"
            title={deafened ? 'Undeafen' : 'Deafen'}
          >
            {deafened ? <VolumeX className="w-4 h-4" /> : <Volume2 className="w-4 h-4" />}
          </button>
        </div>
        <button
          onClick={leaveChannel}
          className="p-1.5 rounded-md bg-red-500/20 text-red-400 hover:bg-red-500/30 transition-colors"
          data-testid="voice-float-disconnect-btn"
          title="Disconnect"
        >
          <PhoneOff className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}
