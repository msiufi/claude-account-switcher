// Lógica de cambio de cuenta (sin dependencias de Electron, para poder probarla aparte).
const fs = require('fs');
const path = require('path');
const os = require('os');
const { execFile, spawn } = require('child_process');

const SHARED_FILES = ['claude_desktop_config.json']; // MCP / extensiones: comunes a todas las cuentas
const NAME_RE = /^[\w .@+\-áéíóúñÁÉÍÓÚÑ]{1,60}$/;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function appData() {
  return process.env.APPDATA || path.join(os.homedir(), 'AppData', 'Roaming');
}
function localAppData() {
  return process.env.LOCALAPPDATA || path.join(os.homedir(), 'AppData', 'Local');
}

function switcherHome() {
  const base = path.join(appData(), 'Claude-Switcher');
  fs.mkdirSync(path.join(base, 'profiles'), { recursive: true });
  return base;
}
const stateFile = () => path.join(switcherHome(), 'state.json');
const profilesDir = () => path.join(switcherHome(), 'profiles');

function loadState() {
  try {
    return { active: null, dataDir: null, launchCmd: null, order: [], ...JSON.parse(fs.readFileSync(stateFile(), 'utf8')) };
  } catch {
    return { active: null, dataDir: null, launchCmd: null, order: [] };
  }
}
function saveState(s) {
  fs.writeFileSync(stateFile(), JSON.stringify(s, null, 2), 'utf8');
}

function claudeDataDir(state) {
  if (state.dataDir) return state.dataDir;
  const cands = [path.join(appData(), 'Claude')];
  const pkgs = path.join(localAppData(), 'Packages');
  try {
    for (const d of fs.readdirSync(pkgs)) {
      if (d.startsWith('Claude_')) cands.push(path.join(pkgs, d, 'LocalCache', 'Roaming', 'Claude'));
    }
  } catch {}
  return cands.find((c) => fs.existsSync(c)) || cands[0];
}

// ---------- Proceso de Claude (Windows) ----------
const NOWIN = { windowsHide: true };
function run(cmd, args) {
  return new Promise((res) => execFile(cmd, args, NOWIN, (err, stdout) => res({ err, stdout: stdout || '' })));
}

const proc = {
  async running() {
    const { stdout } = await run('tasklist', ['/FI', 'IMAGENAME eq claude.exe', '/NH']);
    return stdout.toLowerCase().includes('claude.exe');
  },
  async quit(timeoutMs = 15000) {
    if (!(await proc.running())) return true;
    await run('taskkill', ['/IM', 'claude.exe', '/T']);
    const end = Date.now() + timeoutMs;
    while (Date.now() < end) {
      if (!(await proc.running())) { await sleep(1200); return true; }
      await sleep(500);
    }
    await run('taskkill', ['/F', '/IM', 'claude.exe', '/T']);
    await sleep(1500);
    return !(await proc.running());
  },
  async launch(state) {
    if (state.launchCmd) {
      spawn(state.launchCmd, { shell: true, detached: true, stdio: 'ignore', windowsHide: true }).unref();
      return;
    }
    const exe = path.join(localAppData(), 'AnthropicClaude', 'claude.exe');
    if (fs.existsSync(exe)) {
      spawn(exe, [], { detached: true, stdio: 'ignore' }).unref();
      return;
    }
    // Instalación MSIX / Microsoft Store
    const ps = "$a=(Get-StartApps | Where-Object {$_.Name -eq 'Claude'} | Select-Object -First 1).AppID; if($a){Start-Process \"shell:AppsFolder\\$a\"}";
    spawn('powershell', ['-NoProfile', '-Command', ps], { detached: true, stdio: 'ignore', windowsHide: true }).unref();
  },
};

// ---------- Archivos ----------
async function moveDir(src, dst) {
  // Reintenta: Windows/antivirus a veces retienen archivos unos segundos tras cerrar la app.
  let lastErr;
  for (let i = 0; i < 12; i++) {
    try {
      fs.renameSync(src, dst);
      return;
    } catch (e) {
      lastErr = e;
      if (e.code === 'EXDEV') {
        fs.cpSync(src, dst, { recursive: true });
        fs.rmSync(src, { recursive: true, force: true });
        return;
      }
      if (!['EPERM', 'EBUSY', 'EACCES', 'ENOTEMPTY'].includes(e.code)) throw e;
      await sleep(500);
    }
  }
  throw new Error(`Windows no soltó la carpeta de Claude (${lastErr.code}). Cierra Claude por completo y reintenta.`);
}

