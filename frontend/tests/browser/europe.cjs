/* Isolated synthetic country profiles, original preservation, and deployed UI cache checks. */
const assert = require('node:assert/strict');
const { chromium } = require('playwright');

(async () => {
  const base = process.env.HHE_BASE_URL || 'http://127.0.0.1:18181/';
  assert(['127.0.0.1', 'localhost', '[::1]'].includes(new URL(base).hostname));
  const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || undefined,
    args: ['--no-sandbox', '--disable-dev-shm-usage'] });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  const errors = []; page.on('pageerror', error => errors.push(error.message));
  const api = route => new URL('/api' + route, base).href;
  let id;
  try {
    const htmlResponse = await page.request.get(base);
    assert.match(htmlResponse.headers()['cache-control'], /no-store/);
    const html = await htmlResponse.text();
    const asset = html.match(/src="([^"]*\/assets\/[^\"]+\.js)"/)[1];
    const assetResponse = await page.request.get(new URL(asset, base).href);
    assert.match(assetResponse.headers()['cache-control'], /immutable/);
    assert.doesNotMatch(await assetResponse.text(), /Provenienza (?:dei )?dati accorpati/);
    const build = await page.request.get(new URL('/build-info.json', base).href);
    assert.match(build.headers()['cache-control'], /no-store/);
    assert.equal((await build.json()).ui_version, '2026-11-europe-1');
    assert.equal((await page.request.get(new URL('/assets/missing-fixture.js', base).href)).status(), 404);

    const meta = await (await page.request.get(api('/meta'))).json();
    const suffix = Date.now();
    const model = 'SyntheticEurope-' + suffix;
    const post = async (route, data) => {
      const response = await page.request.post(api(route), { data });
      assert.equal(response.status(), 201, await response.text());
      return response.json();
    };
    const source = await post('/sources', { title: 'Synthetic European price document ' + suffix, url: 'https://example.org/synthetic-prices' });
    const names = ['Spain', 'Italy', 'UK', 'France', 'Japan'];
    const markets = [];
    for (const name of names) markets.push(meta.markets.find(row => row.name === name) || await post('/markets', { name }));
    const data = { model_name: model, manufacturer_id: meta.manufacturers[0].id, description: 'Synthetic regional data',
      configurations: ['Spain', 'Italy', 'UK', 'France', 'USA'].map(variant_name => ({ variant_name, specifications: [
        { component_type: 'RAM', property_name: 'Capacità', numeric_value: 64, unit: 'KiB' },
        { component_type: 'CPU', property_name: 'Modello', text_value: 'Synthetic CPU' }] })),
      releases: markets.map(market => ({ market_id: market.id, release_date: '2002', price: 1000,
        currency: market.name === 'Japan' ? 'JPY' : 'USD', source_ids: [source.id] }))
    };
    id = (await post('/computers', data)).id;
    const raw = await (await page.request.get(api('/admin/computers/' + id))).json();
    assert.equal(raw.configurations.length, 5); assert.equal(raw.releases.length, 5);
    const open = async () => {
      await page.goto(base);
      await page.getByRole('button', { name: 'Catalogo', exact: true }).click();
      await page.getByPlaceholder('Cerca un sistema…', { exact: true }).fill(model);
      await page.locator('.catalog-card').filter({ has: page.getByRole('heading', { name: model, exact: true }) })
        .getByRole('button', { name: 'Dettagli', exact: true }).click();
      await page.getByRole('heading', { name: model, exact: true, level: 1 }).waitFor();
    };
    await open();
    assert.equal(await page.getByRole('region', { name: /^Configurazione ·/ }).count(), 1);
    assert.equal(await page.getByRole('region', { name: 'Configurazione · Scheda tecnica', exact: true }).count(), 1);
    const europe = page.getByRole('region', { name: 'Commercializzazione · Europa', exact: true });
    assert.equal(await page.getByRole('region', { name: /^Commercializzazione ·/ }).count(), 2);
    assert.match(await europe.innerText(), /2002 · 1000 USD/);
    assert.equal(await europe.locator('details').count(), 0);
    assert.equal(await europe.locator('a').count(), 1);
    assert.equal(await page.getByText(/Provenienza (?:dei )?dati accorpati/i).count(), 0);
    for (const width of [320, 390]) {
      await page.setViewportSize({ width, height: 1000 });
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    }
    const payload = { ...raw }; delete payload.id;
    payload.releases[2] = { ...payload.releases[2], price: 2000, currency: 'GBP' };
    payload.configurations[2].specifications[0].numeric_value = 128;
    const update = await page.request.put(api('/computers/' + id), { data: payload });
    assert.equal(update.status(), 200, await update.text());
    await open();
    assert.equal(await page.getByRole('region', { name: /^Configurazione ·/ }).count(), 2);
    assert.equal(await page.getByRole('region', { name: 'Commercializzazione · Europa', exact: true }).count(), 1);
    assert.match(await europe.innerText(), /1000 USD/); assert.match(await europe.innerText(), /2000 GBP/);
    const after = await (await page.request.get(api('/admin/computers/' + id))).json();
    assert.deepEqual(after.configurations.map(row => row.id), raw.configurations.map(row => row.id));
    assert.equal(after.releases.length, 5);
    assert.deepEqual(errors, []);
    console.log('PASS Europe: identical country profiles/offers consolidated, different RAM/prices/currencies preserved, raw IDs unchanged, provenance absent, mobile and fresh HTML/build-info cache headers.');
  } finally {
    if (id) await page.request.delete(api('/computers/' + id)).catch(() => {});
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
