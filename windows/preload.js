const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('api', {
  getState: () => ipcRenderer.invoke('get-state'),
  switchTo: (n) => ipcRenderer.invoke('switch', n),
  add: (n) => ipcRenderer.invoke('add', n),
  saveCurrent: (n) => ipcRenderer.invoke('save-current', n),
  rename: (a, b) => ipcRenderer.invoke('rename', a, b),
  remove: (n) => ipcRenderer.invoke('delete', n),
  move: (n, d) => ipcRenderer.invoke('move', n, d),
  setOpenAtLogin: (v) => ipcRenderer.invoke('open-at-login', v),
  openFolder: () => ipcRenderer.invoke('open-folder'),
  onState: (cb) => ipcRenderer.on('state', (_e, s) => cb(s)),
  onMode: (cb) => ipcRenderer.on('mode', (_e, m) => cb(m)),
});
