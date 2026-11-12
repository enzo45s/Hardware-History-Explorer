import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { runInNewContext } from 'node:vm';

const script = readFileSync(new URL('../public/theme.js', import.meta.url), 'utf8');
function browser({ saved = null, dark = false, blockedRead = false, blockedWrite = false } = {}) {
  const storage = new Map(saved == null ? [] : [['hardware-history-theme', saved]]);
  const events = new Map();
  const root = { dataset: {}, style: {} };
  const meta = { setAttribute(name, value) { this[name] = value; } };
  const media = { matches: dark, addEventListener(event, listener) { this.listener = listener; } };
  const localStorage = { getItem(key) { if (blockedRead) throw Error('blocked'); return storage.get(key) ?? null; }, setItem(key, value) { if (blockedWrite) throw Error('blocked'); storage.set(key, value); } };
  const window = { localStorage, matchMedia: () => media, addEventListener(type, handler) { events.set(type, handler); } };
  runInNewContext(script, { window, document: { documentElement: root, querySelector: () => meta } });
  return { theme: window.HardwareHistoryTheme, root, meta, storage, localStorage,
    changeSystem(dark) { media.matches = dark; media.listener(); },
    storageEvent(newValue, key = 'hardware-history-theme', area = localStorage) { events.get('storage')({ key, newValue, storageArea: area }); } };
}

test('system is the default and responds to live operating-system changes', () => {
  const b = browser({ dark: true });
  assert.equal(b.theme.getSnapshot().preference, 'system');
  assert.equal(b.root.dataset.theme, 'dark');
  assert.equal(b.root.style.backgroundColor, 'var(--theme-page-bg, #07100b)');
  assert.equal(b.root.style.colorScheme, 'dark');
  b.changeSystem(false);
  assert.equal(b.root.dataset.theme, 'light');
  assert.equal(b.meta.content, '#f7f8fc');
});

test('explicit choices override the OS, persist and restore before React starts', () => {
  const b = browser({ saved: 'light', dark: true });
  assert.equal(b.root.dataset.theme, 'light');
  b.changeSystem(false); b.changeSystem(true);
  assert.equal(b.root.dataset.theme, 'light');
  b.theme.setPreference('dark');
  assert.equal(b.storage.get('hardware-history-theme'), 'dark');
  b.changeSystem(false);
  assert.equal(b.root.dataset.theme, 'dark');
  const restored = browser({ saved: b.storage.get('hardware-history-theme'), dark: false });
  assert.equal(restored.root.dataset.theme, 'dark');
  b.theme.setPreference('system');
  assert.equal(b.root.dataset.theme, 'light');
});

test('invalid preferences and inaccessible storage keep a working system fallback', () => {
  assert.equal(browser({ saved: 'other', dark: true }).root.dataset.theme, 'dark');
  const b = browser({ blockedRead: true, blockedWrite: true });
  b.theme.setPreference('dark');
  assert.equal(b.root.dataset.theme, 'dark');
  b.theme.setPreference('invalid');
  assert.equal(b.theme.getSnapshot().preference, 'system');
});

test('same-origin tabs synchronize settings and clearing storage restores system mode', () => {
  const b = browser({ dark: false });
  b.storageEvent('dark');
  assert.equal(b.root.dataset.theme, 'dark');
  b.storageEvent('light', 'unrelated-key');
  assert.equal(b.root.dataset.theme, 'dark');
  b.storageEvent('light', 'hardware-history-theme', {});
  assert.equal(b.root.dataset.theme, 'dark');
  b.storageEvent(null, null);
  assert.equal(b.theme.getSnapshot().preference, 'system');
  assert.equal(b.root.dataset.theme, 'light');
});

test('React snapshots remain stable and subscriptions clean up', () => {
  const b = browser();
  const initial = b.theme.getSnapshot();
  let calls = 0;
  const unsubscribe = b.theme.subscribe(() => calls++);
  b.changeSystem(false);
  assert.equal(b.theme.getSnapshot(), initial);
  assert.equal(calls, 0);
  b.theme.setPreference('light');
  assert.equal(calls, 1);
  assert.notEqual(b.theme.getSnapshot(), initial);
  unsubscribe(); b.theme.setPreference('dark');
  assert.equal(calls, 1);
});
