import { useState, useEffect, useRef, useCallback } from 'react';
import api from '../lib/api';
import { Send, Paperclip, Search, Hash, X } from 'lucide-react';
import { Input } from '../components/ui/input';
import { ScrollArea } from '../components/ui/scroll-area';

export default function ChatArea({ channel, conversation, server, user, ws }) {
  const [messages, setMessages] = useState([]);
  const [newMessage, setNewMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  const targetId = channel?.id || conversation?.id;
  const isChannel = !!channel;

  const loadMessages = useCallback(async () => {
    if (!targetId) return;
    setLoading(true);
    try {
      const endpoint = isChannel
        ? `/channels/${channel.id}/messages`
        : `/dm/${conversation.id}/messages`;
      const { data } = await api.get(endpoint);
      setMessages(data);
    } catch {}
    setLoading(false);
  }, [targetId, isChannel, channel, conversation]);

  useEffect(() => {
    setMessages([]);
    setSearchOpen(false);
    setSearchResults([]);
    loadMessages();
  }, [targetId, loadMessages]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => {
    const websocket = ws?.current;
    if (!websocket) return;
    const handler = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'new_message' && data.message.conversation_id === conversation?.id) {
          setMessages(prev => [...prev, data.message]);
        } else if (data.type === 'channel_message' && data.message.channel_id === channel?.id) {
          setMessages(prev => [...prev, data.message]);
        }
      } catch {}
    };
    websocket.addEventListener('message', handler);

    if (isChannel && channel?.id) {
      websocket.send?.(JSON.stringify({ type: 'subscribe_channel', channel_id: channel.id }));
    } else if (conversation?.id) {
      websocket.send?.(JSON.stringify({ type: 'subscribe_dm', conversation_id: conversation.id }));
    }

    return () => {
      websocket.removeEventListener('message', handler);
    };
  }, [ws, channel, conversation, isChannel]);

  const handleSend = async (e) => {
    e.preventDefault();
    if (!newMessage.trim()) return;
    try {
      const endpoint = isChannel
        ? `/channels/${channel.id}/messages`
        : `/dm/${conversation.id}/messages`;
      const { data } = await api.post(endpoint, { content: newMessage });
      setMessages(prev => [...prev, data]);
      setNewMessage('');
      inputRef.current?.focus();
    } catch {}
  };

  const handleSearch = async () => {
    if (!searchQuery.trim()) return;
    try {
      const { data } = await api.post('/dm/search', {
        query: searchQuery,
        conversation_id: conversation?.id || null,
        limit: 50
      });
      setSearchResults(data);
    } catch {}
  };

  const title = isChannel
    ? `# ${channel?.name}`
    : conversation?.type === 'group_dm'
      ? conversation?.name
      : conversation?.other_user?.display_name || conversation?.other_user?.username || 'Chat';

  const formatTime = (ts) => {
    const d = new Date(ts);
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  const formatDate = (ts) => {
    const d = new Date(ts);
    const today = new Date();
    if (d.toDateString() === today.toDateString()) return 'Today';
    const yesterday = new Date(today);
    yesterday.setDate(yesterday.getDate() - 1);
    if (d.toDateString() === yesterday.toDateString()) return 'Yesterday';
    return d.toLocaleDateString();
  };

  let lastDate = null;

  return (
    <div className="flex-1 flex flex-col min-w-0 bg-[#020617]" data-testid="chat-area">
      {/* Header */}
      <div className="h-12 px-4 flex items-center justify-between border-b border-white/5 flex-shrink-0 bg-slate-950/60 backdrop-blur-2xl">
        <div className="flex items-center gap-2">
          {isChannel && <Hash className="w-4 h-4 text-slate-500" />}
          <span className="text-sm font-medium text-slate-100 font-['Outfit']">{title}</span>
          {channel?.topic && <span className="text-xs text-slate-500 ml-2 hidden sm:inline">{channel.topic}</span>}
        </div>
        <div className="flex items-center gap-2">
          {!isChannel && (
            <button
              onClick={() => setSearchOpen(!searchOpen)}
              className="p-2 text-slate-400 hover:text-slate-200 hover:bg-slate-800/50 rounded transition-colors"
              data-testid="search-messages-btn"
            >
              <Search className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>

      {/* Search panel */}
      {searchOpen && (
        <div className="px-4 py-3 border-b border-white/5 bg-slate-900/50" data-testid="search-panel">
          <div className="flex items-center gap-2">
            <Input
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleSearch()}
              placeholder="Search messages..."
              className="bg-slate-950/50 border-white/10 text-slate-100 text-sm flex-1"
              data-testid="search-input"
            />
            <button onClick={handleSearch} className="p-2 bg-emerald-500 text-slate-950 rounded hover:bg-emerald-400" data-testid="search-submit-btn">
              <Search className="w-4 h-4" />
            </button>
            <button onClick={() => { setSearchOpen(false); setSearchResults([]); }} className="p-2 text-slate-400 hover:text-slate-200">
              <X className="w-4 h-4" />
            </button>
          </div>
          {searchResults.length > 0 && (
            <div className="mt-3 max-h-60 overflow-y-auto space-y-2">
              {searchResults.map(msg => (
                <div key={msg.id} className="px-3 py-2 bg-slate-800/50 rounded text-sm">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-emerald-400 font-medium text-xs">{msg.sender_username}</span>
                    <span className="text-slate-600 text-xs font-mono">{formatTime(msg.created_at)}</span>
                  </div>
                  <p className="text-slate-300">{msg.content}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Messages */}
      <ScrollArea className="flex-1">
        <div className="p-4 space-y-1">
          {loading && <div className="text-center text-slate-500 py-8">Loading messages...</div>}
          {!loading && messages.length === 0 && (
            <div className="text-center text-slate-500 py-16">
              <p className="text-lg font-['Outfit']">No messages yet</p>
              <p className="text-sm mt-1">Start the conversation!</p>
            </div>
          )}
          {messages.map((msg, i) => {
            const msgDate = formatDate(msg.created_at);
            const showDate = msgDate !== lastDate;
            lastDate = msgDate;
            const prevMsg = messages[i - 1];
            const isGrouped = prevMsg?.sender_id === msg.sender_id && !showDate;

            return (
              <div key={msg.id}>
                {showDate && (
                  <div className="flex items-center gap-4 my-4">
                    <div className="flex-1 h-px bg-white/5" />
                    <span className="text-xs font-mono text-slate-600 uppercase tracking-widest">{msgDate}</span>
                    <div className="flex-1 h-px bg-white/5" />
                  </div>
                )}
                <div
                  className={`flex items-start gap-3 px-2 py-1 hover:bg-slate-900/50 rounded group transition-colors ${isGrouped ? 'mt-0' : 'mt-3'}`}
                  data-testid={`message-${msg.id}`}
                >
                  {!isGrouped ? (
                    <div className="w-9 h-9 rounded-full bg-slate-800 flex items-center justify-center text-xs font-medium text-slate-300 flex-shrink-0 mt-0.5">
                      {msg.sender_username?.slice(0, 2).toUpperCase()}
                    </div>
                  ) : (
                    <div className="w-9 flex-shrink-0">
                      <span className="text-[10px] font-mono text-slate-700 opacity-0 group-hover:opacity-100 transition-opacity">
                        {formatTime(msg.created_at)}
                      </span>
                    </div>
                  )}
                  <div className="min-w-0 flex-1">
                    {!isGrouped && (
                      <div className="flex items-baseline gap-2 mb-0.5">
                        <span className="text-sm font-medium text-slate-200">{msg.sender_username}</span>
                        <span className="text-[10px] font-mono text-slate-600">{formatTime(msg.created_at)}</span>
                      </div>
                    )}
                    <p className="text-sm text-slate-300 leading-relaxed break-words font-['IBM_Plex_Sans']">{msg.content}</p>
                    {msg.attachments?.length > 0 && (
                      <div className="flex gap-2 mt-2 flex-wrap">
                        {msg.attachments.map((att, j) => (
                          <div key={j} className="px-3 py-1.5 bg-slate-800/50 rounded border border-white/5 text-xs text-slate-400 flex items-center gap-1">
                            <Paperclip className="w-3 h-3" />
                            {att}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
          <div ref={messagesEndRef} />
        </div>
      </ScrollArea>

      {/* Message input */}
      <div className="p-4 border-t border-white/5 flex-shrink-0">
        <form onSubmit={handleSend} className="flex items-center gap-2">
          <div className="flex-1 relative">
            <Input
              ref={inputRef}
              value={newMessage}
              onChange={e => setNewMessage(e.target.value)}
              placeholder={`Message ${title}`}
              className="bg-slate-900 border-white/10 text-slate-100 pr-10 focus:ring-1 focus:ring-emerald-500/50 font-['IBM_Plex_Sans']"
              data-testid="chat-message-input"
            />
          </div>
          <button
            type="submit"
            className="p-2.5 bg-emerald-500 text-slate-950 rounded-md hover:bg-emerald-400 transition-colors disabled:opacity-50"
            disabled={!newMessage.trim()}
            data-testid="chat-send-btn"
          >
            <Send className="w-4 h-4" />
          </button>
        </form>
      </div>
    </div>
  );
}
