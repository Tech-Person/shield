import { useState, useEffect, useRef } from 'react';
import api from '../lib/api';
import { Mic, MicOff, Video, VideoOff, Monitor, PhoneOff, Settings, Volume2, VolumeX, LogIn, LogOut, Wifi } from 'lucide-react';
import { Button } from '../components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';

export default function VoiceChannel({ channel, server, user, voiceManager }) {
  const [videoQuality, setVideoQuality] = useState('720p');
  const [showSettings, setShowSettings] = useState(false);
  const [viewParticipants, setViewParticipants] = useState([]);
  const localVideoRef = useRef(null);

  const {
    joined,
    channelInfo,
    participants,
    muted,
    deafened,
    videoOn,
    screenSharing,
    speaking,
    speakingUsers,
    voiceEvents,
    ping,
    localStreamRef,
    screenStreamRef,
    remoteStreamsRef,
    remoteStreamVersion,
    joinChannel,
    leaveChannel,
    toggleMute,
    toggleDeafen,
    toggleVideo,
    toggleScreenShare
  } = voiceManager;

  // Whether THIS channel is the one we're connected to
  const isActiveVoice = joined && channelInfo?.id === channel?.id;

  // Load participants independently when viewing a channel we haven't joined
  useEffect(() => {
    if (isActiveVoice) return;
    let cancelled = false;
    const load = async () => {
      try {
        const { data } = await api.get(`/channels/${channel.id}/voice-participants`);
        if (!cancelled) setViewParticipants(data);
      } catch {}
    };
    load();
    const interval = setInterval(load, 5000);
    return () => { cancelled = true; clearInterval(interval); };
  }, [channel?.id, isActiveVoice]);

  const displayParticipants = isActiveVoice ? participants : viewParticipants;

  // Sync local video element when viewing active voice channel
  useEffect(() => {
    if (!isActiveVoice || !localVideoRef.current) return;
    if (videoOn && localStreamRef.current) {
      localVideoRef.current.srcObject = localStreamRef.current;
    } else if (screenSharing && screenStreamRef.current) {
      localVideoRef.current.srcObject = screenStreamRef.current;
    } else {
      localVideoRef.current.srcObject = null;
    }
  }, [isActiveVoice, videoOn, screenSharing]);

  // Sync remote video elements when streams arrive
  useEffect(() => {
    if (!isActiveVoice) return;
    participants.forEach(p => {
      if (p.id !== user?.id) {
        const stream = remoteStreamsRef.current[p.id];
        const videoEl = document.getElementById(`remote-video-${p.id}`);
        if (stream && videoEl) {
          if (videoEl.srcObject !== stream) videoEl.srcObject = stream;
          if (stream.getVideoTracks().length > 0) {
            videoEl.classList.remove('hidden');
          }
        }
      }
    });
  }, [isActiveVoice, participants, remoteStreamVersion, user?.id]);

  const handleJoin = () => {
    if (displayParticipants.length >= 10) {
      alert('Voice channel is full (max 10 participants)');
      return;
    }
    joinChannel(channel, server?.id);
  };

  const getPingColor = (ms) => {
    if (ms == null) return 'text-slate-500';
    if (ms < 80) return 'text-emerald-400';
    if (ms < 150) return 'text-amber-400';
    return 'text-red-400';
  };

  return (
    <div className="flex-1 flex flex-col bg-[#020617]" data-testid="voice-channel">
      {/* Header */}
      <div className="h-12 px-4 flex items-center justify-between border-b border-white/5 flex-shrink-0 bg-slate-950/60 backdrop-blur-2xl">
        <div className="flex items-center gap-2">
          <Volume2 className="w-4 h-4 text-emerald-500" />
          <span className="text-sm font-medium text-slate-100 font-['Outfit']">{channel?.name}</span>
          <span className="text-xs text-slate-500 font-mono">{displayParticipants.length} connected</span>
        </div>
        <button onClick={() => setShowSettings(!showSettings)} className="p-2 text-slate-400 hover:text-slate-200" data-testid="voice-settings-btn">
          <Settings className="w-4 h-4" />
        </button>
      </div>

      {/* Settings panel */}
      {showSettings && (
        <div className="px-4 py-3 border-b border-white/5 bg-slate-900/50" data-testid="voice-settings-panel">
          <div className="flex items-center gap-4">
            <div>
              <label className="text-xs font-mono uppercase tracking-widest text-slate-500 block mb-1">Video Quality</label>
              <Select value={videoQuality} onValueChange={setVideoQuality}>
                <SelectTrigger className="bg-slate-950/50 border-white/10 text-slate-100 w-32" data-testid="quality-select">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="bg-slate-900 border-white/10">
                  <SelectItem value="480p">480p 30fps</SelectItem>
                  <SelectItem value="720p">720p 30fps</SelectItem>
                  <SelectItem value="1080p">1080p 60fps</SelectItem>
                  <SelectItem value="1440p">1440p 60fps</SelectItem>
                  <SelectItem value="2160p">2160p 60fps</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        </div>
      )}

      {/* Video grid / participants */}
      <div className="flex-1 p-4 relative">
        {/* Voice events feed (join/leave toasts) */}
        {isActiveVoice && voiceEvents.length > 0 && (
          <div className="absolute top-4 left-1/2 -translate-x-1/2 z-10 flex flex-col gap-1.5" data-testid="voice-events-feed">
            {voiceEvents.map(evt => (
              <div
                key={evt.id}
                className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-['IBM_Plex_Sans'] backdrop-blur-md animate-in fade-in slide-in-from-top-2 duration-300 ${
                  evt.type === 'join'
                    ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/20'
                    : 'bg-red-500/15 text-red-400 border border-red-500/20'
                }`}
              >
                {evt.type === 'join' ? <LogIn className="w-3 h-3" /> : <LogOut className="w-3 h-3" />}
                <span><strong>{evt.name}</strong> {evt.type === 'join' ? 'joined' : 'left'} the channel</span>
              </div>
            ))}
          </div>
        )}

        {!isActiveVoice ? (
          <div className="flex flex-col items-center justify-center h-full gap-6">
            <div className="text-center">
              <Volume2 className="w-16 h-16 text-slate-700 mx-auto mb-4" />
              <h3 className="text-xl font-medium text-slate-200 font-['Outfit'] mb-2">{channel?.name}</h3>
              <p className="text-sm text-slate-500">{displayParticipants.length} participant{displayParticipants.length !== 1 ? 's' : ''} connected</p>
            </div>
            {displayParticipants.length > 0 && (
              <div className="flex flex-wrap gap-2 justify-center">
                {displayParticipants.map(p => (
                  <div key={p.id} className="flex items-center gap-2 px-3 py-1.5 bg-slate-900/50 rounded-full border border-white/5">
                    <div className="w-6 h-6 rounded-full bg-emerald-500/20 flex items-center justify-center text-[10px] text-emerald-400">{p.username?.slice(0, 2).toUpperCase()}</div>
                    <span className="text-xs text-slate-300">{p.display_name || p.username}</span>
                  </div>
                ))}
              </div>
            )}
            {!joined ? (
              <Button onClick={handleJoin} className="bg-emerald-500 text-slate-950 hover:bg-emerald-400 h-12 px-8" data-testid="join-voice-btn">
                <Mic className="w-4 h-4 mr-2" /> Join Voice Channel
              </Button>
            ) : (
              <p className="text-sm text-amber-400/70 font-['IBM_Plex_Sans']">
                You're connected to <strong>{channelInfo?.name}</strong>. Disconnect first to join this channel.
              </p>
            )}
          </div>
        ) : (
          <div className="h-full flex flex-col">
            {/* Video grid */}
            <div className="flex-1 grid grid-cols-2 lg:grid-cols-3 gap-3 mb-4">
              {/* Local video */}
              <div className={`relative bg-slate-900/50 rounded-lg border-2 aspect-video flex items-center justify-center overflow-hidden transition-all duration-200 ${speaking ? 'border-emerald-500 shadow-[0_0_12px_rgba(16,185,129,0.3)]' : 'border-white/5'}`}>
                {videoOn || screenSharing ? (
                  <video ref={localVideoRef} autoPlay muted playsInline className="w-full h-full object-cover" data-testid="local-video" />
                ) : (
                  <div className="flex flex-col items-center gap-2">
                    <div className="w-16 h-16 rounded-full bg-slate-800 flex items-center justify-center text-xl text-slate-300">
                      {user?.username?.slice(0, 2).toUpperCase()}
                    </div>
                    <span className="text-xs text-slate-500">{user?.username} (You)</span>
                  </div>
                )}
                {muted && <div className="absolute top-2 right-2 p-1 bg-red-500/20 rounded"><MicOff className="w-3 h-3 text-red-400" /></div>}
                {screenSharing && <div className="absolute top-2 left-2 px-2 py-0.5 bg-emerald-500/20 rounded text-[10px] text-emerald-400 font-mono">SHARING</div>}
              </div>
              {/* Remote participants */}
              {participants.filter(p => p.id !== user?.id).map(p => {
                const isRemoteSpeaking = speakingUsers[p.id];
                return (
                  <div
                    key={p.id}
                    className={`relative bg-slate-900/50 rounded-lg border-2 aspect-video flex items-center justify-center overflow-hidden transition-all duration-200 ${
                      isRemoteSpeaking ? 'border-emerald-500 shadow-[0_0_12px_rgba(16,185,129,0.3)]' : 'border-white/5'
                    }`}
                    data-testid={`participant-${p.id}`}
                  >
                    <video id={`remote-video-${p.id}`} autoPlay playsInline className="w-full h-full object-cover absolute inset-0 hidden" />
                    <div className="flex flex-col items-center gap-2">
                      <div className={`w-16 h-16 rounded-full flex items-center justify-center text-xl transition-colors duration-200 ${
                        isRemoteSpeaking ? 'bg-emerald-500/20 text-emerald-300' : 'bg-slate-800 text-slate-300'
                      }`}>
                        {p.username?.slice(0, 2).toUpperCase()}
                      </div>
                      <span className="text-xs text-slate-500">{p.display_name || p.username}</span>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Ping display */}
            <div className="flex items-center justify-center gap-1.5 pb-1" data-testid="ping-display">
              <Wifi className={`w-3 h-3 ${getPingColor(ping)}`} />
              <span className={`text-xs font-mono ${getPingColor(ping)}`}>
                {ping != null ? `${ping} ms` : 'Measuring...'}
              </span>
            </div>

            {/* Controls */}
            <div className="flex items-center justify-center gap-3 py-3">
              <button onClick={toggleMute} className={`p-3 rounded-full transition-colors ${muted ? 'bg-red-500/20 text-red-400 hover:bg-red-500/30' : 'bg-slate-800 text-slate-300 hover:bg-slate-700'}`} data-testid="toggle-mute-btn">
                {muted ? <MicOff className="w-5 h-5" /> : <Mic className="w-5 h-5" />}
              </button>
              <button onClick={toggleDeafen} className={`p-3 rounded-full transition-colors ${deafened ? 'bg-orange-500/20 text-orange-400 hover:bg-orange-500/30' : 'bg-slate-800 text-slate-300 hover:bg-slate-700'}`} data-testid="toggle-deafen-btn">
                {deafened ? <VolumeX className="w-5 h-5" /> : <Volume2 className="w-5 h-5" />}
              </button>
              <button onClick={toggleVideo} className={`p-3 rounded-full transition-colors ${videoOn ? 'bg-emerald-500/20 text-emerald-400 hover:bg-emerald-500/30' : 'bg-slate-800 text-slate-300 hover:bg-slate-700'}`} data-testid="toggle-video-btn">
                {videoOn ? <Video className="w-5 h-5" /> : <VideoOff className="w-5 h-5" />}
              </button>
              <button onClick={toggleScreenShare} className={`p-3 rounded-full transition-colors ${screenSharing ? 'bg-emerald-500/20 text-emerald-400 hover:bg-emerald-500/30' : 'bg-slate-800 text-slate-300 hover:bg-slate-700'}`} data-testid="toggle-screen-share-btn">
                <Monitor className="w-5 h-5" />
              </button>
              <button onClick={leaveChannel} className="p-3 rounded-full bg-red-500/20 text-red-400 hover:bg-red-500/30 transition-colors" data-testid="leave-voice-btn">
                <PhoneOff className="w-5 h-5" />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
