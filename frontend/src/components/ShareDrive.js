import { useState, useEffect, useCallback } from 'react';
import api from '../lib/api';
import { Upload, FileText, Trash2, Download, HardDrive } from 'lucide-react';
import { Button } from '../components/ui/button';
import { ScrollArea } from '../components/ui/scroll-area';
import { Progress } from '../components/ui/progress';

export default function ShareDrive({ server }) {
  const [files, setFiles] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [loading, setLoading] = useState(false);

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
      await api.post(`/servers/${server.id}/drive/upload`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
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

  const formatSize = (bytes) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
  };

  const usedBytes = server?.storage_used_bytes || 0;
  const limitBytes = server?.storage_limit_bytes || 25 * 1024 * 1024 * 1024;
  const usagePercent = (usedBytes / limitBytes) * 100;

  return (
    <div className="flex-1 flex flex-col bg-[#020617]" data-testid="share-drive">
      <div className="h-12 px-6 flex items-center border-b border-white/5 flex-shrink-0">
        <HardDrive className="w-4 h-4 text-emerald-500 mr-2" />
        <span className="text-sm font-medium text-slate-100 font-['Outfit']">Share Drive — {server?.name}</span>
      </div>

      <div className="p-6">
        {/* Storage usage */}
        <div className="mb-6 p-4 bg-slate-900/50 rounded-lg border border-white/5">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-mono uppercase tracking-widest text-slate-500">Storage Usage</span>
            <span className="text-xs font-mono text-slate-400">{formatSize(usedBytes)} / {formatSize(limitBytes)}</span>
          </div>
          <Progress value={usagePercent} className="h-2 bg-slate-800" />
        </div>

        {/* Upload */}
        <div className="mb-6">
          <label className="cursor-pointer">
            <input type="file" onChange={handleUpload} className="hidden" data-testid="drive-file-input" />
            <Button asChild disabled={uploading} className="bg-emerald-500 text-slate-950 hover:bg-emerald-400">
              <span>
                <Upload className="w-4 h-4 mr-2" />
                {uploading ? 'Uploading...' : 'Upload File'}
              </span>
            </Button>
          </label>
        </div>

        {/* Files list */}
        <ScrollArea className="max-h-[60vh]">
          <div className="space-y-1">
            {loading && <p className="text-slate-500 text-sm text-center py-8">Loading files...</p>}
            {!loading && files.length === 0 && (
              <p className="text-slate-500 text-sm text-center py-8">No files in the share drive yet</p>
            )}
            {files.map(f => (
              <div key={f.id} className="flex items-center gap-3 px-4 py-3 bg-slate-900/30 rounded border border-white/5 hover:border-white/10 transition-colors" data-testid={`drive-file-${f.id}`}>
                <FileText className="w-5 h-5 text-slate-500 flex-shrink-0" />
                <div className="min-w-0 flex-1">
                  <p className="text-sm text-slate-200 truncate">{f.original_filename}</p>
                  <div className="flex items-center gap-3 mt-0.5">
                    <span className="text-xs font-mono text-slate-500">{formatSize(f.size)}</span>
                    <span className="text-xs text-slate-600">by {f.uploader_username}</span>
                    <span className="text-xs font-mono text-slate-600">{new Date(f.created_at).toLocaleDateString()}</span>
                  </div>
                </div>
                <div className="flex gap-1">
                  <button onClick={() => handleDownload(f.id, f.original_filename)} className="p-2 text-slate-400 hover:text-emerald-400 rounded" data-testid={`download-file-${f.id}`}>
                    <Download className="w-4 h-4" />
                  </button>
                  <button onClick={() => handleDelete(f.id)} className="p-2 text-slate-400 hover:text-red-400 rounded" data-testid={`delete-file-${f.id}`}>
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
