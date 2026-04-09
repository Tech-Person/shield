import { useState, useEffect, useCallback } from 'react';
import api from '../lib/api';
import { Upload, Trash2, X, Bookmark, BookmarkCheck } from 'lucide-react';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { ScrollArea } from '../components/ui/scroll-area';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';

export default function EmojiManager({ onSelect, onClose }) {
  const [owned, setOwned] = useState([]);
  const [saved, setSaved] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [showUpload, setShowUpload] = useState(false);
  const [emojiName, setEmojiName] = useState('');
  const [emojiType, setEmojiType] = useState('emoji');

  const loadEmojis = useCallback(async () => {
    try {
      const { data } = await api.get('/emojis/mine');
      setOwned(data.owned || []);
      setSaved(data.saved || []);
    } catch {}
  }, []);

  useEffect(() => { loadEmojis(); }, [loadEmojis]);

  const handleUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file || !emojiName.trim()) return;
    setUploading(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      await api.post(`/emojis/upload?name=${encodeURIComponent(emojiName)}&emoji_type=${emojiType}`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      setEmojiName('');
      setShowUpload(false);
      loadEmojis();
    } catch {}
    setUploading(false);
  };

  const handleSave = async (emojiId) => {
    try {
      await api.post(`/emojis/${emojiId}/save`);
      loadEmojis();
    } catch {}
  };

  const handleUnsave = async (emojiId) => {
    try {
      await api.delete(`/emojis/${emojiId}/save`);
      loadEmojis();
    } catch {}
  };

  const handleDelete = async (emojiId) => {
    try {
      await api.delete(`/emojis/${emojiId}`);
      loadEmojis();
    } catch {}
  };

  const handleSelect = (emoji) => {
    if (onSelect) onSelect(emoji);
  };

  const backendUrl = process.env.REACT_APP_BACKEND_URL;
  const emojiUrl = (id) => `${backendUrl}/api/emojis/${id}/image`;
  const savedIds = new Set(saved.map(e => e.id));

  return (
    <div className="w-72 bg-slate-900 border border-white/10 rounded-lg shadow-2xl overflow-hidden" data-testid="emoji-manager">
      <div className="flex items-center justify-between px-3 py-2 border-b border-white/5">
        <span className="text-xs font-mono uppercase tracking-widest text-slate-500">Custom Emojis</span>
        <button onClick={onClose} className="text-slate-500 hover:text-slate-300" data-testid="close-emoji-manager"><X className="w-3.5 h-3.5" /></button>
      </div>

      <Tabs defaultValue="library">
        <TabsList className="w-full bg-slate-950/50 rounded-none border-b border-white/5 h-8">
          <TabsTrigger value="library" className="text-xs data-[state=active]:bg-slate-800 data-[state=active]:text-slate-100 text-slate-500 h-7">My Library</TabsTrigger>
          <TabsTrigger value="upload" className="text-xs data-[state=active]:bg-slate-800 data-[state=active]:text-slate-100 text-slate-500 h-7">Upload</TabsTrigger>
        </TabsList>

        <TabsContent value="library" className="mt-0">
          <ScrollArea className="h-56">
            <div className="p-2">
              {owned.length === 0 && saved.length === 0 && (
                <p className="text-xs text-slate-500 text-center py-6">No custom emojis yet. Upload some!</p>
              )}
              {owned.length > 0 && (
                <div className="mb-3">
                  <p className="text-[10px] font-mono uppercase tracking-widest text-slate-600 px-1 mb-1.5">Your Emojis</p>
                  <div className="grid grid-cols-5 gap-1">
                    {owned.map(e => (
                      <div key={e.id} className="relative group" data-testid={`emoji-item-${e.id}`}>
                        <button
                          onClick={() => handleSelect(e)}
                          className="w-full aspect-square rounded bg-slate-800/50 hover:bg-slate-700 flex items-center justify-center p-1 transition-colors"
                          title={`:${e.name}:`}
                        >
                          <img src={emojiUrl(e.id)} alt={e.name} className="w-7 h-7 object-contain" loading="lazy" />
                        </button>
                        <button
                          onClick={() => handleDelete(e.id)}
                          className="absolute -top-1 -right-1 w-4 h-4 bg-red-500 rounded-full items-center justify-center hidden group-hover:flex"
                          data-testid={`delete-emoji-${e.id}`}
                        >
                          <Trash2 className="w-2.5 h-2.5 text-white" />
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              {saved.length > 0 && (
                <div>
                  <p className="text-[10px] font-mono uppercase tracking-widest text-slate-600 px-1 mb-1.5">Saved</p>
                  <div className="grid grid-cols-5 gap-1">
                    {saved.map(e => (
                      <div key={e.id} className="relative group" data-testid={`saved-emoji-${e.id}`}>
                        <button
                          onClick={() => handleSelect(e)}
                          className="w-full aspect-square rounded bg-slate-800/50 hover:bg-slate-700 flex items-center justify-center p-1 transition-colors"
                          title={`:${e.name}:`}
                        >
                          <img src={emojiUrl(e.id)} alt={e.name} className="w-7 h-7 object-contain" loading="lazy" />
                        </button>
                        <button
                          onClick={() => handleUnsave(e.id)}
                          className="absolute -top-1 -right-1 w-4 h-4 bg-slate-600 rounded-full items-center justify-center hidden group-hover:flex"
                        >
                          <X className="w-2.5 h-2.5 text-white" />
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </ScrollArea>
        </TabsContent>

        <TabsContent value="upload" className="mt-0">
          <div className="p-3 space-y-3">
            <div>
              <Label className="text-slate-400 text-xs">Name</Label>
              <Input
                value={emojiName}
                onChange={e => setEmojiName(e.target.value)}
                placeholder="my_emoji"
                className="bg-slate-950/50 border-white/10 text-slate-100 text-sm mt-1 h-8"
                data-testid="emoji-name-input"
              />
            </div>
            <div>
              <Label className="text-slate-400 text-xs">Type</Label>
              <div className="flex gap-2 mt-1">
                <button
                  onClick={() => setEmojiType('emoji')}
                  className={`px-3 py-1 rounded text-xs transition-colors ${emojiType === 'emoji' ? 'bg-emerald-500 text-slate-950' : 'bg-slate-800 text-slate-400'}`}
                  data-testid="emoji-type-emoji"
                >
                  Emoji
                </button>
                <button
                  onClick={() => setEmojiType('sticker')}
                  className={`px-3 py-1 rounded text-xs transition-colors ${emojiType === 'sticker' ? 'bg-emerald-500 text-slate-950' : 'bg-slate-800 text-slate-400'}`}
                  data-testid="emoji-type-sticker"
                >
                  Sticker
                </button>
              </div>
            </div>
            <label className="cursor-pointer">
              <input type="file" accept="image/*" onChange={handleUpload} className="hidden" data-testid="emoji-file-input" />
              <Button asChild disabled={uploading || !emojiName.trim()} className="w-full bg-emerald-500 text-slate-950 hover:bg-emerald-400 h-8 text-xs">
                <span><Upload className="w-3.5 h-3.5 mr-1.5" />{uploading ? 'Uploading...' : 'Choose Image & Upload'}</span>
              </Button>
            </label>
            <p className="text-[10px] text-slate-600">Max 512KB. Image files only.</p>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
