import { useState, useEffect, useRef, useCallback } from 'react';
import api from '../lib/api';
import { Phone, PhoneOff, Video, VideoOff, Mic, MicOff, X } from 'lucide-react';
import { Button } from '../components/ui/button';
import { playJoinSound, playLeaveSound } from '../lib/audio';

export default function DMCall({ conversation, user, ws, callData, onCallEnd }) {
  const [status, setStatus] = useState(callData?.status || 'ringing'); // ringing, active, ended
  const [muted, setMuted] = useState(false);
  const [videoOn, setVideoOn] = useState(false);
  const [remoteStream, setRemoteStream] = useState(null);
  const localStreamRef = useRef(null);
  const localVideoRef = useRef(null);
  const remoteVideoRef = useRef(null);
  const pcRef = useRef(null);
  const callIdRef = useRef(callData?.call_id || callData?.id);
  const isInitiator = callData?.initiator_id === user.id || callData?.caller_id === user.id;

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

    pc.ontrack = (e) => {
      setRemoteStream(e.streams[0]);
    };

    pc.oniceconnectionstatechange = () => {
      if (pc.iceConnectionState === 'failed' || pc.iceConnectionState === 'disconnected') {
        handleEndCall();
      }
    };

    // Get local media
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
          setStatus('active');
          playJoinSound();
        } else if (data.type === 'call_declined' || data.type === 'call_ended') {
          setStatus('ended');
          playLeaveSound();
          setTimeout(() => onCallEnd(), 1500);
        }
      } catch {}
    };

    websocket.addEventListener('message', handler);
    return () => websocket.removeEventListener('message', handler);
  }, [ws, conversation, user.id, onCallEnd]);

  // Set remote video
  useEffect(() => {
    if (remoteVideoRef.current && remoteStream) {
      remoteVideoRef.current.srcObject = remoteStream;
    }
  }, [remoteStream]);

  const handleAnswer = async () => {
    try {
      await api.post(`/dm/call/${callIdRef.current}/answer`);
      const pc = await setupPeerConnection();
      setStatus('active');
      playJoinSound();

      // Wait for offer from initiator
      // The offer will come through WebRTC signal handler
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

  // Initiator starts the call immediately
  useEffect(() => {
    if (isInitiator && status === 'ringing') {
      handleStartCall();
    }
  }, []);

  const handleEndCall = async () => {
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
      // Stop video
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

  const otherUser = conversation.other_user;
  const otherName = otherUser?.display_name || otherUser?.username || 'User';

  // Ringing state (incoming call)
  if (status === 'ringing' && !isInitiator) {
    return (
      <div className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center" data-testid="incoming-call-overlay">
        <div className="bg-slate-900 border border-white/10 rounded-2xl p-8 text-center max-w-sm w-full mx-4">
          <div className="w-20 h-20 rounded-full bg-slate-800 flex items-center justify-center text-2xl font-medium text-slate-300 mx-auto mb-4">
            {otherName.slice(0, 2).toUpperCase()}
          </div>
          <p className="text-lg text-slate-100 font-['Outfit'] mb-1">{otherName}</p>
          <p className="text-sm text-slate-400 mb-8 animate-pulse">Incoming call...</p>
          <div className="flex items-center justify-center gap-6">
            <button
              onClick={handleDecline}
              className="w-14 h-14 rounded-full bg-red-500 flex items-center justify-center text-white hover:bg-red-600 transition-colors"
              data-testid="decline-call-btn"
            >
              <PhoneOff className="w-6 h-6" />
            </button>
            <button
              onClick={handleAnswer}
              className="w-14 h-14 rounded-full bg-emerald-500 flex items-center justify-center text-white hover:bg-emerald-400 transition-colors"
              data-testid="answer-call-btn"
            >
              <Phone className="w-6 h-6" />
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Ringing state (outgoing call)
  if (status === 'ringing' && isInitiator) {
    return (
      <div className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center" data-testid="outgoing-call-overlay">
        <div className="bg-slate-900 border border-white/10 rounded-2xl p-8 text-center max-w-sm w-full mx-4">
          <div className="w-20 h-20 rounded-full bg-slate-800 flex items-center justify-center text-2xl font-medium text-slate-300 mx-auto mb-4">
            {otherName.slice(0, 2).toUpperCase()}
          </div>
          <p className="text-lg text-slate-100 font-['Outfit'] mb-1">{otherName}</p>
          <p className="text-sm text-slate-400 mb-8 animate-pulse">Calling...</p>
          <button
            onClick={handleEndCall}
            className="w-14 h-14 rounded-full bg-red-500 flex items-center justify-center text-white hover:bg-red-600 transition-colors mx-auto"
            data-testid="cancel-call-btn"
          >
            <PhoneOff className="w-6 h-6" />
          </button>
        </div>
      </div>
    );
  }

  // Active call
  return (
    <div className="fixed inset-0 z-50 bg-black/90 flex flex-col" data-testid="active-call">
      <div className="flex-1 flex items-center justify-center gap-8 p-8">
        {/* Remote video/avatar */}
        <div className="relative flex-1 max-w-2xl aspect-video bg-slate-900/50 rounded-xl border border-white/5 flex items-center justify-center overflow-hidden">
          {remoteStream ? (
            <video ref={remoteVideoRef} autoPlay playsInline className="w-full h-full object-cover" />
          ) : (
            <div className="text-center">
              <div className="w-24 h-24 rounded-full bg-slate-800 flex items-center justify-center text-3xl font-medium text-slate-300 mx-auto mb-3">
                {otherName.slice(0, 2).toUpperCase()}
              </div>
              <p className="text-slate-300 font-['Outfit']">{otherName}</p>
            </div>
          )}
        </div>

        {/* Local video (small PiP) */}
        {videoOn && (
          <div className="absolute bottom-24 right-8 w-48 aspect-video bg-slate-900 rounded-lg border border-white/10 overflow-hidden">
            <video ref={localVideoRef} autoPlay muted playsInline className="w-full h-full object-cover" />
          </div>
        )}
      </div>

      {/* Controls */}
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