function validName(n) {
  n = String(n || '').trim();
  if (!NAME_RE.test(n) || n === '.' || n === '..') throw new Error('Nombre inválido. Usa letras, números, espacios, . @ + - _');
  return n;
}

function listProfiles(state) {
  const names = new Set();
  try {
    for (const d of fs.readdirSync(profilesDir(), { withFileTypes: true })) if (d.isDirectory()) names.add(d.name);
  } catch {}
  if (state.active) names.add(state.active);
  const ordered = (state.order || []).filter((n) => names.has(n));
  const rest = [...names].filter((n) => !ordered.includes(n)).sort();
  return [...ordered, ...rest];
}

function addToOrder(state, n) {
  state.order = state.order || [];
  if (!state.order.includes(n)) state.order.push(n);
}

function saveCurrentAs(name) {
  const state = loadState();
  name = validName(name);
  if (state.active && state.active !== name) throw new Error(`La sesión actual ya está guardada como "${state.active}".`);
  if (fs.existsSync(path.join(profilesDir(), name))) throw new Error(`Ya existe una cuenta "${name}".`);
  state.active = name;
  addToOrder(state, name);
  saveState(state);
}

async function switchTo(name, { fresh = false } = {}) {
  const state = loadState();
  name = validName(name);
  const dataDir = claudeDataDir(state);
  const target = path.join(profilesDir(), name);

  if (!fresh && name === state.active) {
    if (!(await proc.running())) await proc.launch(state);
    return;
  }
  if (fresh && (fs.existsSync(target) || name === state.active)) throw new Error(`Ya existe una cuenta "${name}".`);
  if (!fresh && !fs.existsSync(target)) throw new Error(`No existe la cuenta "${name}".`);

  if (!(await proc.quit())) throw new Error('Claude no se cerró. Ciérralo desde la bandeja y reintenta.');

  // Guardar archivos compartidos
  const shared = {};
  for (const f of SHARED_FILES) {
    const p = path.join(dataDir, f);
    if (fs.existsSync(p)) shared[f] = fs.readFileSync(p);
  }

  // Guardar la sesión actual
  if (fs.existsSync(dataDir)) {
    if (!state.active) {
      state.active = 'sin-nombre-' + new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-');
      addToOrder(state, state.active);
    }
    const stash = path.join(profilesDir(), state.active);
    if (fs.existsSync(stash)) fs.rmSync(stash, { recursive: true, force: true });
    await moveDir(dataDir, stash);
    saveState(state); // a partir de aquí la sesión anterior está a salvo
  }

  // Poner la nueva
  try {
    if (fresh) fs.mkdirSync(dataDir, { recursive: true });
    else await moveDir(target, dataDir);
  } catch (e) {
    // Revertir: devolver la sesión anterior a su sitio
    const back = path.join(profilesDir(), state.active);
    if (!fs.existsSync(dataDir) && fs.existsSync(back)) await moveDir(back, dataDir).catch(() => {});
    throw e;
  }
  for (const [f, buf] of Object.entries(shared)) fs.writeFileSync(path.join(dataDir, f), buf);

  state.active = name;
  addToOrder(state, name);
  saveState(state);
  await proc.launch(state);
}

function renameProfile(oldName, newName) {
  const state = loadState();
  oldName = validName(oldName);
  newName = validName(newName);
  if (oldName === newName) return;
  if (listProfiles(state).includes(newName)) throw new Error(`Ya existe "${newName}".`);
  if (state.active === oldName) state.active = newName;
  else if (fs.existsSync(path.join(profilesDir(), oldName))) fs.renameSync(path.join(profilesDir(), oldName), path.join(profilesDir(), newName));
  else throw new Error(`No existe "${oldName}".`);
  state.order = (state.order || []).map((n) => (n === oldName ? newName : n));
  saveState(state);
}

function deleteProfile(name) {
  const state = loadState();
  name = validName(name);
  if (state.active === name) throw new Error('No puedes eliminar la cuenta activa. Cambia a otra primero.');
  fs.rmSync(path.join(profilesDir(), name), { recursive: true, force: true });
  state.order = (state.order || []).filter((n) => n !== name);
  saveState(state);
}

function moveProfile(name, delta) {
  const state = loadState();
  const list = listProfiles(state);
  const i = list.indexOf(name);
  const j = i + delta;
  if (i < 0 || j < 0 || j >= list.length) return;
  [list[i], list[j]] = [list[j], list[i]];
  state.order = list;
  saveState(state);
}

module.exports = {
  proc, loadState, saveState, listProfiles, saveCurrentAs, switchTo,
  renameProfile, deleteProfile, moveProfile, claudeDataDir, switcherHome,
};
