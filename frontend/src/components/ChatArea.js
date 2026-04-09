import { useState, useEffect, useRef, useCallback } from 'react';
import api from '../lib/api';
import { Send, Paperclip, Search, Hash, X, Smile, MessageSquare, Pencil, Trash2, Upload, ImageIcon, Sticker, CheckCheck } from 'lucide-react';
import { Input } from '../components/ui/input';
import { ScrollArea } from '../components/ui/scroll-area';
import { Popover, PopoverContent, PopoverTrigger } from '../components/ui/popover';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../components/ui/dialog';
import { Button } from '../components/ui/button';
import GifPicker from './GifPicker';
import EmojiManager from './EmojiManager';

const COMMON_EMOJIS = ['👍', '❤️', '😂', '😮', '😢', '🔥', '🎉', '👀', '✅', '❌', '💯', '🙏'];

export default function ChatArea({ channel, conversation, server, user, ws }) {
  const [messages, setMessages] = useState([]);
  const [newMessage, setNewMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [editingId, setEditingId] = useState(null);
  const [editContent, setEditContent] = useState('');
  const [threadMsg, setThreadMsg] = useState(null);
  const [threadReplies, setThreadReplies] = useState([]);
  const [threadReply, setThreadReply] = useState('');
  const [uploading, setUploading] = useState(false);
  const [gifPickerOpen, setGifPickerOpen] = useState(false);
  const [emojiPickerOpen, setEmojiPickerOpen] = useState(false);
  const [typingUsers, setTypingUsers] = useState([]);
  const [readReceipts, setReadReceipts] = useState([]);
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);
  const fileInputRef = useRef(null);
  const typingTimeoutRef = useRef(null);
  const lastTypingSentRef = useRef(0);

  const targetId = channel?.id || conversation?.id;
  const isChannel = !!channel;

  const loadMessages = useCallback(async () => {
    if (!targetId) return;
    setLoading(true);
    try {
      const endpoint = isChannel ? `/channels/${channel.id}/messages` : `/dm/${conversation.id}/messages`;
      const { data } = await api.get(endpoint);
      setMessages(data);
    } catch {}
    setLoading(false);
  }, [targetId, isChannel, channel, conversation]);

  useEffect(() => {
    setMessages([]);
    setSearchOpen(false);
    setSearchResults([]);
    setThreadMsg(null);
    setReadReceipts([]);
    loadMessages();
  }, [targetId, loadMessages]);

  // Send read receipt when messages change
  useEffect(() => {
    if (messages.length === 0 || !targetId) return;
    const lastMsg = messages[messages.length - 1];
    if (lastMsg.sender_id === user?.id) return;
    const endpoint = isChannel
      ? `/channels/${channel.id}/read`
      : `/dm/${conversation.id}/read`;
    api.post(endpoint, { last_message_id: lastMsg.id }).catch(() => {});
  }, [messages, targetId, isChannel, channel, conversation, user]);

  // Load read receipts
  useEffect(() => {
    if (!targetId) return;
    const loadReceipts = async () => {
      try {
        const endpoint = isChannel
          ? `/channels/${channel.id}/read-receipts`
          : `/dm/${conversation.id}/read-receipts`;
        const { data } = await api.get(endpoint);
        setReadReceipts(data);
      } catch {}
    };
    loadReceipts();
  }, [targetId, isChannel, channel, conversation]);

  useEffect(() => { messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);

  useEffect(() => {
    const websocket = ws?.current;
    if (!websocket) return;
    const handler = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'new_message' && data.message.conversation_id === conversation?.id) {
          setMessages(prev => [...prev, { ...data.message, reactions: [], thread_count: 0 }]);
        } else if (data.type === 'channel_message' && data.message.channel_id === channel?.id) {
          setMessages(prev => [...prev, { ...data.message, reactions: [], thread_count: 0 }]);
        } else if (data.type === 'reaction_update') {
          setMessages(prev => prev.map(m => m.id === data.message_id ? { ...m, reactions: data.reactions } : m));
        } else if (data.type === 'message_edited') {
          setMessages(prev => prev.map(m => m.id === data.message_id ? { ...m, content: data.content, edited: true } : m));
        } else if (data.type === 'message_deleted') {
          setMessages(prev => prev.filter(m => m.id !== data.message_id));
        } else if (data.type === 'thread_reply' && threadMsg?.id === data.parent_message_id) {
          setThreadReplies(prev => [...prev, data.reply]);
        } else if (data.type === 'typing' && data.user_id !== user.id) {
          setTypingUsers(prev => {
            const existing = prev.find(t => t.user_id === data.user_id);
            if (existing) return prev;
            const entry = { user_id: data.user_id };
            setTimeout(() => setTypingUsers(p => p.filter(t => t.user_id !== data.user_id)), 3000);
            return [...prev, entry];
          });
        } else if (data.type === 'read_receipt') {
          setReadReceipts(prev => {
            const filtered = prev.filter(r => r.user_id !== data.user_id);
            return [...filtered, { user_id: data.user_id, username: data.username, last_message_id: data.last_message_id, read_at: data.read_at }];
          });
        }
      } catch {}
    };
    websocket.addEventListener('message', handler);
    if (isChannel && channel?.id) {
      try { websocket.send(JSON.stringify({ type: 'subscribe_channel', channel_id: channel.id })); } catch {}
    } else if (conversation?.id) {
      try { websocket.send(JSON.stringify({ type: 'subscribe_dm', conversation_id: conversation.id })); } catch {}
    }
    return () => websocket.removeEventListener('message', handler);
  }, [ws, channel, conversation, isChannel, threadMsg]);

  const handleSend = async (e) => {
    e.preventDefault();
    if (!newMessage.trim()) return;
    try {
      const endpoint = isChannel ? `/channels/${channel.id}/messages` : `/dm/${conversation.id}/messages`;
      const { data } = await api.post(endpoint, { content: newMessage });
      setMessages(prev => [...prev, { ...data, reactions: data.reactions || [], thread_count: data.thread_count || 0 }]);
      setNewMessage('');
      setTypingUsers([]);
      inputRef.current?.focus();
    } catch {}
  };

  const handleGifSelect = async (gif) => {
    try {
      const content = `[gif](${gif.url})`;
      const endpoint = isChannel ? `/channels/${channel.id}/messages` : `/dm/${conversation.id}/messages`;
      const { data } = await api.post(endpoint, { content });
      setMessages(prev => [...prev, { ...data, reactions: data.reactions || [], thread_count: data.thread_count || 0 }]);
    } catch {}
  };

  const handleCustomEmojiSelect = async (emoji) => {
    const backendUrl = process.env.REACT_APP_BACKEND_URL || window.location.origin;
    const emojiUrl = `${backendUrl}/api/emojis/${emoji.id}/image`;
    const content = emoji.type === 'sticker' ? `[sticker:${emoji.name}](${emojiUrl})` : `[emoji:${emoji.name}](${emojiUrl})`;
    try {
      const endpoint = isChannel ? `/channels/${channel.id}/messages` : `/dm/${conversation.id}/messages`;
      const { data } = await api.post(endpoint, { content });
      setMessages(prev => [...prev, { ...data, reactions: data.reactions || [], thread_count: data.thread_count || 0 }]);
      setEmojiPickerOpen(false);
    } catch {}
  };

  const sendTypingIndicator = () => {
    const now = Date.now();
    if (now - lastTypingSentRef.current < 2000) return;
    lastTypingSentRef.current = now;
    const websocket = ws?.current;
    if (websocket?.readyState === WebSocket.OPEN) {
      const payload = isChannel
        ? { type: 'typing', channel_id: channel?.id }
        : { type: 'typing', conversation_id: conversation?.id };
      try { websocket.send(JSON.stringify(payload)); } catch {}
    }
  };

  const handleMessageInput = (e) => {
    setNewMessage(e.target.value);
    if (e.target.value.trim()) sendTypingIndicator();
  };

  const handleReaction = async (messageId, emoji) => {
    const endpoint = isChannel ? `/channel-messages/${messageId}/reactions` : `/messages/${messageId}/reactions`;
    const existing = messages.find(m => m.id === messageId)?.reactions?.find(r => r.emoji === emoji && r.user_id === user.id);
    try {
      if (existing) {
        await api.delete(`${endpoint}/${encodeURIComponent(emoji)}`);
      } else {
        await api.post(endpoint, { emoji });
      }
      loadMessages();
    } catch {}
  };

  const handleEdit = async (messageId) => {
    if (!editContent.trim()) return;
    const endpoint = isChannel ? `/channel-messages/${messageId}` : `/messages/${messageId}`;
    try {
      await api.put(endpoint, { content: editContent });
      setEditingId(null);
      setEditContent('');
    } catch {}
  };

  const handleDelete = async (messageId) => {
    const endpoint = isChannel ? `/channel-messages/${messageId}` : `/messages/${messageId}`;
    try {
      await api.delete(endpoint);
    } catch {}
  };

  const openThread = async (msg) => {
    setThreadMsg(msg);
    const endpoint = isChannel ? `/channel-messages/${msg.id}/thread` : `/messages/${msg.id}/thread`;
    try {
      const { data } = await api.get(endpoint);
      setThreadReplies(data);
    } catch {}
  };

  const sendThreadReply = async () => {
    if (!threadReply.trim() || !threadMsg) return;
    const endpoint = isChannel ? `/channel-messages/${threadMsg.id}/thread` : `/messages/${threadMsg.id}/thread`;
    try {
      const { data } = await api.post(endpoint, { content: threadReply });
      setThreadReplies(prev => [...prev, data]);
      setThreadReply('');
      setMessages(prev => prev.map(m => m.id === threadMsg.id ? { ...m, thread_count: (m.thread_count || 0) + 1 } : m));
    } catch {}
  };

  const handleFileUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      const { data: fileData } = await api.post('/upload?context=message', formData, { headers: { 'Content-Type': 'multipart/form-data' } });
      const attachmentText = `[File: ${fileData.original_filename}]`;
      const endpoint = isChannel ? `/channels/${channel.id}/messages` : `/dm/${conversation.id}/messages`;
      const { data } = await api.post(endpoint, { content: attachmentText, attachments: [fileData.id] });
      setMessages(prev => [...prev, { ...data, reactions: [], thread_count: 0 }]);
    } catch {}
    setUploading(false);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const handleSearch = async () => {
    if (!searchQuery.trim()) return;
    try {
      const { data } = await api.post('/dm/search', { query: searchQuery, conversation_id: conversation?.id || null, limit: 50 });
      setSearchResults(data);
    } catch {}
  };

  const title = isChannel
    ? channel?.name
    : conversation?.type === 'group_dm' ? conversation?.name : conversation?.other_user?.display_name || conversation?.other_user?.username || 'Chat';

  const formatTime = (ts) => new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  const formatDate = (ts) => {
    const d = new Date(ts);
    const today = new Date();
    if (d.toDateString() === today.toDateString()) return 'Today';
    const yesterday = new Date(today); yesterday.setDate(yesterday.getDate() - 1);
    if (d.toDateString() === yesterday.toDateString()) return 'Yesterday';
    return d.toLocaleDateString();
  };

  const groupReactions = (reactions) => {
    const grouped = {};
    (reactions || []).forEach(r => {
      if (!grouped[r.emoji]) grouped[r.emoji] = { emoji: r.emoji, count: 0, users: [], hasOwn: false };
      grouped[r.emoji].count++;
      grouped[r.emoji].users.push(r.username);
      if (r.user_id === user.id) grouped[r.emoji].hasOwn = true;
    });
    return Object.values(grouped);
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
        <div className="flex items-center gap-1">
          {!isChannel && (
            <button onClick={() => setSearchOpen(!searchOpen)} className="p-2 text-slate-400 hover:text-slate-200 hover:bg-slate-800/50 rounded transition-colors" data-testid="search-messages-btn">
              <Search className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>

      {/* Search panel */}
      {searchOpen && (
        <div className="px-4 py-3 border-b border-white/5 bg-slate-900/50" data-testid="search-panel">
          <div className="flex items-center gap-2">
            <Input value={searchQuery} onChange={e => setSearchQuery(e.target.value)} onKeyDown={e => e.key === 'Enter' && handleSearch()} placeholder="Search messages..." className="bg-slate-950/50 border-white/10 text-slate-100 text-sm flex-1" data-testid="search-input" />
            <button onClick={handleSearch} className="p-2 bg-emerald-500 text-slate-950 rounded hover:bg-emerald-400" data-testid="search-submit-btn"><Search className="w-4 h-4" /></button>
            <button onClick={() => { setSearchOpen(false); setSearchResults([]); }} className="p-2 text-slate-400 hover:text-slate-200"><X className="w-4 h-4" /></button>
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

      {/* Main content: Messages + Thread panel */}
      <div className="flex-1 flex min-h-0">
        {/* Messages */}
        <ScrollArea className="flex-1">
          <div className="p-4 space-y-0.5">
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
              const grouped = groupReactions(msg.reactions);

              return (
                <div key={msg.id}>
                  {showDate && (
                    <div className="flex items-center gap-4 my-4">
                      <div className="flex-1 h-px bg-white/5" />
                      <span className="text-xs font-mono text-slate-600 uppercase tracking-widest">{msgDate}</span>
                      <div className="flex-1 h-px bg-white/5" />
                    </div>
                  )}
                  <div className={`flex items-start gap-3 px-2 py-1 hover:bg-slate-900/50 rounded group transition-colors ${isGrouped ? 'mt-0' : 'mt-3'}`} data-testid={`message-${msg.id}`}>
                    {!isGrouped ? (
                      <div className="w-9 h-9 rounded-full bg-slate-800 flex items-center justify-center text-xs font-medium text-slate-300 flex-shrink-0 mt-0.5">
                        {msg.sender_username?.slice(0, 2).toUpperCase()}
                      </div>
                    ) : (
                      <div className="w-9 flex-shrink-0">
                        <span className="text-[10px] font-mono text-slate-700 opacity-0 group-hover:opacity-100 transition-opacity">{formatTime(msg.created_at)}</span>
                      </div>
                    )}
                    <div className="min-w-0 flex-1">
                      {!isGrouped && (
                        <div className="flex items-baseline gap-2 mb-0.5">
                          <span className="text-sm font-medium text-slate-200">{msg.sender_username}</span>
                          <span className="text-[10px] font-mono text-slate-600">{formatTime(msg.created_at)}</span>
                          {msg.edited && <span className="text-[10px] text-slate-600">(edited)</span>}
                        </div>
                      )}

                      {editingId === msg.id ? (
                        <div className="flex items-center gap-2">
                          <Input value={editContent} onChange={e => setEditContent(e.target.value)} onKeyDown={e => { if (e.key === 'Enter') handleEdit(msg.id); if (e.key === 'Escape') setEditingId(null); }} className="bg-slate-900 border-white/10 text-slate-100 text-sm flex-1" autoFocus data-testid="edit-message-input" />
                          <button onClick={() => handleEdit(msg.id)} className="text-emerald-400 hover:text-emerald-300 text-xs">Save</button>
                          <button onClick={() => setEditingId(null)} className="text-slate-500 hover:text-slate-300 text-xs">Cancel</button>
                        </div>
                      ) : (
                        <MessageContent content={msg.content} />
                      )}

                      {/* Reactions display */}
                      {grouped.length > 0 && (
                        <div className="flex flex-wrap gap-1 mt-1.5">
                          {grouped.map(r => (
                            <button
                              key={r.emoji}
                              onClick={() => handleReaction(msg.id, r.emoji)}
                              className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs border transition-colors ${
                                r.hasOwn ? 'bg-emerald-500/15 border-emerald-500/30 text-emerald-400' : 'bg-slate-800/50 border-white/5 text-slate-400 hover:border-white/10'
                              }`}
                              data-testid={`reaction-${msg.id}-${r.emoji}`}
                              title={r.users.join(', ')}
                            >
                              <span>{r.emoji}</span>
                              <span className="font-mono">{r.count}</span>
                            </button>
                          ))}
                        </div>
                      )}

                      {/* Thread indicator */}
                      {(msg.thread_count || 0) > 0 && (
                        <button onClick={() => openThread(msg)} className="flex items-center gap-1.5 mt-1.5 text-xs text-emerald-400 hover:text-emerald-300 transition-colors" data-testid={`thread-indicator-${msg.id}`}>
                          <MessageSquare className="w-3 h-3" />
                          <span>{msg.thread_count} {msg.thread_count === 1 ? 'reply' : 'replies'}</span>
                        </button>
                      )}

                      {/* Read receipts — show on last message from current user */}
                      {msg.sender_id === user?.id && (() => {
                        const readers = readReceipts.filter(r =>
                          r.user_id !== user?.id && r.last_message_id === msg.id
                        );
                        const isNextFromSame = messages[i + 1]?.sender_id === user?.id;
                        if (readers.length === 0 && !isNextFromSame) {
                          return (
                            <div className="flex items-center gap-1 mt-1" data-testid={`read-receipt-${msg.id}`}>
                              <CheckCheck className="w-3 h-3 text-slate-600" />
                              <span className="text-[10px] text-slate-600">Sent</span>
                            </div>
                          );
                        }
                        if (readers.length > 0) {
                          const names = readers.map(r => r.username).join(', ');
                          return (
                            <div className="flex items-center gap-1 mt-1" data-testid={`read-receipt-${msg.id}`}>
                              <CheckCheck className="w-3 h-3 text-emerald-500" />
                              <span className="text-[10px] text-slate-500">Seen by {names}</span>
                            </div>
                          );
                        }
                        return null;
                      })()}

                      {/* Action buttons (hover) */}
                      <div className="opacity-0 group-hover:opacity-100 transition-opacity flex items-center gap-0.5 mt-1">
                        <Popover>
                          <PopoverTrigger asChild>
                            <button className="p-1 text-slate-600 hover:text-slate-300 hover:bg-slate-800 rounded" data-testid={`reaction-picker-${msg.id}`}>
                              <Smile className="w-3.5 h-3.5" />
                            </button>
                          </PopoverTrigger>
                          <PopoverContent className="bg-slate-900 border-white/10 p-2 w-auto" align="start">
                            <div className="flex flex-wrap gap-1 max-w-[200px]">
                              {COMMON_EMOJIS.map(e => (
                                <button key={e} onClick={() => handleReaction(msg.id, e)} className="p-1.5 hover:bg-slate-800 rounded text-lg leading-none" data-testid={`emoji-${e}`}>
                                  {e}
                                </button>
                              ))}
                            </div>
                          </PopoverContent>
                        </Popover>
                        <button onClick={() => openThread(msg)} className="p-1 text-slate-600 hover:text-slate-300 hover:bg-slate-800 rounded" data-testid={`thread-btn-${msg.id}`}>
                          <MessageSquare className="w-3.5 h-3.5" />
                        </button>
                        {msg.sender_id === user.id && (
                          <>
                            <button onClick={() => { setEditingId(msg.id); setEditContent(msg.content); }} className="p-1 text-slate-600 hover:text-slate-300 hover:bg-slate-800 rounded" data-testid={`edit-btn-${msg.id}`}>
                              <Pencil className="w-3.5 h-3.5" />
                            </button>
                            <button onClick={() => handleDelete(msg.id)} className="p-1 text-slate-600 hover:text-red-400 hover:bg-slate-800 rounded" data-testid={`delete-btn-${msg.id}`}>
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          </>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
            <div ref={messagesEndRef} />
          </div>
        </ScrollArea>

        {/* Thread panel */}
        {threadMsg && (
          <div className="w-80 border-l border-white/5 flex flex-col bg-slate-900/30" data-testid="thread-panel">
            <div className="h-12 px-4 flex items-center justify-between border-b border-white/5">
              <span className="text-sm font-medium text-slate-100 font-['Outfit']">Thread</span>
              <button onClick={() => setThreadMsg(null)} className="text-slate-400 hover:text-slate-200" data-testid="close-thread-btn"><X className="w-4 h-4" /></button>
            </div>
            {/* Parent message */}
            <div className="p-3 border-b border-white/5">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-xs font-medium text-emerald-400">{threadMsg.sender_username}</span>
                <span className="text-[10px] font-mono text-slate-600">{formatTime(threadMsg.created_at)}</span>
              </div>
              <MessageContent content={threadMsg.content} />
            </div>
            {/* Replies */}
            <ScrollArea className="flex-1">
              <div className="p-3 space-y-3">
                {threadReplies.map(r => (
                  <div key={r.id} className="flex gap-2" data-testid={`thread-reply-${r.id}`}>
                    <div className="w-7 h-7 rounded-full bg-slate-800 flex items-center justify-center text-[10px] text-slate-400 flex-shrink-0">
                      {r.sender_username?.slice(0, 2).toUpperCase()}
                    </div>
                    <div>
                      <div className="flex items-center gap-1.5 mb-0.5">
                        <span className="text-xs font-medium text-slate-200">{r.sender_username}</span>
                        <span className="text-[10px] font-mono text-slate-600">{formatTime(r.created_at)}</span>
                      </div>
                      <MessageContent content={r.content} />
                    </div>
                  </div>
                ))}
              </div>
            </ScrollArea>
            {/* Thread reply input */}
            <div className="p-3 border-t border-white/5">
              <div className="flex items-center gap-2">
                <Input value={threadReply} onChange={e => setThreadReply(e.target.value)} onKeyDown={e => e.key === 'Enter' && sendThreadReply()} placeholder="Reply..." className="bg-slate-950/50 border-white/10 text-slate-100 text-sm" data-testid="thread-reply-input" />
                <button onClick={sendThreadReply} className="p-2 bg-emerald-500 text-slate-950 rounded hover:bg-emerald-400" data-testid="thread-send-btn"><Send className="w-3.5 h-3.5" /></button>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Typing indicator */}
      {typingUsers.length > 0 && (
        <div className="px-4 py-1 flex items-center gap-2 border-t border-white/5" data-testid="typing-indicator">
          <div className="flex gap-0.5">
            <span className="w-1.5 h-1.5 bg-emerald-500 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
            <span className="w-1.5 h-1.5 bg-emerald-500 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
            <span className="w-1.5 h-1.5 bg-emerald-500 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
          </div>
          <span className="text-xs text-slate-500 font-['IBM_Plex_Sans']">Someone is typing...</span>
        </div>
      )}

      {/* GIF picker */}
      {gifPickerOpen && (
        <div className="absolute bottom-20 left-16 z-50" data-testid="gif-picker-container">
          <GifPicker onSelect={handleGifSelect} onClose={() => setGifPickerOpen(false)} />
        </div>
      )}

      {/* Custom emoji picker */}
      {emojiPickerOpen && (
        <div className="absolute bottom-20 left-28 z-50" data-testid="custom-emoji-picker-container">
          <EmojiManager onSelect={handleCustomEmojiSelect} onClose={() => setEmojiPickerOpen(false)} />
        </div>
      )}

      {/* Message input */}
      <div className="p-4 border-t border-white/5 flex-shrink-0 relative">
        <form onSubmit={handleSend} className="flex items-center gap-2">
          <input type="file" ref={fileInputRef} onChange={handleFileUpload} className="hidden" data-testid="file-upload-input" />
          <button type="button" onClick={() => fileInputRef.current?.click()} className="p-2.5 text-slate-400 hover:text-slate-200 hover:bg-slate-800 rounded-md transition-colors" disabled={uploading} data-testid="attach-file-btn">
            {uploading ? <Upload className="w-4 h-4 animate-pulse" /> : <Paperclip className="w-4 h-4" />}
          </button>
          <button type="button" onClick={() => setGifPickerOpen(!gifPickerOpen)} className={`p-2.5 rounded-md transition-colors ${gifPickerOpen ? 'text-emerald-400 bg-emerald-500/10' : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'}`} data-testid="gif-picker-btn">
            <ImageIcon className="w-4 h-4" />
          </button>
          <button type="button" onClick={() => setEmojiPickerOpen(!emojiPickerOpen)} className={`p-2.5 rounded-md transition-colors ${emojiPickerOpen ? 'text-emerald-400 bg-emerald-500/10' : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'}`} data-testid="custom-emoji-btn">
            <Sticker className="w-4 h-4" />
          </button>
          <div className="flex-1 relative">
            <Input ref={inputRef} value={newMessage} onChange={handleMessageInput} placeholder={`Message ${isChannel ? '#' : ''}${title}`} className="bg-slate-900 border-white/10 text-slate-100 pr-10 focus:ring-1 focus:ring-emerald-500/50 font-['IBM_Plex_Sans']" data-testid="chat-message-input" />
          </div>
          <button type="submit" className="p-2.5 bg-emerald-500 text-slate-950 rounded-md hover:bg-emerald-400 transition-colors disabled:opacity-50" disabled={!newMessage.trim()} data-testid="chat-send-btn">
            <Send className="w-4 h-4" />
          </button>
        </form>
      </div>
    </div>
  );
}

// Renders message content with inline GIF, emoji, and sticker support
function MessageContent({ content }) {
  const gifMatch = content?.match(/^\[gif\]\((https?:\/\/[^\s)]+)\)$/);
  if (gifMatch) {
    return (
      <div className="mt-1 max-w-sm">
        <img src={gifMatch[1]} alt="GIF" className="rounded-lg max-h-64 w-auto" loading="lazy" data-testid="gif-message-image" />
      </div>
    );
  }
  // Custom sticker
  const stickerMatch = content?.match(/^\[sticker:([^\]]+)\]\((https?:\/\/[^\s)]+)\)$/);
  if (stickerMatch) {
    return (
      <div className="mt-1">
        <img src={stickerMatch[2]} alt={stickerMatch[1]} className="w-32 h-32 object-contain" loading="lazy" data-testid="sticker-message-image" />
      </div>
    );
  }
  // Custom emoji (inline)
  const emojiMatch = content?.match(/^\[emoji:([^\]]+)\]\((https?:\/\/[^\s)]+)\)$/);
  if (emojiMatch) {
    return (
      <div className="mt-0.5 inline-block">
        <img src={emojiMatch[2]} alt={emojiMatch[1]} className="w-8 h-8 object-contain inline" loading="lazy" data-testid="custom-emoji-message" />
      </div>
    );
  }
  // Check for image URLs
  const imgMatch = content?.match(/^(https?:\/\/\S+\.(gif|png|jpg|jpeg|webp)(\?\S*)?)$/i);
  if (imgMatch) {
    return (
      <div className="mt-1 max-w-sm">
        <img src={imgMatch[1]} alt="Image" className="rounded-lg max-h-64 w-auto" loading="lazy" />
      </div>
    );
  }
  return <p className="text-sm text-slate-300 leading-relaxed break-words font-['IBM_Plex_Sans']">{content}</p>;
}
