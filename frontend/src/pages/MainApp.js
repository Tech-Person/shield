import { useState, useEffect, useCallback } from 'react';
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
import { Menu, X } from 'lucide-react';

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

  const loadServerData = useCallback(async (serverId) => {
    try {
      const { data } = await api.get(`/servers/${serverId}`);
      setServerData(data);
      if (data.channels?.length > 0 && !activeChannel) {
        const textChannels = data.channels.filter(c => c.channel_type === 'text');
        if (textChannels.length > 0) setActiveChannel(textChannels[0]);
      }
    } catch {}
  }, [activeChannel]);

  useEffect(() => {
    loadServers();
    loadConversations();
  }, [loadServers, loadConversations]);

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
        if (data.type === 'new_message' || data.type === 'channel_message') {
          loadConversations();
        } else if (data.type === 'friend_request' || data.type === 'friend_accepted') {
          // handled by FriendsList
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
    setMobileMenuOpen(false);
  };

  const handleSelectDMs = () => {
    setActiveServer(null);
    setServerData(null);
    setActiveChannel(null);
    setActiveView('dms');
    setShowDrive(false);
    setMobileMenuOpen(false);
  };

  const handleSelectFriends = () => {
    setActiveServer(null);
    setServerData(null);
    setActiveChannel(null);
    setActiveConversation(null);
    setActiveView('friends');
    setShowDrive(false);
    setMobileMenuOpen(false);
  };

  const handleSelectConversation = (conv) => {
    setActiveConversation(conv);
    setActiveView('dms');
    setMobileMenuOpen(false);
  };

  const handleSelectChannel = (channel) => {
    setActiveChannel(channel);
    setShowDrive(false);
    setMobileMenuOpen(false);
  };

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
        {showSettings ? (
          <UserSettings onClose={() => setShowSettings(null)} />
        ) : showServerSettings && serverData ? (
          <ServerSettings server={serverData} onClose={() => setShowServerSettings(false)} onUpdate={() => loadServerData(activeServer)} />
        ) : showDrive && serverData ? (
          <ShareDrive server={serverData} />
        ) : activeView === 'friends' && !activeServer ? (
          <FriendsList onStartDM={(conv) => { setActiveConversation(conv); setActiveView('dms'); }} />
        ) : activeServer && activeChannel && activeChannel.channel_type === 'voice' ? (
          <div className="flex-1 flex min-h-0">
            <VoiceChannel
              channel={activeChannel}
              server={serverData}
              user={user}
              ws={ws}
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

      {/* User bar at bottom of server sidebar - shown via CSS */}
      {mobileMenuOpen && <div className="fixed inset-0 bg-black/50 z-30 lg:hidden" onClick={() => setMobileMenuOpen(false)} />}
    </div>
  );
}
