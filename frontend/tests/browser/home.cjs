/* Read-only navigation checks against the real local API; no archive mutations. */
const assert = require('node:assert/strict');
const { chromium } = require('playwright');

(async () => {
  const base = process.env.HHE_BASE_URL || 'http://127.0.0.1:8080/';
  assert(['127.0.0.1', 'localhost', '[::1]'].includes(new URL(base).hostname));
  const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || undefined,
    args: ['--no-sandbox', '--disable-dev-shm-usage'] });
  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
    const errors = []; page.on('pageerror', error => errors.push(error.message));
    const response = await page.request.get(new URL('/api/home', base).href);
    assert.equal(response.status(), 200); const home = await response.json();
    // Network-independent photo rendering uses explicitly synthetic fixtures.
    for (const computer of [home.spotlight, ...home.featured].filter(Boolean)) if (computer.image_url) {
      const url = new URL(computer.image_url, base).href;
      await page.route(u => u.href === url, route => route.fulfill({ contentType: 'image/svg+xml',
        body: '<svg xmlns="http://www.w3.org/2000/svg" width="500" height="250"><rect width="500" height="250" fill="#dae5d8"/><text x="120" y="135" font-size="32">TEST PHOTO</text></svg>' }));
    }
    const nav = page.getByRole('navigation', { name: 'Navigazione principale' });
    const welcome = async () => {
      await nav.getByRole('button', { name: 'Benvenuto', exact: true }).click();
      await page.getByRole('heading', { name: 'Ogni computer, una storia.', exact: true }).waitFor();
      assert.equal(await nav.getByRole('button', { name: 'Benvenuto', exact: true }).getAttribute('aria-current'), 'page');
    };
    await page.goto(base);
    await page.getByRole('heading', { name: 'Ogni computer, una storia.', exact: true }).waitFor();
    await page.waitForFunction(total => document.querySelector('.home-stat strong')?.textContent === total,
      home.summary.systems.toLocaleString('it-IT'));
    assert.equal(await page.locator('.home-stat strong').nth(1).innerText(), home.summary.manufacturers.toLocaleString('it-IT'));
    assert.equal(await page.locator('.home-exhibit').count(), home.featured.length);
    assert.deepEqual(await page.locator('.home-exhibit h3').allInnerTexts(), home.featured.map(c => c.model_name));
    if (home.spotlight) assert(!home.featured.some(c => c.id === home.spotlight.id));
    for (const [selector, heading] of [
      [() => page.getByRole('button', { name: 'Entra nel catalogo', exact: true }), 'Catalogo sistemi'],
      [() => page.getByRole('button', { name: 'Percorri la timeline', exact: true }), 'La storia dei calcolatori.'],
      [() => page.locator('.home-path').filter({ hasText: 'Attraversa le epoche' }), 'La storia dei calcolatori.'],
      [() => page.locator('.home-path').filter({ hasText: 'Scopri le macchine' }), 'Catalogo sistemi'],
      [() => page.locator('.home-path').filter({ hasText: 'Conosci i protagonisti' }), 'Produttori'],
      [() => page.getByRole('button', { name: 'Il catalogo completo', exact: true }), 'Catalogo sistemi'],
      [() => page.getByRole('button', { name: 'Tutti i produttori', exact: true }), 'Produttori'],
      [() => page.getByRole('button', { name: 'Confronta i sistemi', exact: true }), 'Confronta i sistemi'],
      [() => page.getByRole('button', { name: 'Interroga l’archivio', exact: true }), 'Assistente storico AI.']
    ]) {
      await welcome(); await selector().click();
      await page.getByRole('heading', { name: heading, exact: true, level: 1 }).waitFor();
    }
    // Existing sidebar destinations remain reachable independently of home.
    for (const [button, heading] of [
      ['Timeline', 'La storia dei calcolatori.'], ['Catalogo', 'Catalogo sistemi'],
      ['Esplora produttori', 'Produttori'], ['Analisi', 'Analisi dell’archivio'],
      ['Confronta', 'Confronta i sistemi'], ['Assistente AI', 'Assistente storico AI.']
    ]) {
      await nav.getByRole('button', { name: button, exact: true }).click();
      // Analysis uses a straight apostrophe in its existing title.
      await page.getByRole('heading', { name: heading.replace('dell’', "dell'"), exact: true, level: 1 }).waitFor();
    }
    await welcome();
    if (home.spotlight) {
      const model = home.spotlight;
      await page.getByRole('button', { name: 'Scopri ' + model.model_name, exact: true }).click();
      await page.getByRole('heading', { name: model.model_name, exact: true, level: 1 }).waitFor();
      await page.getByRole('button', { name: "Torna all'esplorazione", exact: true }).click();
      if (home.featured.length) {
        const card = home.featured[0];
        await page.getByRole('button', { name: 'Scopri la storia di ' + card.model_name, exact: true }).click();
        await page.getByRole('heading', { name: card.model_name, exact: true, level: 1 }).waitFor();
      }
      await welcome();
      // A late detail response must not pull the user out of another section.
      let release, started;
      const held = new Promise(resolve => { release = resolve; });
      const requested = new Promise(resolve => { started = resolve; });
      const detailUrl = new URL('/api/computers/' + model.id, base).href;
      const holdDetail = async route => { started(); await held; await route.continue(); };
      await page.route(detailUrl, holdDetail);
      await page.getByRole('button', { name: 'Scopri ' + model.model_name, exact: true }).click();
      await requested;
      await nav.getByRole('button', { name: 'Catalogo', exact: true }).click();
      const received = page.waitForResponse(detailUrl); release(); await received;
      await page.waitForTimeout(100);
      assert(await page.getByRole('heading', { name: 'Catalogo sistemi', exact: true, level: 1 }).isVisible());
      await page.unroute(detailUrl, holdDetail);
      await welcome();
      await page.getByRole('button', { name: 'Entra nel catalogo', exact: true }).click();
      await page.getByPlaceholder('Cerca un sistema…', { exact: true }).fill(model.model_name);
      const card = page.locator('.catalog-card').filter({ has: page.getByRole('heading', { name: model.model_name, exact: true }) }).first();
      await card.getByRole('button', { name: '+ Confronta', exact: true }).click();
      await welcome(); await page.getByRole('button', { name: 'Confronta i sistemi', exact: true }).click();
      await page.locator('.comparison-picker').waitFor();
      assert.match(await page.locator('main').innerText(), new RegExp(model.model_name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')));
      await welcome(); await page.getByRole('button', { name: 'Entra nel catalogo', exact: true }).click();
      assert.equal(await page.getByPlaceholder('Cerca un sistema…', { exact: true }).inputValue(), model.model_name);
    }
    await welcome();
    const makers = page.locator('.home-maker-names button:not(.home-link)');
    if (await makers.count()) {
      const name = await makers.first().innerText(); await makers.first().click();
      await page.getByRole('heading', { name, exact: true, level: 1 }).waitFor();
      await welcome();
    }
    await page.getByRole('button', { name: 'Esplora il periodo 1980–1989', exact: true }).click();
    await page.getByRole('heading', { name: 'La storia dei calcolatori.', exact: true, level: 1 }).waitFor();
    assert.equal(await page.getByPlaceholder('Da anno', { exact: true }).inputValue(), '1980');
    assert.equal(await page.getByPlaceholder('A anno', { exact: true }).inputValue(), '1989');
    assert.equal(await page.getByPlaceholder('Cerca un sistema…', { exact: true }).inputValue(), '');
    // Unsaved administrative changes retain the original cancel/confirm guard.
    await nav.getByRole('button', { name: 'Amministrazione', exact: true }).click();
    await page.getByRole('button', { name: 'Produttori', exact: true }).click();
    await page.getByRole('button', { name: 'Nuovo produttore', exact: true }).click();
    await page.getByLabel('Nome del produttore', { exact: true }).fill('Unsaved home navigation fixture');
    let cancelled = false;
    page.once('dialog', async d => { cancelled = true; await d.dismiss(); });
    await nav.getByRole('button', { name: 'Benvenuto', exact: true }).click();
    assert(cancelled); assert(await page.getByLabel('Nome del produttore', { exact: true }).isVisible());
    page.once('dialog', d => d.accept()); await welcome();
    await page.evaluate(() => document.fonts.ready);
    let fonts;
    for (const mode of ['Tema: Chiaro', 'Tema: Fosfori verdi']) {
      await page.getByRole('button', { name: mode, exact: true }).click();
      for (const width of [320, 390, 768, 1440]) {
        await page.setViewportSize({ width, height: 1000 });
        assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), 'Home overflows at ' + width);
        const eras = await page.locator('.home-era').evaluateAll(nodes => nodes.map(node => ({
          top: node.getBoundingClientRect().top,
          height: node.getBoundingClientRect().height,
          label: node.querySelector('strong').getBoundingClientRect().top,
        })));
        for (const era of eras) {
          const peers = eras.filter(other => Math.abs(other.top - era.top) < 1);
          assert(peers.every(other => Math.abs(other.label - era.label) < 1 && Math.abs(other.height - era.height) < 1),
            'Era labels must align at the top of each row: ' + JSON.stringify(eras));
        }
      }
      const current = await page.locator('h1').evaluate(e => {
        const s = getComputedStyle(e); return [s.fontFamily, s.fontSize, s.fontWeight];
      });
      if (fonts) assert.deepEqual(current, fonts); else fonts = current;
    }
    // A failed home request can be retried; it never blocks the existing nav.
    let failing = true;
    await page.route('**/api/home', route => route.fulfill({ status: failing ? 503 : 200, contentType: 'application/json',
      body: JSON.stringify(failing ? { detail: 'Synthetic temporary home error' } : home) }));
    await page.reload(); await page.getByRole('alert').filter({ hasText: 'Synthetic temporary home error' }).waitFor();
    failing = false; await page.getByRole('button', { name: 'Riprova', exact: true }).click();
    await page.waitForFunction(() => !document.querySelector('[role=alert]'));
    await page.unroute('**/api/home');
    await page.route('**/api/home', route => route.fulfill({ contentType: 'application/json',
      body: JSON.stringify({ summary: { systems: 0, manufacturers: 0 }, spotlight: null, featured: [] }) }));
    await page.reload(); await page.getByRole('heading', { name: 'La collezione comincia da qui.', exact: true }).waitFor();
    assert.equal(await page.locator('.home-showcase').count(), 0);
    assert.equal(await page.locator('.home-exhibit').count(), 0);
    assert.equal(await page.locator('.home-stat strong').first().innerText(), '0');
    await page.getByRole('button', { name: 'Entra nel catalogo', exact: true }).click();
    await page.getByRole('heading', { name: 'Catalogo sistemi', exact: true, level: 1 }).waitFor();
    assert.deepEqual(errors, []);
    console.log('Home: live counts/IDs, all destinations, cards/companies, filters/comparison, unsaved changes, empty/error/retry and both themes at 320/390/768/1440px pass.');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exit(1); });
