import { useState, useEffect, useRef, useCallback } from 'react';
import api from '../lib/api';
import { Search, X, Loader2, TrendingUp } from 'lucide-react';
import { Input } from '../components/ui/input';
import { ScrollArea } from '../components/ui/scroll-area';

export default function GifPicker({ onSelect, onClose }) {
  const [query, setQuery] = useState('');
  const [gifs, setGifs] = useState([]);
  const [loading, setLoading] = useState(false);
  const [mode, setMode] = useState('trending');
  const searchTimeout = useRef(null);

  const loadTrending = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await api.get('/gifs/trending', { params: { limit: 30 } });
      setGifs(data.gifs || []);
    } catch {
      setGifs([]);
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    loadTrending();
  }, [loadTrending]);

  const handleSearch = useCallback(async (searchQuery) => {
    if (!searchQuery.trim()) {
      setMode('trending');
      loadTrending();
      return;
    }
    setMode('search');
    setLoading(true);
    try {
      const { data } = await api.get('/gifs/search', { params: { q: searchQuery, limit: 30 } });
      setGifs(data.gifs || []);
    } catch {
      setGifs([]);
    }
    setLoading(false);
  }, [loadTrending]);

  const handleInputChange = (e) => {
    const val = e.target.value;
    setQuery(val);
    clearTimeout(searchTimeout.current);
    searchTimeout.current = setTimeout(() => handleSearch(val), 400);
  };

  const handleSelectGif = (gif) => {
    onSelect(gif);
    onClose();
  };

  return (
    <div className="w-[380px] bg-slate-900 border border-white/10 rounded-lg shadow-2xl overflow-hidden" data-testid="gif-picker">
      {/* Header */}
      <div className="flex items-center gap-2 p-3 border-b border-white/5">
        <div className="relative flex-1">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-500" />
          <Input
            value={query}
            onChange={handleInputChange}
            placeholder="Search GIFs..."
            className="bg-slate-950/50 border-white/10 text-slate-100 text-sm pl-8 h-9"
            autoFocus
            data-testid="gif-search-input"
          />
        </div>
        <button
          onClick={onClose}
          className="p-1.5 text-slate-400 hover:text-slate-200 hover:bg-slate-800 rounded transition-colors"
          data-testid="gif-close-btn"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Label */}
      <div className="px-3 py-1.5 flex items-center gap-1.5">
        <TrendingUp className="w-3 h-3 text-emerald-500" />
        <span className="text-[10px] font-mono uppercase tracking-widest text-slate-500">
          {mode === 'trending' ? 'Trending' : `Results for "${query}"`}
        </span>
      </div>

      {/* GIF Grid */}
      <ScrollArea className="h-[320px]">
        {loading ? (
          <div className="flex items-center justify-center h-full">
            <Loader2 className="w-6 h-6 text-emerald-500 animate-spin" />
          </div>
        ) : gifs.length === 0 ? (
          <div className="flex items-center justify-center h-full text-slate-500 text-sm">
            No GIFs found
          </div>
        ) : (
          <div className="columns-2 gap-1.5 p-2">
            {gifs.map((gif) => (
              <button
                key={gif.id}
                onClick={() => handleSelectGif(gif)}
                className="w-full mb-1.5 rounded overflow-hidden hover:ring-2 hover:ring-emerald-500/50 transition-all cursor-pointer block"
                data-testid={`gif-item-${gif.id}`}
              >
                <img
                  src={gif.preview}
                  alt={gif.title}
                  loading="lazy"
                  className="w-full h-auto block"
                  style={{ minHeight: '60px', backgroundColor: '#0f172a' }}
                />
              </button>
            ))}
          </div>
        )}
      </ScrollArea>

      {/* Footer */}
      <div className="px-3 py-1.5 border-t border-white/5 flex items-center justify-end">
        <span className="text-[9px] font-mono text-slate-600 uppercase tracking-widest">Powered by GIPHY</span>
      </div>
    </div>
  );
}
