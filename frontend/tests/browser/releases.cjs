/* Real API + rendered catalog; only synthetic records on a local test instance. */
const assert = require('node:assert/strict');
const { chromium } = require('playwright');

(async () => {
  const base = process.env.HHE_BASE_URL || 'http://127.0.0.1:18081/';
  assert(['127.0.0.1', 'localhost', '[::1]'].includes(new URL(base).hostname));
  const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || undefined,
    args: ['--no-sandbox', '--disable-dev-shm-usage'] });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } });
  const errors = []; page.on('pageerror', error => errors.push(error.message));
  const api = route => new URL('/api' + route, base).href;
  let id;
  try {
    const meta = await (await page.request.get(api('/meta'))).json();
    const suffix = Date.now();
    const model = 'SyntheticReleaseBrowser-' + suffix;
    const post = async (route, data) => {
      const response = await page.request.post(api(route), { data });
      assert.equal(response.status(), 201, await response.text());
      return response.json();
    };
    const market = async name => meta.markets.find(row => row.name === name) ?? await post('/markets', { name });
    const unknown = await market('Non specificato dalla fonte');
    const us = await market('Stati Uniti');
    const japan = await market('Giappone');
    const dated = await post('/sources', { title: 'Synthetic model-date source ' + suffix, url: 'https://example.org/synthetic-date' });
    const priced = await post('/sources', { title: 'Synthetic regional-price source ' + suffix, url: 'https://example.org/synthetic-price' });
    const releases = [
      { market_id: unknown.id, release_date: '1982', source_ids: [dated.id] },
      { market_id: us.id, price: 3298, currency: 'USD', price_type: 'prezzo riportato', source_ids: [priced.id] }
    ];
    id = (await post('/computers', { model_name: model, manufacturer_id: meta.manufacturers[0].id, releases })).id;
    // A base-dataset import still keeps its original technical provenance, but
    // must never add MAME back into the reader/admin bibliography.
    const imported = await page.request.post(api('/admin/imports/upload'), { multipart: {
      provider: 'manual', rights_confirmed: 'true', file: { name: 'synthetic-base.json', mimeType: 'application/json',
        buffer: Buffer.from(JSON.stringify([{ manufacturer: meta.manufacturers[0].name, model_name: model,
          source: { title: 'MAME synthetic base ' + suffix, url: 'https://github.com/mamedev/mame' },
          releases: [{ market: unknown.name, release_date: '1982' }],
          configurations: [{ variant_name: 'Synthetic base', specifications: [
            { component_type: 'CPU', property_name: 'Frequenza', numeric_value: 2, unit: 'MHz' }] }]
        }])) }
    } });
    assert.equal(imported.status(), 201, await imported.text());
    const job = await imported.json();
    const applied = await page.request.post(api('/admin/imports/' + job.id + '/apply'));
    assert.equal(applied.status(), 200);
    assert.equal((await applied.json()).counts.updated, 1);
    const technical = await (await page.request.get(api('/computers/' + id))).json();
    assert(technical.configurations.some(config => config.variant_name === 'Synthetic base' &&
      config.specifications.some(spec => spec.numeric_value === 2 && spec.unit === 'MHz' && spec.sources.length === 0)));
    const sources = await (await page.request.get(api('/sources'))).json();
    assert(!sources.some(source => /mame|mamedev/i.test(JSON.stringify(source))));
    const open = async () => {
      await page.goto(base);
      await page.getByRole('button', { name: 'Catalogo', exact: true }).click();
      await page.getByPlaceholder('Cerca un sistema…', { exact: true }).fill(model);
      const card = page.locator('.catalog-card').filter({ has: page.getByRole('heading', { name: model, exact: true }) });
      await card.getByRole('button', { name: 'Dettagli', exact: true }).click();
      await page.getByRole('heading', { name: model, exact: true, level: 1 }).waitFor();
    };
    await open();
    const summary = page.getByRole('region', { name: 'Commercializzazione · Stati Uniti', exact: true });
    assert.equal(await page.getByRole('region', { name: /^Commercializzazione ·/ }).count(), 1);
    assert.match(await summary.innerText(), /1982 · 3298 USD/);
    assert.equal(await summary.locator('a:visible').count(), 1);
    assert.equal(await summary.locator('details').count(), 0);
    assert(await summary.getByRole('link', { name: 'Fonte: ' + priced.title, exact: true }).isVisible());
    assert.doesNotMatch(await summary.innerText(), /Provenienza dei dati accorpati|Data del modello|Non specificato dalla fonte/);
    assert.doesNotMatch(await page.locator('main').innerText(), /MAME|mamedev/);
    for (const width of [320, 390]) {
      await page.setViewportSize({ width, height: 1000 });
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    }
    const raw = await (await page.request.get(api('/admin/computers/' + id))).json();
    assert.equal(raw.releases.length, 2); assert.equal(raw.releases[1].release_date, null);
    await page.getByRole('button', { name: 'Amministrazione', exact: true }).click();
    await page.getByRole('button', { name: 'Fonti', exact: true }).click();
    await page.getByRole('button', { name: 'Nuova fonte', exact: true }).waitFor();
    assert.doesNotMatch(await page.locator('main').innerText(), /MAME|mamedev/);
    let response = await page.request.put(api('/computers/' + id), { data: {
      model_name: model, manufacturer_id: raw.manufacturer_id,
      releases: [...raw.releases, { market_id: japan.id, price: 200000, currency: 'JPY', source_ids: [priced.id] }]
    } });
    assert.equal(response.status(), 200, await response.text());
    await open();
    assert.equal(await page.getByRole('region', { name: /^Commercializzazione ·/ }).count(), 2);
    assert.match(await page.getByRole('region', { name: 'Commercializzazione · Stati Uniti', exact: true }).innerText(), /1982 · 3298 USD/);
    assert.match(await page.getByRole('region', { name: 'Commercializzazione · Giappone', exact: true }).innerText(), /1982 · 200000 JPY/);
    const normalized = await (await page.request.get(api('/computers/' + id))).json();
    assert.equal(new Set(normalized.display_releases.map(row => row.id)).size, 2);
    assert(normalized.display_releases.every(row => row.date_scope === 'model'));
    assert(normalized.releases.filter(row => row.price != null).every(row => row.release_date === null));
    assert.doesNotMatch(await page.locator('main').innerText(), /Mercato non documentato|Provenienza dei dati accorpati/);
    response = await page.request.put(api('/computers/' + id), { data: {
      model_name: model, manufacturer_id: raw.manufacturer_id,
      releases: [raw.releases[0], { ...raw.releases[1], price_type: 'listino successivo' }]
    } });
    assert.equal(response.status(), 200, await response.text());
    await open();
    assert.equal(await page.getByRole('region', { name: /^Commercializzazione ·/ }).count(), 2);
    assert.match(await page.getByRole('region', { name: 'Commercializzazione · Stati Uniti', exact: true }).innerText(), /Data non disponibile · 3298 USD/);
    assert.deepEqual(errors, []);
    console.log('PASS releases: shared model date across markets, distinct prices, one price source, no provenance box, raw editor and technical evidence preserved, later lists undated, mobile 320/390px.');
  } finally {
    if (id) await page.request.delete(api('/computers/' + id)).catch(() => {});
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
