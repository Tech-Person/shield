import { ScrollArea } from '../components/ui/scroll-area';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '../components/ui/tooltip';

export default function MembersPanel({ server }) {
  const members = server?.members || [];
  const onlineMembers = members.filter(m => m.is_online && m.status !== 'invisible');
  const offlineMembers = members.filter(m => !m.is_online || m.status === 'invisible');

  const statusColor = (m) => {
    if (!m.is_online) return 'bg-slate-600';
    switch (m.status) {
      case 'away': return 'bg-amber-500';
      case 'busy': return 'bg-red-500';
      case 'invisible': return 'bg-slate-600';
      default: return 'bg-emerald-500';
    }
  };

  const renderMember = (m) => (
    <TooltipProvider key={m.user_id} delayDuration={300}>
      <Tooltip>
        <TooltipTrigger asChild>
          <div className="flex items-center gap-3 px-3 py-1.5 hover:bg-white/[0.03] rounded cursor-default" data-testid={`member-${m.user_id}`}>
            <div className="relative flex-shrink-0">
              <div className="w-8 h-8 rounded-full bg-slate-800 flex items-center justify-center text-xs font-medium text-slate-300">
                {(m.display_name || m.username)?.slice(0, 2).toUpperCase()}
              </div>
              <div className={`absolute -bottom-0.5 -right-0.5 w-3 h-3 rounded-full border-2 border-[#0f172a] ${statusColor(m)}`} />
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-sm text-slate-300 truncate font-['IBM_Plex_Sans']">{m.display_name || m.username}</p>
              {m.status_message && (
                <p className="text-[10px] text-slate-500 truncate">{m.status_message}</p>
              )}
            </div>
            {m.is_owner && <span className="text-[10px] font-mono text-amber-500/60">OWNER</span>}
          </div>
        </TooltipTrigger>
        <TooltipContent side="left" className="bg-slate-900 border-white/10 text-slate-300 text-xs">
          <p className="font-medium">{m.display_name || m.username}</p>
          {m.status_message && <p className="text-slate-500 mt-0.5">{m.status_message}</p>}
          <p className="text-slate-600 mt-0.5 font-mono">{m.is_online ? (m.status || 'online') : 'offline'}</p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );

  return (
    <div className="w-60 bg-slate-950/50 border-l border-white/5 hidden lg:block" data-testid="members-panel">
      <ScrollArea className="h-full">
        <div className="p-3">
          <p className="text-[10px] font-mono uppercase tracking-widest text-slate-600 px-3 mb-2" data-testid="online-count">
            Online — {onlineMembers.length}
          </p>
          {onlineMembers.map(renderMember)}

          {offlineMembers.length > 0 && (
            <>
              <p className="text-[10px] font-mono uppercase tracking-widest text-slate-600 px-3 mt-4 mb-2" data-testid="offline-count">
                Offline — {offlineMembers.length}
              </p>
              {offlineMembers.map(m => (
                <div key={m.user_id} className="flex items-center gap-3 px-3 py-1.5 opacity-40" data-testid={`member-${m.user_id}`}>
                  <div className="relative flex-shrink-0">
                    <div className="w-8 h-8 rounded-full bg-slate-800 flex items-center justify-center text-xs font-medium text-slate-400">
                      {(m.display_name || m.username)?.slice(0, 2).toUpperCase()}
                    </div>
                    <div className="absolute -bottom-0.5 -right-0.5 w-3 h-3 rounded-full border-2 border-[#0f172a] bg-slate-600" />
                  </div>
                  <p className="text-sm text-slate-400 truncate font-['IBM_Plex_Sans']">{m.display_name || m.username}</p>
                </div>
              ))}
            </>
          )}
        </div>
      </ScrollArea>
    </div>
  );
}
