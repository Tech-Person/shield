import { useState, useEffect, useRef, useCallback } from 'react';
import api from '../lib/api';
import { Phone, PhoneOff, Video, VideoOff, Mic, MicOff } from 'lucide-react';
import { playJoinSound, playLeaveSound, playRingtone, stopRingtone, playDialtone, stopDialtone } from '../lib/audio';

const RING_TIMEOUT_MS = 30000;

export default function DMCall({ conversation, user, ws, callData, onCallEnd }) {
  const [status, setStatus] = useState(callData?.status || 'ringing');
  const [muted, setMuted] = useState(false);
  const [videoOn, setVideoOn] = useState(false);
  const [remoteStream, setRemoteStream] = useState(null);
  const [ringElapsed, setRingElapsed] = useState(0);
  const localStreamRef = useRef(null);
  const localVideoRef = useRef(null);
  const remoteVideoRef = useRef(null);
  const pcRef = useRef(null);
  const callIdRef = useRef(callData?.call_id || callData?.id);
  const isInitiator = callData?.initiator_id === user.id || callData?.caller_id === user.id;
  const ringStartRef = useRef(Date.now());

  // ─── Ringing audio ───
  useEffect(() => {
    if (status !== 'ringing') return;
    if (isInitiator) {
      playDialtone();
    } else {
      playRingtone();
      // Browser notification for incoming call
      if (document.hidden && 'Notification' in window && Notification.permission === 'granted') {
        const otherName = conversation?.other_user?.display_name || conversation?.other_user?.username || 'Someone';
        const n = new Notification('Incoming Call', {
          body: `${otherName} is calling you`,
          icon: '/favicon.ico',
          tag: 'shield-call',
          requireInteraction: true,
        });
        n.onclick = () => { window.focus(); n.close(); };
      }
    }
    return () => { stopRingtone(); stopDialtone(); };
  }, [status, isInitiator, conversation]);

  // ─── Ring countdown & auto-timeout ───
  useEffect(() => {
    if (status !== 'ringing') return;
    ringStartRef.current = Date.now();
    const tick = setInterval(() => {
      const elapsed = Date.now() - ringStartRef.current;
      setRingElapsed(elapsed);
      if (elapsed >= RING_TIMEOUT_MS) {
        clearInterval(tick);
        if (isInitiator) {
          handleEndCall();
        } else {
          handleDecline();
        }
      }
    }, 1000);
    return () => clearInterval(tick);
  }, [status]);

  // ─── Request notification permission ───
  useEffect(() => {
    if ('Notification' in window && Notification.permission === 'default') {
      Notification.requestPermission();
    }
  }, []);

  const getIceServers = useCallback(async () => {
    try {
      const { data } = await api.get('/turn/credentials');
      return data.ice_servers;
    } catch {
      return [{ urls: 'stun:stun.l.google.com:19302' }];
    }
  }, []);

  const setupPeerConnection = useCallback(async () => {
    const iceServers = await getIceServers();
    const pc = new RTCPeerConnection({ iceServers });
    pcRef.current = pc;

    pc.onicecandidate = (e) => {
      if (e.candidate && ws?.current?.readyState === WebSocket.OPEN) {
        const otherId = conversation.participants.find(p => p !== user.id);
        ws.current.send(JSON.stringify({
          type: 'webrtc_signal',
          target_user_id: otherId,
          signal: { candidate: e.candidate }
        }));
      }
    };

    pc.ontrack = (e) => setRemoteStream(e.streams[0]);

    pc.oniceconnectionstatechange = () => {
      if (pc.iceConnectionState === 'failed' || pc.iceConnectionState === 'disconnected') {
        handleEndCall();
      }
    };

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
      localStreamRef.current = stream;
      stream.getTracks().forEach(t => pc.addTrack(t, stream));
    } catch (err) {
      console.error('Media access failed:', err);
    }

    return pc;
  }, [ws, conversation, user.id, getIceServers]);

  // Handle incoming WebRTC signals
  useEffect(() => {
    const websocket = ws?.current;
    if (!websocket) return;

    const handler = async (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'webrtc_signal' && pcRef.current) {
          const signal = data.signal;
          if (signal.sdp) {
            await pcRef.current.setRemoteDescription(new RTCSessionDescription(signal.sdp));
            if (signal.sdp.type === 'offer') {
              const answer = await pcRef.current.createAnswer();
              await pcRef.current.setLocalDescription(answer);
              const otherId = conversation.participants.find(p => p !== user.id);
              websocket.send(JSON.stringify({
                type: 'webrtc_signal',
                target_user_id: otherId,
                signal: { sdp: pcRef.current.localDescription }
              }));
            }
          } else if (signal.candidate) {
            await pcRef.current.addIceCandidate(new RTCIceCandidate(signal.candidate));
          }
        } else if (data.type === 'call_answered') {
          stopDialtone();
          stopRingtone();
          setStatus('active');
          playJoinSound();
        } else if (data.type === 'call_declined' || data.type === 'call_ended') {
          stopDialtone();
          stopRingtone();
          setStatus('ended');
          playLeaveSound();
          setTimeout(() => onCallEnd(), 1500);
        }
      } catch {}
    };

    websocket.addEventListener('message', handler);
    return () => websocket.removeEventListener('message', handler);
  }, [ws, conversation, user.id, onCallEnd]);

  useEffect(() => {
    if (remoteVideoRef.current && remoteStream) {
      remoteVideoRef.current.srcObject = remoteStream;
    }
  }, [remoteStream]);

  const handleAnswer = async () => {
    try {
      stopRingtone();
      await api.post(`/dm/call/${callIdRef.current}/answer`);
      await setupPeerConnection();
      setStatus('active');
      playJoinSound();
    } catch {}
  };

  const handleStartCall = async () => {
    const pc = await setupPeerConnection();
    const offer = await pc.createOffer();
    await pc.setLocalDescription(offer);
    const otherId = conversation.participants.find(p => p !== user.id);
    ws.current.send(JSON.stringify({
      type: 'webrtc_signal',
      target_user_id: otherId,
      signal: { sdp: pc.localDescription }
    }));
  };

  useEffect(() => {
    if (isInitiator && status === 'ringing') {
      handleStartCall();
    }
  }, []);

  const handleEndCall = async () => {
    stopDialtone();
    stopRingtone();
    try {
      await api.post(`/dm/call/${callIdRef.current}/end`);
    } catch {}
    localStreamRef.current?.getTracks().forEach(t => t.stop());
    pcRef.current?.close();
    pcRef.current = null;
    playLeaveSound();
    setStatus('ended');
    onCallEnd();
  };

  const handleDecline = async () => {
    stopRingtone();
    try {
      await api.post(`/dm/call/${callIdRef.current}/decline`);
    } catch {}
    playLeaveSound();
    onCallEnd();
  };

  const toggleMute = () => {
    const audioTrack = localStreamRef.current?.getAudioTracks()[0];
    if (audioTrack) {
      audioTrack.enabled = !audioTrack.enabled;
      setMuted(!audioTrack.enabled);
    }
  };

  const toggleVideo = async () => {
    if (videoOn) {
      const videoTrack = localStreamRef.current?.getVideoTracks()[0];
      if (videoTrack) {
        videoTrack.stop();
        pcRef.current?.getSenders().forEach(s => {
          if (s.track?.kind === 'video') pcRef.current.removeTrack(s);
        });
      }
      setVideoOn(false);
    } else {
      try {
        const videoStream = await navigator.mediaDevices.getUserMedia({ video: true });
        const videoTrack = videoStream.getVideoTracks()[0];
        if (localStreamRef.current) localStreamRef.current.addTrack(videoTrack);
        pcRef.current?.addTrack(videoTrack, localStreamRef.current);
        if (localVideoRef.current) localVideoRef.current.srcObject = localStreamRef.current;
        setVideoOn(true);
      } catch {}
    }
  };

  const otherUser = conversation?.other_user;
  const otherName = otherUser?.display_name || otherUser?.username || 'User';
  const ringSecondsLeft = Math.max(0, Math.ceil((RING_TIMEOUT_MS - ringElapsed) / 1000));

  // ─── Incoming call ───
  if (status === 'ringing' && !isInitiator) {
    return (
      <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center" data-testid="incoming-call-overlay">
        <div className="bg-slate-900 border border-white/10 rounded-2xl p-8 text-center max-w-sm w-full mx-4 shadow-2xl shadow-emerald-500/10">
          {/* Pulsating ring animation */}
          <div className="relative w-24 h-24 mx-auto mb-5">
            <div className="absolute inset-0 rounded-full bg-emerald-500/20 animate-ping" style={{ animationDuration: '1.5s' }} />
            <div className="absolute inset-1 rounded-full bg-emerald-500/10 animate-ping" style={{ animationDuration: '1.5s', animationDelay: '0.3s' }} />
            <div className="relative w-24 h-24 rounded-full bg-gradient-to-br from-slate-700 to-slate-800 flex items-center justify-center text-2xl font-semibold text-slate-200 ring-2 ring-emerald-500/40">
              {otherName.slice(0, 2).toUpperCase()}
            </div>
          </div>
          <p className="text-lg text-slate-100 font-semibold mb-0.5">{otherName}</p>
          <p className="text-sm text-emerald-400 mb-1 font-medium flex items-center justify-center gap-1.5">
            <Phone className="w-3.5 h-3.5 animate-bounce" style={{ animationDuration: '0.6s' }} />
            Incoming call...
          </p>
          <p className="text-xs text-slate-500 mb-6">Auto-decline in {ringSecondsLeft}s</p>
          <div className="flex items-center justify-center gap-8">
            <div className="flex flex-col items-center gap-1.5">
              <button
                onClick={handleDecline}
                className="w-16 h-16 rounded-full bg-red-500/90 flex items-center justify-center text-white hover:bg-red-500 hover:scale-105 transition-all shadow-lg shadow-red-500/30"
                data-testid="decline-call-btn"
              >
                <PhoneOff className="w-7 h-7" />
              </button>
              <span className="text-xs text-slate-400">Decline</span>
            </div>
            <div className="flex flex-col items-center gap-1.5">
              <button
                onClick={handleAnswer}
                className="w-16 h-16 rounded-full bg-emerald-500 flex items-center justify-center text-white hover:bg-emerald-400 hover:scale-105 transition-all shadow-lg shadow-emerald-500/30 animate-pulse"
                style={{ animationDuration: '1.2s' }}
                data-testid="answer-call-btn"
              >
                <Phone className="w-7 h-7" />
              </button>
              <span className="text-xs text-slate-400">Answer</span>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // ─── Outgoing call ───
  if (status === 'ringing' && isInitiator) {
    return (
      <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center" data-testid="outgoing-call-overlay">
        <div className="bg-slate-900 border border-white/10 rounded-2xl p-8 text-center max-w-sm w-full mx-4 shadow-2xl">
          <div className="relative w-24 h-24 mx-auto mb-5">
            <div className="absolute inset-0 rounded-full bg-sky-500/15 animate-ping" style={{ animationDuration: '2s' }} />
            <div className="relative w-24 h-24 rounded-full bg-gradient-to-br from-slate-700 to-slate-800 flex items-center justify-center text-2xl font-semibold text-slate-200 ring-2 ring-sky-500/30">
              {otherName.slice(0, 2).toUpperCase()}
            </div>
          </div>
          <p className="text-lg text-slate-100 font-semibold mb-0.5">{otherName}</p>
          <p className="text-sm text-sky-400 mb-1 font-medium">Calling...</p>
          <p className="text-xs text-slate-500 mb-6">Ringing ({ringSecondsLeft}s)</p>
          <button
            onClick={handleEndCall}
            className="w-16 h-16 rounded-full bg-red-500/90 flex items-center justify-center text-white hover:bg-red-500 hover:scale-105 transition-all shadow-lg shadow-red-500/30 mx-auto"
            data-testid="cancel-call-btn"
          >
            <PhoneOff className="w-7 h-7" />
          </button>
          <span className="text-xs text-slate-400 mt-1.5 block">Cancel</span>
        </div>
      </div>
    );
  }

  // ─── Active call ───
  return (
    <div className="fixed inset-0 z-50 bg-black/90 flex flex-col" data-testid="active-call">
      <div className="flex-1 flex items-center justify-center gap-8 p-8">
        <div className="relative flex-1 max-w-2xl aspect-video bg-slate-900/50 rounded-xl border border-white/5 flex items-center justify-center overflow-hidden">
          {remoteStream ? (
            <video ref={remoteVideoRef} autoPlay playsInline className="w-full h-full object-cover" />
          ) : (
            <div className="text-center">
              <div className="w-24 h-24 rounded-full bg-slate-800 flex items-center justify-center text-3xl font-medium text-slate-300 mx-auto mb-3">
                {otherName.slice(0, 2).toUpperCase()}
              </div>
              <p className="text-slate-300">{otherName}</p>
            </div>
          )}
        </div>

        {videoOn && (
          <div className="absolute bottom-24 right-8 w-48 aspect-video bg-slate-900 rounded-lg border border-white/10 overflow-hidden">
            <video ref={localVideoRef} autoPlay muted playsInline className="w-full h-full object-cover" />
          </div>
        )}
      </div>

      <div className="flex items-center justify-center gap-4 pb-8">
        <button
          onClick={toggleMute}
          className={`w-12 h-12 rounded-full flex items-center justify-center transition-colors ${muted ? 'bg-red-500 text-white' : 'bg-slate-800 text-slate-300 hover:bg-slate-700'}`}
          data-testid="call-mute-btn"
        >
          {muted ? <MicOff className="w-5 h-5" /> : <Mic className="w-5 h-5" />}
        </button>
        <button
          onClick={toggleVideo}
          className={`w-12 h-12 rounded-full flex items-center justify-center transition-colors ${videoOn ? 'bg-emerald-500 text-white' : 'bg-slate-800 text-slate-300 hover:bg-slate-700'}`}
          data-testid="call-video-btn"
        >
          {videoOn ? <Video className="w-5 h-5" /> : <VideoOff className="w-5 h-5" />}
        </button>
        <button
          onClick={handleEndCall}
          className="w-14 h-14 rounded-full bg-red-500 flex items-center justify-center text-white hover:bg-red-600 transition-colors"
          data-testid="end-call-btn"
        >
          <PhoneOff className="w-6 h-6" />
        </button>
      </div>
    </div>
  );
}
