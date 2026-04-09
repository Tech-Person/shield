import { useState, useEffect, useRef, useCallback } from 'react';
import api from '../lib/api';
import { Mic, MicOff, Video, VideoOff, Monitor, PhoneOff, Settings, Users, Volume2, Maximize2 } from 'lucide-react';
import { Button } from '../components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { ScrollArea } from '../components/ui/scroll-area';
import { playJoinSound, playLeaveSound, createAudioLevelDetector } from '../lib/audio';

export default function VoiceChannel({ channel, server, user, ws, onVoiceJoin, onVoiceLeave }) {
  const [joined, setJoined] = useState(false);
  const [participants, setParticipants] = useState([]);
  const [muted, setMuted] = useState(false);
  const [videoOn, setVideoOn] = useState(false);
  const [screenSharing, setScreenSharing] = useState(false);
  const [videoQuality, setVideoQuality] = useState('720p');
  const [showSettings, setShowSettings] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const localVideoRef = useRef(null);
  const localStreamRef = useRef(null);
  const screenStreamRef = useRef(null);
  const peerConnectionsRef = useRef({});
  const iceServersRef = useRef(null);
  const audioDetectorCleanupRef = useRef(null);

  // Fetch TURN/STUN credentials
  useEffect(() => {
    (async () => {
      try {
        const { data } = await api.get('/turn/credentials');
        iceServersRef.current = data.ice_servers;
      } catch {
        iceServersRef.current = [
          { urls: 'stun:stun.l.google.com:19302' },
          { urls: 'stun:stun1.l.google.com:19302' }
        ];
      }
    })();
  }, []);

  const loadParticipants = useCallback(async () => {
    try {
      const { data } = await api.get(`/channels/${channel.id}/voice-participants`);
      setParticipants(data);
    } catch {}
  }, [channel.id]);

  useEffect(() => {
    loadParticipants();
    const interval = setInterval(loadParticipants, 5000);
    return () => clearInterval(interval);
  }, [loadParticipants]);

  useEffect(() => {
    const websocket = ws?.current;
    if (!websocket) return;
    const handler = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'voice_state_update' && data.channel_id === channel.id) {
          loadParticipants();
          // Play sounds for other users joining/leaving
          if (data.user_joined && data.user_joined !== user.id && joined) playJoinSound();
          if (data.user_left && data.user_left !== user.id && joined) playLeaveSound();
          // Clean up peer connections for users who left
          if (data.user_left) {
            const leftUserId = data.user_left;
            const pc = peerConnectionsRef.current[leftUserId];
            if (pc) { pc.close(); delete peerConnectionsRef.current[leftUserId]; }
            const remoteEl = document.getElementById(`remote-video-${leftUserId}`);
            if (remoteEl) remoteEl.remove();
          }
        }
        if (data.type === 'webrtc_signal' && joined) {
          handleWebRTCSignal(data);
        }
      } catch {}
    };
    websocket.addEventListener('message', handler);
    return () => websocket.removeEventListener('message', handler);
  }, [ws, channel.id, joined, loadParticipants]);

  const handleWebRTCSignal = async (data) => {
    const fromUser = data.from_user_id;
    let pc = peerConnectionsRef.current[fromUser];
    if (!pc) {
      pc = createPeerConnection(fromUser);
      peerConnectionsRef.current[fromUser] = pc;
    }
    const signal = data.signal;
    try {
      if (signal.type === 'offer') {
        await pc.setRemoteDescription(new RTCSessionDescription(signal));
        const answer = await pc.createAnswer();
        await pc.setLocalDescription(answer);
        sendSignal(fromUser, answer);
      } else if (signal.type === 'answer') {
        await pc.setRemoteDescription(new RTCSessionDescription(signal));
      } else if (signal.candidate) {
        await pc.addIceCandidate(new RTCIceCandidate(signal));
      }
    } catch (err) {
      console.error('WebRTC signal error:', err);
    }
  };

  const createPeerConnection = (targetUserId) => {
    const iceConfig = iceServersRef.current || [
      { urls: 'stun:stun.l.google.com:19302' },
      { urls: 'stun:stun1.l.google.com:19302' }
    ];
    const pc = new RTCPeerConnection({ iceServers: iceConfig });
    pc.onicecandidate = (event) => {
      if (event.candidate) {
        sendSignal(targetUserId, event.candidate);
      }
    };
    pc.oniceconnectionstatechange = () => {
      if (pc.iceConnectionState === 'failed' || pc.iceConnectionState === 'disconnected') {
        pc.close();
        delete peerConnectionsRef.current[targetUserId];
      }
    };
    pc.onnegotiationneeded = async () => {
      try {
        const offer = await pc.createOffer();
        await pc.setLocalDescription(offer);
        sendSignal(targetUserId, pc.localDescription);
      } catch {}
    };
    pc.ontrack = (event) => {
      // Create or update remote video element
      const remoteId = `remote-video-${targetUserId}`;
      let videoEl = document.getElementById(remoteId);
      if (!videoEl) {
        videoEl = document.createElement('video');
        videoEl.id = remoteId;
        videoEl.autoplay = true;
        videoEl.playsInline = true;
        videoEl.className = 'w-full h-full object-cover rounded-lg';
        const container = document.getElementById('remote-streams');
        if (container) container.appendChild(videoEl);
      }
      videoEl.srcObject = event.streams[0];
    };
    if (localStreamRef.current) {
      localStreamRef.current.getTracks().forEach(track => {
        pc.addTrack(track, localStreamRef.current);
      });
    }
    return pc;
  };

  const sendSignal = (targetUserId, signal) => {
    const websocket = ws?.current;
    if (websocket?.readyState === WebSocket.OPEN) {
      websocket.send(JSON.stringify({
        type: 'webrtc_signal',
        target_user_id: targetUserId,
        signal
      }));
    }
  };

  const getQualityConstraints = () => {
    const qualities = {
      '480p': { width: 854, height: 480, frameRate: 30 },
      '720p': { width: 1280, height: 720, frameRate: 30 },
      '1080p': { width: 1920, height: 1080, frameRate: 60 },
      '1440p': { width: 2560, height: 1440, frameRate: 60 },
      '2160p': { width: 3840, height: 2160, frameRate: 60 }
    };
    return qualities[videoQuality] || qualities['720p'];
  };

  const joinChannel = async () => {
    if (participants.length >= 10) {
      alert('Voice channel is full (max 10 participants)');
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
      localStreamRef.current = stream;
      ws?.current?.send(JSON.stringify({ type: 'join_voice', channel_id: channel.id }));
      setJoined(true);
      if (onVoiceJoin) onVoiceJoin();
      playJoinSound();
      // Start speaking detection
      audioDetectorCleanupRef.current = createAudioLevelDetector(stream, setSpeaking);
      // Initiate connections to existing participants
      setTimeout(() => {
        participants.forEach(p => {
          if (p.id !== user.id) {
            initiateConnection(p.id);
          }
        });
      }, 500);
    } catch (err) {
      console.error('Failed to get media:', err);
    }
  };

  const initiateConnection = async (targetUserId) => {
    const pc = createPeerConnection(targetUserId);
    peerConnectionsRef.current[targetUserId] = pc;
    try {
      const offer = await pc.createOffer();
      await pc.setLocalDescription(offer);
      sendSignal(targetUserId, offer);
    } catch (err) {
      console.error('Failed to create offer:', err);
    }
  };

  const leaveChannel = () => {
    ws?.current?.send(JSON.stringify({ type: 'leave_voice', channel_id: channel.id }));
    localStreamRef.current?.getTracks().forEach(t => t.stop());
    screenStreamRef.current?.getTracks().forEach(t => t.stop());
    Object.values(peerConnectionsRef.current).forEach(pc => pc.close());
    peerConnectionsRef.current = {};
    localStreamRef.current = null;
    screenStreamRef.current = null;
    if (audioDetectorCleanupRef.current) audioDetectorCleanupRef.current();
    audioDetectorCleanupRef.current = null;
    setSpeaking(false);
    setJoined(false);
    setMuted(false);
    setVideoOn(false);
    setScreenSharing(false);
    if (onVoiceLeave) onVoiceLeave();
    playLeaveSound();
  };

  const toggleMute = () => {
    if (localStreamRef.current) {
      localStreamRef.current.getAudioTracks().forEach(t => { t.enabled = muted; });
      setMuted(!muted);
    }
  };

  const toggleVideo = async () => {
    if (videoOn) {
      localStreamRef.current?.getVideoTracks().forEach(t => { t.stop(); localStreamRef.current.removeTrack(t); });
      if (localVideoRef.current) localVideoRef.current.srcObject = null;
      setVideoOn(false);
    } else {
      try {
        const constraints = getQualityConstraints();
        const videoStream = await navigator.mediaDevices.getUserMedia({ video: { width: { ideal: constraints.width }, height: { ideal: constraints.height }, frameRate: { ideal: constraints.frameRate } } });
        videoStream.getVideoTracks().forEach(t => localStreamRef.current?.addTrack(t));
        if (localVideoRef.current) localVideoRef.current.srcObject = videoStream;
        // Add track to existing peer connections
        Object.values(peerConnectionsRef.current).forEach(pc => {
          videoStream.getVideoTracks().forEach(track => pc.addTrack(track, localStreamRef.current));
        });
        setVideoOn(true);
      } catch (err) {
        console.error('Failed to get video:', err);
      }
    }
  };

  const toggleScreenShare = async () => {
    if (screenSharing) {
      screenStreamRef.current?.getTracks().forEach(t => t.stop());
      screenStreamRef.current = null;
      setScreenSharing(false);
    } else {
      try {
        const constraints = getQualityConstraints();
        const stream = await navigator.mediaDevices.getDisplayMedia({
          video: { width: { ideal: constraints.width }, height: { ideal: constraints.height }, frameRate: { ideal: constraints.frameRate } },
          audio: true
        });
        screenStreamRef.current = stream;
        // Replace video tracks in peer connections
        Object.values(peerConnectionsRef.current).forEach(pc => {
          const senders = pc.getSenders();
          const videoSender = senders.find(s => s.track?.kind === 'video');
          if (videoSender) {
            videoSender.replaceTrack(stream.getVideoTracks()[0]);
          } else {
            stream.getTracks().forEach(track => pc.addTrack(track, stream));
          }
        });
        stream.getVideoTracks()[0].onended = () => {
          setScreenSharing(false);
          screenStreamRef.current = null;
        };
        setScreenSharing(true);
      } catch (err) {
        console.error('Screen share failed:', err);
      }
    }
  };

  return (
    <div className="flex-1 flex flex-col bg-[#020617]" data-testid="voice-channel">
      {/* Header */}
      <div className="h-12 px-4 flex items-center justify-between border-b border-white/5 flex-shrink-0 bg-slate-950/60 backdrop-blur-2xl">
        <div className="flex items-center gap-2">
          <Volume2 className="w-4 h-4 text-emerald-500" />
          <span className="text-sm font-medium text-slate-100 font-['Outfit']">{channel?.name}</span>
          <span className="text-xs text-slate-500 font-mono">{participants.length} connected</span>
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
      <div className="flex-1 p-4">
        {!joined ? (
          <div className="flex flex-col items-center justify-center h-full gap-6">
            <div className="text-center">
              <Volume2 className="w-16 h-16 text-slate-700 mx-auto mb-4" />
              <h3 className="text-xl font-medium text-slate-200 font-['Outfit'] mb-2">{channel?.name}</h3>
              <p className="text-sm text-slate-500">{participants.length} participant{participants.length !== 1 ? 's' : ''} connected</p>
            </div>
            {participants.length > 0 && (
              <div className="flex flex-wrap gap-2 justify-center">
                {participants.map(p => (
                  <div key={p.id} className="flex items-center gap-2 px-3 py-1.5 bg-slate-900/50 rounded-full border border-white/5">
                    <div className="w-6 h-6 rounded-full bg-emerald-500/20 flex items-center justify-center text-[10px] text-emerald-400">{p.username?.slice(0, 2).toUpperCase()}</div>
                    <span className="text-xs text-slate-300">{p.display_name || p.username}</span>
                  </div>
                ))}
              </div>
            )}
            <Button onClick={joinChannel} className="bg-emerald-500 text-slate-950 hover:bg-emerald-400 h-12 px-8" data-testid="join-voice-btn">
              <Mic className="w-4 h-4 mr-2" /> Join Voice Channel
            </Button>
          </div>
        ) : (
          <div className="h-full flex flex-col">
            {/* Video grid */}
            <div className="flex-1 grid grid-cols-2 lg:grid-cols-3 gap-3 mb-4" id="remote-streams">
              {/* Local video */}
              <div className={`relative bg-slate-900/50 rounded-lg border aspect-video flex items-center justify-center overflow-hidden transition-all duration-200 ${speaking ? 'border-emerald-500 shadow-[0_0_12px_rgba(16,185,129,0.3)]' : 'border-white/5'}`}>
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
              {participants.filter(p => p.id !== user.id).map(p => (
                <div key={p.id} className="relative bg-slate-900/50 rounded-lg border border-white/5 aspect-video flex items-center justify-center" data-testid={`participant-${p.id}`}>
                  <div className="flex flex-col items-center gap-2">
                    <div className="w-16 h-16 rounded-full bg-slate-800 flex items-center justify-center text-xl text-slate-300">
                      {p.username?.slice(0, 2).toUpperCase()}
                    </div>
                    <span className="text-xs text-slate-500">{p.display_name || p.username}</span>
                  </div>
                </div>
              ))}
            </div>

            {/* Controls */}
            <div className="flex items-center justify-center gap-3 py-4">
              <button onClick={toggleMute} className={`p-3 rounded-full transition-colors ${muted ? 'bg-red-500/20 text-red-400 hover:bg-red-500/30' : 'bg-slate-800 text-slate-300 hover:bg-slate-700'}`} data-testid="toggle-mute-btn">
                {muted ? <MicOff className="w-5 h-5" /> : <Mic className="w-5 h-5" />}
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
