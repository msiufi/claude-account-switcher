// Tests for the profile-switching logic. They run on any OS: Claude's process
// control is stubbed and %APPDATA% points at a temporary folder.
const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const os = require('os');
const path = require('path');

const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'claude-switcher-'));
process.env.APPDATA = path.join(tmp, 'Roaming');
process.env.LOCALAPPDATA = path.join(tmp, 'Local');

const core = require('../core');
core.proc.running = async () => false;
core.proc.quit = async () => true;
core.proc.launch = async () => {};

const dataDir = path.join(process.env.APPDATA, 'Claude');
const cookie = () => fs.readFileSync(path.join(dataDir, 'Cookies'), 'utf8');

test.before(() => {
  fs.mkdirSync(dataDir, { recursive: true });
  fs.writeFileSync(path.join(dataDir, 'Cookies'), 'session-A');
  fs.writeFileSync(path.join(dataDir, 'claude_desktop_config.json'), '{"mcpServers":{}}');
});
test.after(() => fs.rmSync(tmp, { recursive: true, force: true }));

test('save current, add a fresh account, and round-trip between them', async () => {
  core.saveCurrentAs('personal');
  await core.switchTo('work', { fresh: true });

  assert.ok(!fs.existsSync(path.join(dataDir, 'Cookies')), 'new account starts signed out');
  assert.strictEqual(
    fs.readFileSync(path.join(dataDir, 'claude_desktop_config.json'), 'utf8'),
    '{"mcpServers":{}}',
    'MCP config is shared across accounts',
  );

  fs.writeFileSync(path.join(dataDir, 'Cookies'), 'session-B');
  await core.switchTo('personal');
  assert.strictEqual(cookie(), 'session-A');
  await core.switchTo('work');
  assert.strictEqual(cookie(), 'session-B');
});

test('refuses duplicates and deleting the active account', async () => {
  await assert.rejects(core.switchTo('work', { fresh: true }), /Ya existe/);
  assert.throws(() => core.deleteProfile('work'), /activa/);
  assert.throws(() => core.saveCurrentAs('../escape'), /inválido/);
});

test('rename, reorder and delete', async () => {
  core.moveProfile('work', -1);
  assert.deepStrictEqual(core.listProfiles(core.loadState()), ['work', 'personal']);
  core.renameProfile('personal', 'home');
  await core.switchTo('home');
  assert.strictEqual(cookie(), 'session-A');
  core.deleteProfile('work');
  assert.deepStrictEqual(core.listProfiles(core.loadState()), ['home']);
});
