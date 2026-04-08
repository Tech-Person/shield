import { useState, useEffect, useCallback } from 'react';
import api from '../lib/api';
import { formatApiError } from '../lib/api';
import { useAuth } from '../contexts/AuthContext';
import { UserPlus, UserX, Ban, MessageCircle, Search, Check, X, Clock, ShieldOff } from 'lucide-react';
import { Input } from '../components/ui/input';
import { Button } from '../components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { ScrollArea } from '../components/ui/scroll-area';

export default function FriendsList({ onStartDM }) {
  const { user } = useAuth();
  const [friends, setFriends] = useState([]);
  const [pendingIn, setPendingIn] = useState([]);
  const [pendingOut, setPendingOut] = useState([]);
  const [blocked, setBlocked] = useState([]);
  const [searchUsername, setSearchUsername] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const loadFriends = useCallback(async () => {
    try {
      const { data } = await api.get('/friends');
      setFriends(data.friends);
      setPendingIn(data.pending_incoming);
      setPendingOut(data.pending_outgoing);
      setBlocked(data.blocked);
    } catch {}
  }, []);

  useEffect(() => { loadFriends(); }, [loadFriends]);

  const handleAddFriend = async () => {
    setError('');
    setSuccess('');
    if (!searchUsername.trim()) return;
    try {
      const { data } = await api.post('/friends/request', { username: searchUsername });
      setSuccess(data.message);
      setSearchUsername('');
      loadFriends();
    } catch (err) {
      setError(formatApiError(err.response?.data?.detail));
    }
  };

  const handleAccept = async (userId) => {
    try {
      await api.post(`/friends/accept/${userId}`);
      loadFriends();
    } catch {}
  };

  const handleReject = async (userId) => {
    try {
      await api.post(`/friends/reject/${userId}`);
      loadFriends();
    } catch {}
  };

  const handleRemove = async (userId) => {
    try {
      await api.delete(`/friends/${userId}`);
      loadFriends();
    } catch {}
  };

  const handleBlock = async (userId) => {
    try {
      await api.post(`/friends/block/${userId}`);
      loadFriends();
    } catch {}
  };

  const handleUnblock = async (userId) => {
    try {
      await api.post(`/friends/unblock/${userId}`);
      loadFriends();
    } catch {}
  };

  const handleStartDM = async (friendId) => {
    try {
      const { data } = await api.post('/dm/create', { recipient_id: friendId, content: '' });
      onStartDM(data);
    } catch {}
  };

  const handleSearch = async () => {
    if (!searchUsername.trim()) return;
    try {
      const { data } = await api.get(`/users/search?q=${searchUsername}`);
      setSearchResults(data.filter(u => u.id !== user.id));
    } catch {}
  };

  return (
    <div className="flex-1 flex flex-col bg-[#020617]" data-testid="friends-list">
      <div className="h-12 px-6 flex items-center border-b border-white/5 flex-shrink-0">
        <span className="text-sm font-medium text-slate-100 font-['Outfit']">Friends</span>
      </div>

      <div className="flex-1 p-6">
        {/* Add Friend */}
        <div className="mb-6">
          <h3 className="text-sm font-medium text-slate-200 mb-3 font-['Outfit']">Add Friend</h3>
          <div className="flex items-center gap-2">
            <Input
              value={searchUsername}
              onChange={e => setSearchUsername(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleAddFriend()}
              placeholder="Enter username"
              className="bg-slate-900 border-white/10 text-slate-100 max-w-sm"
              data-testid="add-friend-input"
            />
            <Button onClick={handleAddFriend} className="bg-emerald-500 text-slate-950 hover:bg-emerald-400" data-testid="add-friend-btn">
              <UserPlus className="w-4 h-4 mr-2" /> Send Request
            </Button>
            <Button variant="outline" onClick={handleSearch} className="border-slate-700 text-slate-300 hover:bg-slate-800" data-testid="search-users-btn">
              <Search className="w-4 h-4 mr-2" /> Search
            </Button>
          </div>
          {error && <p className="text-red-400 text-sm mt-2" data-testid="friend-error">{error}</p>}
          {success && <p className="text-emerald-400 text-sm mt-2" data-testid="friend-success">{success}</p>}

          {searchResults.length > 0 && (
            <div className="mt-3 space-y-1 max-w-sm">
              {searchResults.map(u => (
                <div key={u.id} className="flex items-center justify-between px-3 py-2 bg-slate-900/50 rounded border border-white/5">
                  <div className="flex items-center gap-2">
                    <div className="w-8 h-8 rounded-full bg-slate-800 flex items-center justify-center text-xs text-slate-300">
                      {u.username?.slice(0, 2).toUpperCase()}
                    </div>
                    <span className="text-sm text-slate-200">{u.username}</span>
                  </div>
                  <Button size="sm" onClick={() => { setSearchUsername(u.username); handleAddFriend(); }} className="bg-emerald-500/20 text-emerald-400 hover:bg-emerald-500/30 h-7 text-xs">
                    Add
                  </Button>
                </div>
              ))}
            </div>
          )}
        </div>

        <Tabs defaultValue="all" className="w-full">
          <TabsList className="bg-slate-900/50 border border-white/5">
            <TabsTrigger value="all" className="data-[state=active]:bg-slate-800 text-slate-400 data-[state=active]:text-slate-100">
              All ({friends.length})
            </TabsTrigger>
            <TabsTrigger value="online" className="data-[state=active]:bg-slate-800 text-slate-400 data-[state=active]:text-slate-100">
              Online ({friends.filter(f => f.is_online).length})
            </TabsTrigger>
            <TabsTrigger value="pending" className="data-[state=active]:bg-slate-800 text-slate-400 data-[state=active]:text-slate-100">
              Pending ({pendingIn.length + pendingOut.length})
            </TabsTrigger>
            <TabsTrigger value="blocked" className="data-[state=active]:bg-slate-800 text-slate-400 data-[state=active]:text-slate-100">
              Blocked ({blocked.length})
            </TabsTrigger>
          </TabsList>

          <TabsContent value="all">
            <FriendListView friends={friends} onMessage={handleStartDM} onRemove={handleRemove} onBlock={handleBlock} />
          </TabsContent>
          <TabsContent value="online">
            <FriendListView friends={friends.filter(f => f.is_online)} onMessage={handleStartDM} onRemove={handleRemove} onBlock={handleBlock} />
          </TabsContent>
          <TabsContent value="pending">
            <ScrollArea className="max-h-[60vh]">
              <div className="space-y-1 mt-2">
                {pendingIn.map(p => (
                  <div key={p.id} className="flex items-center justify-between px-4 py-3 rounded bg-slate-900/30 border border-white/5">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-full bg-slate-800 flex items-center justify-center text-sm text-slate-300">
                        {p.username?.slice(0, 2).toUpperCase()}
                      </div>
                      <div>
                        <p className="text-sm text-slate-200">{p.username}</p>
                        <p className="text-xs text-slate-500 flex items-center gap-1"><Clock className="w-3 h-3" /> Incoming request</p>
                      </div>
                    </div>
                    <div className="flex gap-2">
                      <button onClick={() => handleAccept(p.id)} className="p-2 text-emerald-400 hover:bg-emerald-500/20 rounded" data-testid={`accept-friend-${p.id}`}>
                        <Check className="w-4 h-4" />
                      </button>
                      <button onClick={() => handleReject(p.id)} className="p-2 text-red-400 hover:bg-red-500/20 rounded" data-testid={`reject-friend-${p.id}`}>
                        <X className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                ))}
                {pendingOut.map(p => (
                  <div key={p.id} className="flex items-center justify-between px-4 py-3 rounded bg-slate-900/30 border border-white/5 opacity-60">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-full bg-slate-800 flex items-center justify-center text-sm text-slate-300">
                        {p.username?.slice(0, 2).toUpperCase()}
                      </div>
                      <div>
                        <p className="text-sm text-slate-200">{p.username}</p>
                        <p className="text-xs text-slate-500">Outgoing request</p>
                      </div>
                    </div>
                  </div>
                ))}
                {pendingIn.length === 0 && pendingOut.length === 0 && (
                  <p className="text-slate-500 text-sm text-center py-8">No pending requests</p>
                )}
              </div>
            </ScrollArea>
          </TabsContent>
          <TabsContent value="blocked">
            <ScrollArea className="max-h-[60vh]">
              <div className="space-y-1 mt-2">
                {blocked.map(uid => (
                  <div key={uid} className="flex items-center justify-between px-4 py-3 rounded bg-slate-900/30 border border-white/5">
                    <span className="text-sm text-slate-400 font-mono">{uid}</span>
                    <button onClick={() => handleUnblock(uid)} className="p-2 text-slate-400 hover:text-slate-200 hover:bg-slate-800 rounded" data-testid={`unblock-${uid}`}>
                      <ShieldOff className="w-4 h-4" />
                    </button>
                  </div>
                ))}
                {blocked.length === 0 && <p className="text-slate-500 text-sm text-center py-8">No blocked users</p>}
              </div>
            </ScrollArea>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}

function FriendListView({ friends, onMessage, onRemove, onBlock }) {
  if (friends.length === 0) {
    return <p className="text-slate-500 text-sm text-center py-8 mt-2">No friends yet. Add someone above!</p>;
  }

  return (
    <ScrollArea className="max-h-[60vh]">
      <div className="space-y-1 mt-2">
        {friends.map(f => (
          <div key={f.id} className="flex items-center justify-between px-4 py-3 rounded hover:bg-slate-900/50 transition-colors border border-transparent hover:border-white/5" data-testid={`friend-${f.id}`}>
            <div className="flex items-center gap-3">
              <div className="relative">
                <div className="w-10 h-10 rounded-full bg-slate-800 flex items-center justify-center text-sm text-slate-300">
                  {f.display_name?.slice(0, 2).toUpperCase() || f.username?.slice(0, 2).toUpperCase()}
                </div>
                <div className={`absolute -bottom-0.5 -right-0.5 w-3 h-3 rounded-full border-2 border-[#020617] ${f.is_online ? 'bg-emerald-500' : 'bg-slate-600'}`} />
              </div>
              <div>
                <p className="text-sm text-slate-200">{f.display_name || f.username}</p>
                <p className="text-xs text-slate-500">{f.status_message || (f.is_online ? 'Online' : 'Offline')}</p>
              </div>
            </div>
            <div className="flex gap-1">
              <button onClick={() => onMessage(f.id)} className="p-2 text-slate-400 hover:text-emerald-400 hover:bg-slate-800 rounded transition-colors" data-testid={`dm-friend-${f.id}`}>
                <MessageCircle className="w-4 h-4" />
              </button>
              <button onClick={() => onRemove(f.id)} className="p-2 text-slate-400 hover:text-red-400 hover:bg-slate-800 rounded transition-colors" data-testid={`remove-friend-${f.id}`}>
                <UserX className="w-4 h-4" />
              </button>
              <button onClick={() => onBlock(f.id)} className="p-2 text-slate-400 hover:text-red-400 hover:bg-slate-800 rounded transition-colors" data-testid={`block-friend-${f.id}`}>
                <Ban className="w-4 h-4" />
              </button>
            </div>
          </div>
        ))}
      </div>
    </ScrollArea>
  );
}
