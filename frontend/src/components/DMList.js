import { ScrollArea } from '../components/ui/scroll-area';
import { MessageCircle, Users, Plus, X, Check } from 'lucide-react';
import { useState } from 'react';
import api from '../lib/api';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '../components/ui/dialog';
import { Input } from '../components/ui/input';
import { Button } from '../components/ui/button';

export default function DMList({ conversations, activeConversation, onSelectConversation, onSelectFriends, activeView, user }) {
  const [showGroupCreate, setShowGroupCreate] = useState(false);
  const [groupName, setGroupName] = useState('');
  const [selectedFriends, setSelectedFriends] = useState([]);
  const [friends, setFriends] = useState([]);

  const loadFriends = async () => {
    try {
      const { data } = await api.get('/friends');
      setFriends(data.friends || []);
    } catch {}
  };

  const handleCreateGroup = async () => {
    if (selectedFriends.length < 1) return;
    try {
      const { data } = await api.post('/dm/group', {
        name: groupName.trim() || 'Group Chat',
        member_ids: selectedFriends
      });
      setShowGroupCreate(false);
      setGroupName('');
      setSelectedFriends([]);
      onSelectConversation(data);
    } catch {}
  };

  const toggleFriend = (id) => {
    setSelectedFriends(prev =>
      prev.includes(id) ? prev.filter(f => f !== id) : [...prev, id]
    );
  };

  return (
    <div className="w-60 bg-slate-900/50 border-r border-white/5 flex flex-col h-full" data-testid="dm-list">
      <div className="h-12 px-4 flex items-center justify-between border-b border-white/5 flex-shrink-0">
        <button
          onClick={onSelectFriends}
          className={`text-sm font-medium transition-colors ${activeView === 'friends' ? 'text-slate-100' : 'text-slate-400 hover:text-slate-200'} font-['Outfit']`}
          data-testid="friends-nav-btn"
        >
          Friends
        </button>
        <Dialog open={showGroupCreate} onOpenChange={(open) => { setShowGroupCreate(open); if (open) loadFriends(); }}>
          <DialogTrigger asChild>
            <button className="p-1.5 text-slate-400 hover:text-slate-200 rounded hover:bg-slate-800/50 transition-colors" data-testid="create-group-dm-btn">
              <Plus className="w-4 h-4" />
            </button>
          </DialogTrigger>
          <DialogContent className="bg-slate-900 border-white/10 text-slate-100 max-w-sm">
            <DialogHeader><DialogTitle className="font-['Outfit']">Create Group DM</DialogTitle></DialogHeader>
            <div className="space-y-4 pt-2">
              <Input
                value={groupName}
                onChange={e => setGroupName(e.target.value)}
                placeholder="Group name (optional)"
                className="bg-slate-950/50 border-white/10 text-slate-100"
                data-testid="group-dm-name-input"
              />
              <p className="text-xs text-slate-500">Select friends to add:</p>
              <ScrollArea className="max-h-48">
                <div className="space-y-1">
                  {friends.map(f => (
                    <button
                      key={f.id}
                      onClick={() => toggleFriend(f.id)}
                      className={`w-full flex items-center gap-3 px-3 py-2 rounded text-sm transition-colors ${
                        selectedFriends.includes(f.id) ? 'bg-emerald-500/10 border border-emerald-500/30' : 'hover:bg-slate-800/50 border border-transparent'
                      }`}
                      data-testid={`group-select-${f.id}`}
                    >
                      <div className="w-7 h-7 rounded-full bg-slate-800 flex items-center justify-center text-xs text-slate-300">
                        {(f.display_name || f.username)?.slice(0, 2).toUpperCase()}
                      </div>
                      <span className="text-slate-200 flex-1 text-left">{f.display_name || f.username}</span>
                      {selectedFriends.includes(f.id) && <Check className="w-4 h-4 text-emerald-400" />}
                    </button>
                  ))}
                  {friends.length === 0 && <p className="text-xs text-slate-500 text-center py-4">Add friends first</p>}
                </div>
              </ScrollArea>
              <Button
                onClick={handleCreateGroup}
                disabled={selectedFriends.length < 1}
                className="w-full bg-emerald-500 text-slate-950 hover:bg-emerald-400 disabled:opacity-50"
                data-testid="create-group-dm-submit"
              >
                Create Group ({selectedFriends.length} selected)
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      <ScrollArea className="flex-1">
        <div className="p-1.5">
          <p className="text-[10px] font-mono uppercase tracking-widest text-slate-600 px-3 mb-2 mt-2">Direct Messages</p>
          {conversations.map(conv => {
            const isActive = activeConversation?.id === conv.id;
            const name = conv.type === 'group_dm'
              ? conv.name
              : (conv.other_user?.display_name || conv.other_user?.username || 'User');
            const isOnline = conv.other_user?.is_online;
            const lastMsg = conv.last_message;
            const lastContent = lastMsg?.e2e ? 'Encrypted message' : lastMsg?.content?.substring(0, 30);

            return (
              <button
                key={conv.id}
                onClick={() => onSelectConversation(conv)}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded text-left transition-colors ${
                  isActive ? 'bg-slate-800 text-slate-100' : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
                }`}
                data-testid={`dm-conv-${conv.id}`}
              >
                <div className="relative flex-shrink-0">
                  <div className="w-9 h-9 rounded-full bg-slate-800 flex items-center justify-center text-xs font-medium text-slate-300">
                    {conv.type === 'group_dm' ? <Users className="w-4 h-4" /> : name?.slice(0, 2).toUpperCase()}
                  </div>
                  {conv.type === 'dm' && (
                    <div className={`absolute -bottom-0.5 -right-0.5 w-2.5 h-2.5 rounded-full border-2 border-slate-900 ${isOnline ? 'bg-emerald-500' : 'bg-slate-600'}`} />
                  )}
                </div>
                <div className="min-w-0 flex-1">
                  <p className="text-sm truncate font-['IBM_Plex_Sans']">{name}</p>
                  {lastContent && <p className="text-xs text-slate-500 truncate">{lastContent}</p>}
                </div>
              </button>
            );
          })}
          {conversations.length === 0 && (
            <p className="text-xs text-slate-500 text-center py-8">No conversations yet</p>
          )}
        </div>
      </ScrollArea>
    </div>
  );
}
