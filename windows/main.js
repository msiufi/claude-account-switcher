const { app, Tray, Menu, BrowserWindow, ipcMain, globalShortcut, Notification, nativeImage, shell } = require('electron');
const path = require('path');
const core = require('./core');

if (!app.requestSingleInstanceLock()) app.quit();
app.setAppUserModelId('com.lean.claudeswitcher');

let tray = null;
let win = null;
let busy = false;

const icon = (n) => nativeImage.createFromPath(path.join(__dirname, 'assets', n));

function notify(body) {
  if (Notification.isSupported()) new Notification({ title: 'Claude Switcher', body, silent: true }).show();
}

async function doSwitch(name, opts) {
  if (busy) return;
  busy = true;
  tray.setImage(icon('tray-busy.png'));
  tray.setToolTip(`Cambiando a ${name}…`);
  pushState();
  try {
    await core.switchTo(name, opts);
    notify(opts && opts.fresh ? `Claude abierto limpio. Inicia sesión con "${name}".` : `Ahora estás en "${name}".`);
  } catch (e) {
    notify(e.message);
    throw e;
  } finally {
    busy = false;
    tray.setImage(icon('tray.png'));
    refresh();
  }
}

function snapshot() {
  const s = core.loadState();
  return {
    profiles: core.listProfiles(s),
    active: s.active,
    busy,
    dataDir: core.claudeDataDir(s),
    openAtLogin: app.getLoginItemSettings().openAtLogin,
  };
}

function pushState() {
  if (win && !win.isDestroyed()) win.webContents.send('state', snapshot());
}

function refresh() {
  const { profiles, active } = snapshot();
  tray.setToolTip(active ? `Claude: ${active}` : 'Claude Switcher');

  const items = profiles.map((n, i) => ({
    label: n,
    type: 'radio',
    checked: n === active,
    accelerator: i < 9 ? `Ctrl+Alt+${i + 1}` : undefined,
    enabled: !busy,
    click: () => doSwitch(n).catch(() => {}),
  }));

  const menu = Menu.buildFromTemplate([
    { label: 'Cuentas de Claude', enabled: false },
    ...(items.length ? items : [{ label: 'Sin cuentas todavía', enabled: false }]),
    { type: 'separator' },
    { label: 'Añadir cuenta…', click: () => openWindow('add') },
    { label: 'Administrar cuentas…', click: () => openWindow() },
    { type: 'separator' },
    {
      label: 'Iniciar con Windows',
      type: 'checkbox',
      checked: app.getLoginItemSettings().openAtLogin,
      click: (m) => { app.setLoginItemSettings({ openAtLogin: m.checked }); pushState(); },
    },
    { label: 'Salir', click: () => app.quit() },
  ]);
  tray.setContextMenu(menu);

  globalShortcut.unregisterAll();
  profiles.slice(0, 9).forEach((n, i) => {
    globalShortcut.register(`Ctrl+Alt+${i + 1}`, () => doSwitch(n).catch(() => {}));
  });
  pushState();
}

function openWindow(mode) {
  if (win && !win.isDestroyed()) {
    win.show();
    win.focus();
    if (mode) win.webContents.send('mode', mode);
    return;
  }
  win = new BrowserWindow({
    width: 400,
    height: 560,
    resizable: false,
    maximizable: false,
    minimizable: false,
    title: 'Claude Switcher',
    icon: path.join(__dirname, 'assets', 'icon.png'),
    backgroundColor: '#1f1e1d',
    autoHideMenuBar: true,
    show: false,
    webPreferences: { preload: path.join(__dirname, 'preload.js'), contextIsolation: true, nodeIntegration: false },
  });
  win.loadFile('manage.html', mode ? { query: { mode } } : undefined);
  win.once('ready-to-show', () => win.show());
  win.webContents.setWindowOpenHandler(({ url }) => { shell.openExternal(url); return { action: 'deny' }; });
}

const wrap = (fn) => async (_e, ...args) => {
  try {
    await fn(...args);
    refresh();
    return { ok: true };
  } catch (e) {
    refresh();
    return { ok: false, error: e.message };
  }
};

ipcMain.handle('get-state', () => snapshot());
ipcMain.handle('switch', wrap((n) => doSwitch(n)));
ipcMain.handle('add', wrap((n) => doSwitch(n, { fresh: true })));
ipcMain.handle('save-current', wrap((n) => core.saveCurrentAs(n)));
ipcMain.handle('rename', wrap((a, b) => core.renameProfile(a, b)));
ipcMain.handle('delete', wrap((n) => core.deleteProfile(n)));
ipcMain.handle('move', wrap((n, d) => core.moveProfile(n, d)));
ipcMain.handle('open-at-login', wrap((v) => app.setLoginItemSettings({ openAtLogin: !!v })));
ipcMain.handle('open-folder', () => shell.openPath(core.switcherHome()));

app.on('second-instance', () => openWindow());
app.on('window-all-closed', (e) => e.preventDefault()); // seguir viviendo en la bandeja
app.on('will-quit', () => globalShortcut.unregisterAll());

app.whenReady().then(() => {
  tray = new Tray(icon('tray.png'));
  tray.on('click', () => tray.popUpContextMenu());
  tray.on('double-click', () => openWindow());
  refresh();
  if (!core.loadState().active) openWindow(); // primer uso
});
