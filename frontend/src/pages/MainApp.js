import { useState, useEffect, useCallback, useRef } from 'react';
import { useAuth } from '../contexts/AuthContext';
import api from '../lib/api';
import ServerSidebar from '../components/ServerSidebar';
import ChannelSidebar from '../components/ChannelSidebar';
import ChatArea from '../components/ChatArea';
import MembersPanel from '../components/MembersPanel';
import DMList from '../components/DMList';
import FriendsList from '../components/FriendsList';
import UserSettings from '../components/UserSettings';
import ServerSettings from '../components/ServerSettings';
import ShareDrive from '../components/ShareDrive';
import VoiceChannel from '../components/VoiceChannel';
import ChannelSettings from '../components/ChannelSettings';
import DMCall from '../components/DMCall';
import { Menu, X, PhoneOff, Mic } from 'lucide-react';

export default function MainApp() {
  const { user, ws } = useAuth();
  const [servers, setServers] = useState([]);
  const [activeServer, setActiveServer] = useState(null);
  const [serverData, setServerData] = useState(null);
  const [activeChannel, setActiveChannel] = useState(null);
  const [activeView, setActiveView] = useState('friends');
  const [conversations, setConversations] = useState([]);
  const [activeConversation, setActiveConversation] = useState(null);
  const [showMembers, setShowMembers] = useState(true);
  const [showSettings, setShowSettings] = useState(null);
  const [showServerSettings, setShowServerSettings] = useState(false);
  const [showDrive, setShowDrive] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [channelSettings, setChannelSettings] = useState(null); // channel being edited
  const [activeCall, setActiveCall] = useState(null); // { call_id, conversation_id, caller_id, caller_username }
  // Persistent voice state - survives navigation
  const [voiceState, setVoiceState] = useState(null); // { serverId, channelId, channelName }

  const loadServers = useCallback(async () => {
    try {
      const { data } = await api.get('/servers');
      setServers(data);
    } catch {}
  }, []);

  const loadConversations = useCallback(async () => {
    try {
      const { data } = await api.get('/dm/conversations');
      setConversations(data);
    } catch {}
  }, []);

  const activeChannelRef = useRef(activeChannel);
  activeChannelRef.current = activeChannel;

  const loadServerData = useCallback(async (serverId) => {
    try {
      const { data } = await api.get(`/servers/${serverId}`);
      setServerData(data);
      if (data.channels?.length > 0 && !activeChannelRef.current) {
        const textChannels = data.channels.filter(c => c.channel_type === 'text');
        if (textChannels.length > 0) setActiveChannel(textChannels[0]);
      }
    } catch {}
  }, []);

  useEffect(() => {
    loadServers();
    loadConversations();
  }, [loadServers, loadConversations]);

  // Escape key to back out of menus/views
  useEffect(() => {
    const handleEscape = (e) => {
      if (e.key !== 'Escape') return;
      if (showSettings) { setShowSettings(null); return; }
      if (showServerSettings) { setShowServerSettings(false); return; }
      if (showDrive) { setShowDrive(false); return; }
      if (activeConversation) { setActiveConversation(null); return; }
      if (activeChannel) { setActiveChannel(null); return; }
      if (activeServer) { setActiveServer(null); setServerData(null); setActiveView('friends'); return; }
    };
    window.addEventListener('keydown', handleEscape);
    return () => window.removeEventListener('keydown', handleEscape);
  }, [showSettings, showServerSettings, showDrive, activeConversation, activeChannel, activeServer]);

  useEffect(() => {
    if (activeServer) {
      loadServerData(activeServer);
      setActiveView('server');
      setShowDrive(false);
    }
  }, [activeServer, loadServerData]);

  useEffect(() => {
    const websocket = ws?.current;
    if (!websocket) return;
    const handler = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'new_message') {
          loadConversations();
        } else if (data.type === 'incoming_call') {
          // Find the conversation for this call
          const conv = conversations.find(c => c.id === data.conversation_id) || { id: data.conversation_id, participants: [] };
          setActiveCall({ ...data, conversation: conv });
        } else if (data.type === 'call_ended' || data.type === 'call_declined') {
          setActiveCall(null);
        } else if (data.type === 'member_status_update') {
          // Update member status locally without refetching entire server
          setServerData(prev => {
            if (!prev?.members) return prev;
            return {
              ...prev,
              members: prev.members.map(m =>
                m.user_id === data.user_id
                  ? { ...m, status: data.status, is_online: data.is_online }
                  : m
              )
            };
          });
        } else if (data.type === 'status_update') {
          // Friend status update - update conversations list
          setConversations(prev => prev.map(c => {
            if (c.other_user?.id === data.user_id) {
              return { ...c, other_user: { ...c.other_user, status: data.status, is_online: data.status !== 'invisible' } };
            }
            return c;
          }));
        }
      } catch {}
    };
    websocket.addEventListener('message', handler);
    return () => websocket.removeEventListener('message', handler);
  }, [ws, loadConversations]);

  const handleSelectServer = (serverId) => {
    setActiveServer(serverId);
    setActiveConversation(null);
    setActiveChannel(null);
    setShowDrive(false);
    setShowServerSettings(false);
    setMobileMenuOpen(false);
  };

  const handleSelectDMs = () => {
    setActiveServer(null);
    setServerData(null);
    setActiveChannel(null);
    setActiveView('dms');
    setShowDrive(false);
    setShowServerSettings(false);
    setMobileMenuOpen(false);
  };

  const handleSelectFriends = () => {
    setActiveServer(null);
    setServerData(null);
    setActiveChannel(null);
    setActiveConversation(null);
    setActiveView('friends');
    setShowDrive(false);
    setShowServerSettings(false);
    setMobileMenuOpen(false);
  };

  const handleSelectConversation = (conv) => {
    setActiveConversation(conv);
    setActiveView('dms');
    setShowServerSettings(false);
    setMobileMenuOpen(false);
  };

  const handleSelectChannel = (channel) => {
    setActiveChannel(channel);
    setShowDrive(false);
    setShowServerSettings(false);
    setChannelSettings(null);
    setMobileMenuOpen(false);
  };

  const handleStartDM = (conv) => {
    setActiveConversation(conv);
    setActiveView('dms');
    loadConversations();
  };

  const handleStartCall = async (conv) => {
    try {
      const { data } = await api.post(`/dm/${conv.id}/call`);
      setActiveCall({ ...data, conversation: conv });
    } catch {}
  };

  const handleVoiceJoin = (serverId, channel) => {
    setVoiceState({ serverId, channelId: channel.id, channelName: channel.name });
  };

  const handleVoiceLeave = () => {
    setVoiceState(null);
  };

  // Determine if we should show voice channel view
  const showVoiceView = activeServer && activeChannel?.channel_type === 'voice';
  // Determine if persistent voice bar should show (connected to voice but viewing something else)
  const showVoiceBar = voiceState && !(showVoiceView && voiceState.channelId === activeChannel?.id);

  return (
    <div className="h-screen w-full flex overflow-hidden bg-[#020617]" data-testid="main-app">
      {/* Mobile menu toggle */}
      <button
        className="lg:hidden fixed top-3 left-3 z-50 p-2 bg-slate-800 rounded-md text-slate-300"
        onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
        data-testid="mobile-menu-btn"
      >
        {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
      </button>

      {/* Server sidebar */}
      <div className={`${mobileMenuOpen ? 'flex' : 'hidden'} lg:flex flex-shrink-0 fixed lg:relative z-40 h-full`}>
        <ServerSidebar
          servers={servers}
          activeServer={activeServer}
          onSelectServer={handleSelectServer}
          onSelectDMs={handleSelectDMs}
          onSelectFriends={handleSelectFriends}
          onServerCreated={loadServers}
          onOpenSettings={() => setShowSettings(true)}
        />

        {/* Channel / DM sidebar */}
        {activeServer && serverData ? (
          <ChannelSidebar
            server={serverData}
            activeChannel={activeChannel}
            onSelectChannel={handleSelectChannel}
            onOpenSettings={() => setShowServerSettings(true)}
            onOpenDrive={() => { setShowDrive(true); setActiveChannel(null); }}
            user={user}
            onChannelCreated={() => loadServerData(activeServer)}
            onOpenChannelSettings={(ch) => { setChannelSettings(ch); setActiveChannel(null); }}
          />
        ) : (
          <DMList
            conversations={conversations}
            activeConversation={activeConversation}
            onSelectConversation={handleSelectConversation}
            onSelectFriends={handleSelectFriends}
            activeView={activeView}
            user={user}
          />
        )}
      </div>

      {/* Main content area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Persistent voice bar */}
        {showVoiceBar && (
          <div className="h-10 bg-emerald-500/10 border-b border-emerald-500/20 flex items-center justify-between px-4 flex-shrink-0" data-testid="voice-bar">
            <div className="flex items-center gap-2 text-sm text-emerald-400">
              <Mic className="w-3.5 h-3.5" />
              <span className="font-['IBM_Plex_Sans']">Connected to <strong>{voiceState.channelName}</strong></span>
            </div>
            <button
              onClick={() => {
                const websocket = ws?.current;
                if (websocket?.readyState === WebSocket.OPEN) {
                  websocket.send(JSON.stringify({ type: 'leave_voice', channel_id: voiceState.channelId }));
                }
                handleVoiceLeave();
              }}
              className="flex items-center gap-1.5 text-xs text-red-400 hover:text-red-300 transition-colors"
              data-testid="voice-disconnect-btn"
            >
              <PhoneOff className="w-3.5 h-3.5" />
              Disconnect
            </button>
          </div>
        )}

        {showSettings ? (
          <UserSettings onClose={() => setShowSettings(null)} />
        ) : showServerSettings && serverData ? (
          <ServerSettings server={serverData} onClose={() => setShowServerSettings(false)} onUpdate={() => loadServerData(activeServer)} />
        ) : channelSettings && serverData ? (
          <ChannelSettings channel={channelSettings} server={serverData} onClose={() => setChannelSettings(null)} onUpdate={() => loadServerData(activeServer)} />
        ) : showDrive && serverData ? (
          <ShareDrive server={serverData} />
        ) : activeView === 'friends' && !activeServer ? (
          <FriendsList onStartDM={handleStartDM} />
        ) : showVoiceView ? (
          <div className="flex-1 flex min-h-0">
            <VoiceChannel
              channel={activeChannel}
              server={serverData}
              user={user}
              ws={ws}
              onVoiceJoin={() => handleVoiceJoin(activeServer, activeChannel)}
              onVoiceLeave={handleVoiceLeave}
            />
            {showMembers && serverData && <MembersPanel server={serverData} />}
          </div>
        ) : (activeView === 'dms' && activeConversation) || (activeServer && activeChannel) ? (
          <div className="flex-1 flex min-h-0">
            <ChatArea
              channel={activeChannel}
              conversation={activeConversation}
              server={serverData}
              user={user}
              ws={ws}
              onStartCall={activeConversation ? () => handleStartCall(activeConversation) : undefined}
            />
            {activeServer && serverData && showMembers && (
              <MembersPanel server={serverData} />
            )}
          </div>
        ) : (
          <div className="flex-1 flex items-center justify-center text-slate-500 font-['IBM_Plex_Sans']">
            <div className="text-center">
              <p className="text-lg">Select a conversation or channel to start chatting</p>
              <p className="text-sm mt-2 text-slate-600">Or add some friends to get started</p>
            </div>
          </div>
        )}
      </div>

      {mobileMenuOpen && <div className="fixed inset-0 bg-black/50 z-30 lg:hidden" onClick={() => setMobileMenuOpen(false)} />}

      {/* DM Call overlay */}
      {activeCall && (
        <DMCall
          conversation={activeCall.conversation || activeConversation}
          user={user}
          ws={ws}
          callData={activeCall}
          onCallEnd={() => setActiveCall(null)}
        />
      )}
    </div>
  );
}
