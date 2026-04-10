const { contextBridge, ipcRenderer } = require('electron');

// Expose safe APIs to the renderer process
contextBridge.exposeInMainWorld('shieldDesktop', {
  platform: process.platform,
  isDesktop: true,
  // Notification bridge
  showNotification: (title, body) => {
    ipcRenderer.send('show-notification', { title, body });
  },
  // App info
  getVersion: () => ipcRenderer.invoke('get-version'),
});
