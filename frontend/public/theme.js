/* Loaded synchronously in <head>: apply the saved/system theme before first paint. */
(() => {
  if (window.HardwareHistoryTheme) return;
  const key = 'hardware-history-theme';
  const normalize = value => ['system', 'light', 'dark'].includes(value) ? value : 'system';
  let storage;
  let preference = 'system';
  try { storage = window.localStorage; preference = normalize(storage.getItem(key)); } catch { /* Storage can be unavailable in private/restricted browsers. */ }
  const media = window.matchMedia ? window.matchMedia('(prefers-color-scheme: dark)') : { matches: false };
  const listeners = new Set();
  let snapshot;
  function apply() {
    const resolved = preference === 'system' ? (media.matches ? 'dark' : 'light') : preference;
    if (snapshot?.preference === preference && snapshot.resolved === resolved) return;
    const root = document.documentElement;
    root.dataset.theme = resolved;
    root.dataset.themePreference = preference;
    root.style.colorScheme = resolved;
    const background = resolved === 'dark' ? '#07100b' : '#f7f8fc';
    const foreground = resolved === 'dark' ? '#b4e4bf' : '#202b42';
    root.style.backgroundColor = `var(--theme-page-bg, ${background})`;
    root.style.color = `var(--theme-text-primary, ${foreground})`;
    document.querySelector('meta[name="theme-color"]')?.setAttribute('content', background);
    snapshot = Object.freeze({ preference, resolved });
    listeners.forEach(listener => listener());
  }
  apply();
  if (media.addEventListener) media.addEventListener('change', apply);
  else if (media.addListener) media.addListener(apply);
  window.addEventListener('storage', event => {
    if (event.key !== key && event.key !== null) return;
    if (event.storageArea && storage && event.storageArea !== storage) return;
    preference = event.key === null ? 'system' : normalize(event.newValue);
    apply();
  });
  window.HardwareHistoryTheme = Object.freeze({
    getSnapshot: () => snapshot,
    subscribe(listener) { listeners.add(listener); return () => listeners.delete(listener); },
    setPreference(value) {
      preference = normalize(value);
      try { storage?.setItem(key, preference); } catch { /* Keep the choice for this page even if it cannot be persisted. */ }
      apply();
    }
  });
})();
