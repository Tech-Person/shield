import { ScrollArea } from '../components/ui/scroll-area';
import { Crown, Shield } from 'lucide-react';

export default function MembersPanel({ server }) {
  const members = server?.members || [];
  const onlineMembers = members.filter(m => m.is_online);
  const offlineMembers = members.filter(m => !m.is_online);

  return (
    <div className="w-60 bg-slate-900/30 border-l border-white/5 hidden lg:block" data-testid="members-panel">
      <ScrollArea className="h-full">
        <div className="p-3">
          {onlineMembers.length > 0 && (
            <>
              <p className="text-xs font-mono uppercase tracking-widest text-slate-500 px-2 mb-2">
                Online — {onlineMembers.length}
              </p>
              {onlineMembers.map(m => (
                <MemberItem key={m.id} member={m} server={server} online />
              ))}
            </>
          )}
          {offlineMembers.length > 0 && (
            <>
              <p className="text-xs font-mono uppercase tracking-widest text-slate-500 px-2 mb-2 mt-4">
                Offline — {offlineMembers.length}
              </p>
              {offlineMembers.map(m => (
                <MemberItem key={m.id} member={m} server={server} />
              ))}
            </>
          )}
        </div>
      </ScrollArea>
    </div>
  );
}

function MemberItem({ member, server, online }) {
  const isOwner = member.user_id === server?.owner_id;

  return (
    <div className={`flex items-center gap-2 px-2 py-1.5 rounded hover:bg-slate-800/50 transition-colors cursor-pointer ${!online ? 'opacity-40' : ''}`} data-testid={`member-${member.user_id}`}>
      <div className="relative">
        <div className="w-8 h-8 rounded-full bg-slate-800 flex items-center justify-center text-xs font-medium text-slate-300">
          {member.display_name?.slice(0, 2).toUpperCase() || member.username?.slice(0, 2).toUpperCase()}
        </div>
        <div className={`absolute -bottom-0.5 -right-0.5 w-3 h-3 rounded-full border-2 border-slate-900 ${online ? 'bg-emerald-500' : 'bg-slate-600'}`} />
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-1">
          <span className="text-sm text-slate-300 truncate">{member.display_name || member.username}</span>
          {isOwner && <Crown className="w-3 h-3 text-amber-500 flex-shrink-0" />}
        </div>
      </div>
    </div>
  );
}
