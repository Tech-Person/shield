// VoiceManager - Persistent voice state that lives at MainApp level
// Holds peer connections, streams, and participants across navigation
import { useRef, useState, useCallback, useEffect } from 'react';
import api from './api';
import { playJoinSound, playLeaveSound, createAudioLevelDetector } from './audio';

export function useVoiceManager(user, ws) {
  const [joined, setJoined] = useState(false);
  const [channelInfo, setChannelInfo] = useState(null); // { id, name, serverId }
  const [participants, setParticipants] = useState([]);
  const [muted, setMuted] = useState(false);
  const [deafened, setDeafened] = useState(false);
  const [videoOn, setVideoOn] = useState(false);
  const [screenSharing, setScreenSharing] = useState(false);
  const [speaking, setSpeaking] = useState(false);

  const localStreamRef = useRef(null);
  const screenStreamRef = useRef(null);
  const peerConnectionsRef = useRef({});
  const remoteStreamsRef = useRef({}); // userId -> MediaStream
  const iceServersRef = useRef(null);
  const audioDetectorCleanupRef = useRef(null);
  const remoteAudioRefs = useRef({}); // userId -> HTMLAudioElement
  const participantPollRef = useRef(null);

  // Fetch TURN/STUN credentials
  useEffect(() => {
    (async () => {
      try {
        const { data } = await api.get('/turn/credentials');
        iceServersRef.current = data.ice_servers;
      } catch {
        iceServersRef.current = [{ urls: 'stun:stun.l.google.com:19302' }];
      }
    })();
  }, []);

  const loadParticipants = useCallback(async () => {
    if (!channelInfo?.id) return;
    try {
      const { data } = await api.get(`/channels/${channelInfo.id}/voice-participants`);
      setParticipants(data);
    } catch {}
  }, [channelInfo?.id]);

  // Poll participants while joined
  useEffect(() => {
    if (joined && channelInfo?.id) {
      loadParticipants();
      participantPollRef.current = setInterval(loadParticipants, 5000);
      return () => clearInterval(participantPollRef.current);
    }
  }, [joined, channelInfo?.id, loadParticipants]);

  // Play remote audio from persistent elements (survives navigation)
  const playRemoteStream = useCallback((userId, stream) => {
    remoteStreamsRef.current[userId] = stream;
    // Create or reuse a persistent audio element
    let audioEl = remoteAudioRefs.current[userId];
    if (!audioEl) {
      audioEl = new Audio();
      audioEl.autoplay = true;
      remoteAudioRefs.current[userId] = audioEl;
    }
    audioEl.srcObject = stream;
    audioEl.muted = deafened;
    audioEl.play().catch(() => {});
  }, [deafened]);

  // Update deafen state on all remote audio
  useEffect(() => {
    Object.values(remoteAudioRefs.current).forEach(el => {
      el.muted = deafened;
    });
  }, [deafened]);

  const createPeerConnection = useCallback((targetUserId) => {
    const iceConfig = iceServersRef.current || [{ urls: 'stun:stun.l.google.com:19302' }];
    const pc = new RTCPeerConnection({ iceServers: iceConfig });

    pc.onicecandidate = (e) => {
      if (e.candidate && ws?.current?.readyState === WebSocket.OPEN) {
        ws.current.send(JSON.stringify({
          type: 'webrtc_signal',
          target_user_id: targetUserId,
          signal: e.candidate
        }));
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
        if (ws?.current?.readyState === WebSocket.OPEN) {
          ws.current.send(JSON.stringify({
            type: 'webrtc_signal',
            target_user_id: targetUserId,
            signal: pc.localDescription
          }));
        }
      } catch {}
    };

    pc.ontrack = (e) => {
      playRemoteStream(targetUserId, e.streams[0]);
    };

    // Add local tracks
    if (localStreamRef.current) {
      localStreamRef.current.getTracks().forEach(track => {
        pc.addTrack(track, localStreamRef.current);
      });
    }

    return pc;
  }, [ws, playRemoteStream]);

  const handleWebRTCSignal = useCallback(async (data) => {
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
        if (ws?.current?.readyState === WebSocket.OPEN) {
          ws.current.send(JSON.stringify({
            type: 'webrtc_signal',
            target_user_id: fromUser,
            signal: answer
          }));
        }
      } else if (signal.type === 'answer') {
        await pc.setRemoteDescription(new RTCSessionDescription(signal));
      } else if (signal.candidate) {
        await pc.addIceCandidate(new RTCIceCandidate(signal));
      }
    } catch (err) {
      console.error('WebRTC signal error:', err);
    }
  }, [ws, createPeerConnection]);

  // WebSocket handler for voice events (lives at MainApp level, always active)
  useEffect(() => {
    const websocket = ws?.current;
    if (!websocket) return;
    const handler = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'voice_state_update' && data.channel_id === channelInfo?.id) {
          loadParticipants();
          if (data.user_joined && data.user_joined !== user?.id && joined) playJoinSound();
          if (data.user_left && data.user_left !== user?.id && joined) playLeaveSound();
          if (data.user_left) {
            const leftId = data.user_left;
            const pc = peerConnectionsRef.current[leftId];
            if (pc) { pc.close(); delete peerConnectionsRef.current[leftId]; }
            const audioEl = remoteAudioRefs.current[leftId];
            if (audioEl) { audioEl.srcObject = null; delete remoteAudioRefs.current[leftId]; }
            delete remoteStreamsRef.current[leftId];
          }
        }
        if (data.type === 'webrtc_signal' && joined) {
          handleWebRTCSignal(data);
        }
      } catch {}
    };
    websocket.addEventListener('message', handler);
    return () => websocket.removeEventListener('message', handler);
  }, [ws, channelInfo?.id, joined, user?.id, loadParticipants, handleWebRTCSignal]);

  const joinChannel = useCallback(async (channel, serverId) => {
    if (joined) return; // Already in a call
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
      localStreamRef.current = stream;
      setChannelInfo({ id: channel.id, name: channel.name, serverId });

      // Subscribe and join
      const websocket = ws?.current;
      if (websocket?.readyState === WebSocket.OPEN) {
        websocket.send(JSON.stringify({ type: 'subscribe_channel', channel_id: channel.id }));
        websocket.send(JSON.stringify({ type: 'join_voice', channel_id: channel.id }));
      }

      setJoined(true);
      playJoinSound();
      audioDetectorCleanupRef.current = createAudioLevelDetector(stream, setSpeaking);

      // Get current participants and connect to them
      const { data: parts } = await api.get(`/channels/${channel.id}/voice-participants`);
      setParticipants(parts);
      setTimeout(() => {
        parts.forEach(p => {
          if (p.id !== user?.id && !peerConnectionsRef.current[p.id]) {
            const pc = createPeerConnection(p.id);
            peerConnectionsRef.current[p.id] = pc;
            (async () => {
              try {
                const offer = await pc.createOffer();
                await pc.setLocalDescription(offer);
                if (ws?.current?.readyState === WebSocket.OPEN) {
                  ws.current.send(JSON.stringify({
                    type: 'webrtc_signal',
                    target_user_id: p.id,
                    signal: offer
                  }));
                }
              } catch {}
            })();
          }
        });
      }, 500);
    } catch (err) {
      console.error('Failed to join voice:', err);
    }
  }, [joined, ws, user?.id, createPeerConnection]);

  const leaveChannel = useCallback(() => {
    const websocket = ws?.current;
    if (websocket?.readyState === WebSocket.OPEN && channelInfo?.id) {
      websocket.send(JSON.stringify({ type: 'leave_voice', channel_id: channelInfo.id }));
    }
    // Stop all streams
    localStreamRef.current?.getTracks().forEach(t => t.stop());
    screenStreamRef.current?.getTracks().forEach(t => t.stop());
    // Close all peer connections
    Object.values(peerConnectionsRef.current).forEach(pc => pc.close());
    peerConnectionsRef.current = {};
    // Stop all remote audio
    Object.values(remoteAudioRefs.current).forEach(el => { el.srcObject = null; });
    remoteAudioRefs.current = {};
    remoteStreamsRef.current = {};
    localStreamRef.current = null;
    screenStreamRef.current = null;
    if (audioDetectorCleanupRef.current) audioDetectorCleanupRef.current();
    audioDetectorCleanupRef.current = null;
    setSpeaking(false);
    setJoined(false);
    setMuted(false);
    setDeafened(false);
    setVideoOn(false);
    setScreenSharing(false);
    setChannelInfo(null);
    setParticipants([]);
    playLeaveSound();
  }, [ws, channelInfo?.id]);

  const toggleMute = useCallback(() => {
    if (localStreamRef.current) {
      localStreamRef.current.getAudioTracks().forEach(t => { t.enabled = muted; });
      setMuted(!muted);
    }
  }, [muted]);

  const toggleDeafen = useCallback(() => {
    setDeafened(prev => !prev);
  }, []);

  const toggleVideo = useCallback(async () => {
    if (videoOn) {
      localStreamRef.current?.getVideoTracks().forEach(t => { t.stop(); localStreamRef.current.removeTrack(t); });
      setVideoOn(false);
    } else {
      try {
        const videoStream = await navigator.mediaDevices.getUserMedia({
          video: { width: { ideal: 1280 }, height: { ideal: 720 }, frameRate: { ideal: 30 } }
        });
        videoStream.getVideoTracks().forEach(t => localStreamRef.current?.addTrack(t));
        Object.values(peerConnectionsRef.current).forEach(pc => {
          videoStream.getVideoTracks().forEach(track => pc.addTrack(track, localStreamRef.current));
        });
        setVideoOn(true);
      } catch {}
    }
  }, [videoOn]);

  const toggleScreenShare = useCallback(async () => {
    if (screenSharing) {
      screenStreamRef.current?.getTracks().forEach(t => t.stop());
      screenStreamRef.current = null;
      setScreenSharing(false);
    } else {
      try {
        const stream = await navigator.mediaDevices.getDisplayMedia({ video: true, audio: true });
        screenStreamRef.current = stream;
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
      } catch {}
    }
  }, [screenSharing]);

  return {
    joined,
    channelInfo,
    participants,
    muted,
    deafened,
    videoOn,
    screenSharing,
    speaking,
    localStreamRef,
    screenStreamRef,
    remoteStreamsRef,
    joinChannel,
    leaveChannel,
    toggleMute,
    toggleDeafen,
    toggleVideo,
    toggleScreenShare
  };
}
