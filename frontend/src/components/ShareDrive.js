import { useState, useEffect, useCallback } from 'react';
import api from '../lib/api';
import { Upload, FileText, Trash2, Download, HardDrive, Plus, Link, Edit3, Save, X, File as FileIcon } from 'lucide-react';
import { Button } from '../components/ui/button';
import { ScrollArea } from '../components/ui/scroll-area';
import { Progress } from '../components/ui/progress';
import { Input } from '../components/ui/input';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '../components/ui/dialog';
import { Label } from '../components/ui/label';

export default function ShareDrive({ server }) {
  const [files, setFiles] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [loading, setLoading] = useState(false);
  const [editingFile, setEditingFile] = useState(null);
  const [editContent, setEditContent] = useState('');
  const [showNewText, setShowNewText] = useState(false);
  const [newFileName, setNewFileName] = useState('');
  const [newFileContent, setNewFileContent] = useState('');
  const [copiedLink, setCopiedLink] = useState(null);
  const [saving, setSaving] = useState(false);

  const loadFiles = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await api.get(`/servers/${server.id}/drive`);
      setFiles(data);
    } catch {}
    setLoading(false);
  }, [server.id]);

  useEffect(() => { loadFiles(); }, [loadFiles]);

  const handleUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      await api.post(`/servers/${server.id}/drive/upload`, formData, { headers: { 'Content-Type': 'multipart/form-data' } });
      loadFiles();
    } catch {}
    setUploading(false);
  };

  const handleDelete = async (fileId) => {
    try {
      await api.delete(`/servers/${server.id}/drive/${fileId}`);
      loadFiles();
    } catch {}
  };

  const handleDownload = async (fileId, filename) => {
    try {
      const { data } = await api.get(`/files/${fileId}/download`, { responseType: 'blob' });
      const url = URL.createObjectURL(data);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
    } catch {}
  };

  const handleCopyLink = async (fileId) => {
    try {
      const { data } = await api.get(`/servers/${server.id}/drive/${fileId}/link`);
      const fullLink = `${process.env.REACT_APP_BACKEND_URL || window.location.origin}${data.link}`;
      await navigator.clipboard.writeText(fullLink);
      setCopiedLink(fileId);
      setTimeout(() => setCopiedLink(null), 2000);
    } catch {}
  };

  const handleCreateText = async () => {
    if (!newFileName.trim()) return;
    setSaving(true);
    try {
      await api.post(`/servers/${server.id}/drive/text`, { filename: newFileName, content: newFileContent });
      setShowNewText(false);
      setNewFileName('');
      setNewFileContent('');
      loadFiles();
    } catch {}
    setSaving(false);
  };

  const handleOpenEdit = async (file) => {
    try {
      const { data } = await api.get(`/servers/${server.id}/drive/${file.id}/content`);
      setEditingFile(file);
      setEditContent(data.content);
    } catch {}
  };

  const handleSaveEdit = async () => {
    if (!editingFile) return;
    setSaving(true);
    try {
      await api.put(`/servers/${server.id}/drive/${editingFile.id}/content`, { content: editContent });
      setEditingFile(null);
      loadFiles();
    } catch {}
    setSaving(false);
  };

  const formatSize = (bytes) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
  };

  const usedBytes = server?.storage_used_bytes || 0;
  const limitBytes = server?.storage_limit_bytes || 25 * 1024 * 1024 * 1024;
  const usagePercent = Math.min((usedBytes / limitBytes) * 100, 100);

  // Text file editor view
  if (editingFile) {
    return (
      <div className="flex-1 flex flex-col bg-[#020617]" data-testid="text-file-editor">
        <div className="h-12 px-6 flex items-center justify-between border-b border-white/5 flex-shrink-0">
          <div className="flex items-center gap-2">
            <FileText className="w-4 h-4 text-emerald-500" />
            <span className="text-sm font-medium text-slate-100 font-['Outfit']">{editingFile.original_filename}</span>
          </div>
          <div className="flex items-center gap-2">
            <Button size="sm" onClick={handleSaveEdit} disabled={saving} className="bg-emerald-500 text-slate-950 hover:bg-emerald-400 h-8" data-testid="save-text-file-btn">
              <Save className="w-3.5 h-3.5 mr-1" /> {saving ? 'Saving...' : 'Save'}
            </Button>
            <button onClick={() => setEditingFile(null)} className="p-2 text-slate-400 hover:text-slate-200" data-testid="close-editor-btn">
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>
        <div className="flex-1 p-4">
          <textarea
            value={editContent}
            onChange={e => setEditContent(e.target.value)}
            className="w-full h-full bg-slate-950/50 border border-white/10 rounded-lg p-4 text-sm text-slate-100 font-mono resize-none focus:outline-none focus:ring-1 focus:ring-emerald-500/50"
            data-testid="text-file-textarea"
          />
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col bg-[#020617]" data-testid="share-drive">
      <div className="h-12 px-6 flex items-center border-b border-white/5 flex-shrink-0">
        <HardDrive className="w-4 h-4 text-emerald-500 mr-2" />
        <span className="text-sm font-medium text-slate-100 font-['Outfit']">Share Drive — {server?.name}</span>
      </div>

      <div className="p-6 flex-1 overflow-y-auto">
        {/* Storage usage */}
        <div className="mb-6 p-4 bg-slate-900/50 rounded-lg border border-white/5">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-mono uppercase tracking-widest text-slate-500">Storage Usage</span>
            <span className="text-xs font-mono text-slate-400">{formatSize(usedBytes)} / {formatSize(limitBytes)}</span>
          </div>
          <Progress value={usagePercent} className="h-2 bg-slate-800" />
        </div>

        {/* Actions */}
        <div className="flex items-center gap-3 mb-6">
          <label className="cursor-pointer">
            <input type="file" onChange={handleUpload} className="hidden" data-testid="drive-file-input" />
            <Button asChild disabled={uploading} className="bg-emerald-500 text-slate-950 hover:bg-emerald-400">
              <span><Upload className="w-4 h-4 mr-2" />{uploading ? 'Uploading...' : 'Upload File'}</span>
            </Button>
          </label>

          <Dialog open={showNewText} onOpenChange={setShowNewText}>
            <DialogTrigger asChild>
              <Button variant="outline" className="border-slate-700 text-slate-300 hover:bg-slate-800" data-testid="new-text-file-btn">
                <Plus className="w-4 h-4 mr-2" /> New Text File
              </Button>
            </DialogTrigger>
            <DialogContent className="bg-slate-900 border-white/10 text-slate-100 max-w-lg">
              <DialogHeader><DialogTitle className="font-['Outfit']">Create Text File</DialogTitle></DialogHeader>
              <div className="space-y-4 pt-2">
                <div>
                  <Label className="text-slate-300 text-sm">Filename</Label>
                  <Input value={newFileName} onChange={e => setNewFileName(e.target.value)} placeholder="notes.txt" className="bg-slate-950/50 border-white/10 text-slate-100 mt-1.5" data-testid="new-text-filename" />
                </div>
                <div>
                  <Label className="text-slate-300 text-sm">Content</Label>
                  <textarea value={newFileContent} onChange={e => setNewFileContent(e.target.value)} placeholder="Type content here..." className="w-full h-40 bg-slate-950/50 border border-white/10 rounded-md p-3 text-sm text-slate-100 font-mono resize-none mt-1.5 focus:outline-none focus:ring-1 focus:ring-emerald-500/50" data-testid="new-text-content" />
                </div>
                <Button onClick={handleCreateText} disabled={saving} className="w-full bg-emerald-500 text-slate-950 hover:bg-emerald-400" data-testid="create-text-file-btn">
                  {saving ? 'Creating...' : 'Create File'}
                </Button>
              </div>
            </DialogContent>
          </Dialog>
        </div>

        {/* Files list */}
        <ScrollArea className="max-h-[55vh]">
          <div className="space-y-1">
            {loading && <p className="text-slate-500 text-sm text-center py-8">Loading files...</p>}
            {!loading && files.length === 0 && (
              <p className="text-slate-500 text-sm text-center py-8 font-['IBM_Plex_Sans']">No files in the share drive yet. Upload a file or create a text file to get started.</p>
            )}
            {files.map(f => (
              <div key={f.id} className="flex items-center gap-3 px-4 py-3 bg-slate-900/30 rounded border border-white/5 hover:border-white/10 transition-colors group" data-testid={`drive-file-${f.id}`}>
                {f.is_text_file ? <FileText className="w-5 h-5 text-emerald-500 flex-shrink-0" /> : <FileIcon className="w-5 h-5 text-slate-500 flex-shrink-0" />}
                <div className="min-w-0 flex-1">
                  <p className="text-sm text-slate-200 truncate">{f.original_filename}</p>
                  <div className="flex items-center gap-3 mt-0.5">
                    <span className="text-xs font-mono text-slate-500">{formatSize(f.size)}</span>
                    <span className="text-xs text-slate-600">by {f.uploader_username}</span>
                    <span className="text-xs font-mono text-slate-600">{new Date(f.created_at).toLocaleDateString()}</span>
                  </div>
                </div>
                <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                  {f.is_text_file && (
                    <button onClick={() => handleOpenEdit(f)} className="p-2 text-slate-400 hover:text-emerald-400 rounded" title="Edit" data-testid={`edit-file-${f.id}`}>
                      <Edit3 className="w-4 h-4" />
                    </button>
                  )}
                  <button onClick={() => handleCopyLink(f.id)} className={`p-2 rounded transition-colors ${copiedLink === f.id ? 'text-emerald-400' : 'text-slate-400 hover:text-emerald-400'}`} title="Copy link" data-testid={`link-file-${f.id}`}>
                    <Link className="w-4 h-4" />
                  </button>
                  {!f.is_text_file && (
                    <button onClick={() => handleDownload(f.id, f.original_filename)} className="p-2 text-slate-400 hover:text-emerald-400 rounded" title="Download" data-testid={`download-file-${f.id}`}>
                      <Download className="w-4 h-4" />
                    </button>
                  )}
                  <button onClick={() => handleDelete(f.id)} className="p-2 text-slate-400 hover:text-red-400 rounded" title="Delete" data-testid={`delete-file-${f.id}`}>
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </ScrollArea>
      </div>
    </div>
  );
}
