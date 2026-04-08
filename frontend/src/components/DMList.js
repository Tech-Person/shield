import { MessageCircle, Users, Plus } from 'lucide-react';
import { ScrollArea } from '../components/ui/scroll-area';

export default function DMList({ conversations, activeConversation, onSelectConversation, onSelectFriends, activeView, user }) {
  return (
    <div className="w-60 bg-slate-900/50 border-r border-white/5 flex flex-col h-full" data-testid="dm-list">
      <div className="h-12 px-4 flex items-center border-b border-white/5 flex-shrink-0">
        <span className="text-sm font-medium text-slate-100 font-['Outfit']">Messages</span>
      </div>

      <div className="p-2">
        <button
          onClick={onSelectFriends}
          className={`w-full flex items-center gap-2 px-3 py-2 rounded text-sm transition-colors ${
            activeView === 'friends' ? 'bg-slate-800 text-slate-100' : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
          }`}
          data-testid="friends-btn"
        >
          <Users className="w-4 h-4" />
          Friends
        </button>
      </div>

      <div className="px-4 py-1">
        <span className="text-xs font-mono uppercase tracking-widest text-slate-500">Direct Messages</span>
      </div>

      <ScrollArea className="flex-1">
        <div className="p-2 space-y-0.5">
          {conversations.map(conv => {
            const otherUser = conv.other_user;
            const displayName = conv.type === 'group_dm'
              ? conv.name
              : otherUser?.display_name || otherUser?.username || 'Unknown';
            const isActive = activeConversation?.id === conv.id;
            const lastMsg = conv.last_message;

            return (
              <button
                key={conv.id}
                onClick={() => onSelectConversation(conv)}
                className={`w-full flex items-center gap-3 px-2 py-2 rounded transition-colors ${
                  isActive ? 'bg-slate-800 text-slate-100' : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
                }`}
                data-testid={`dm-conv-${conv.id}`}
              >
                <div className="relative flex-shrink-0">
                  <div className="w-8 h-8 rounded-full bg-slate-800 flex items-center justify-center text-xs font-medium text-slate-300">
                    {conv.type === 'group_dm' ? <Users className="w-4 h-4" /> : displayName.slice(0, 2).toUpperCase()}
                  </div>
                  {otherUser?.is_online && (
                    <div className="absolute -bottom-0.5 -right-0.5 w-3 h-3 rounded-full border-2 border-slate-900 bg-emerald-500" />
                  )}
                </div>
                <div className="min-w-0 flex-1 text-left">
                  <p className="text-sm truncate">{displayName}</p>
                  {lastMsg && (
                    <p className="text-xs text-slate-600 truncate">{lastMsg.content}</p>
                  )}
                </div>
              </button>
            );
          })}
          {conversations.length === 0 && (
            <p className="text-xs text-slate-600 text-center py-4 font-['IBM_Plex_Sans']">No conversations yet</p>
          )}
        </div>
      </ScrollArea>
    </div>
  );
}
