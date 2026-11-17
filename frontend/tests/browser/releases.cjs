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
    assert.match(await summary.innerText(), /Data del modello/);
    assert.equal(await summary.locator('a:visible').count(), 2);
    await summary.getByText('Provenienza dei dati accorpati', { exact: true }).click();
    assert.match(await summary.innerText(), /Non specificato dalla fonte/);
    assert.match(await summary.innerText(), /Data non disponibile · 3298 USD/);
    assert(await summary.locator('details').getByRole('link', { name: 'Fonte: ' + dated.title, exact: true }).isVisible());
    assert(await summary.locator('details').getByRole('link', { name: 'Fonte: ' + priced.title, exact: true }).isVisible());
    for (const width of [320, 390]) {
      await page.setViewportSize({ width, height: 1000 });
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    }
    const raw = await (await page.request.get(api('/admin/computers/' + id))).json();
    assert.equal(raw.releases.length, 2); assert.equal(raw.releases[1].release_date, null);
    let response = await page.request.put(api('/computers/' + id), { data: {
      model_name: model, manufacturer_id: raw.manufacturer_id,
      releases: [...raw.releases, { market_id: japan.id, price: 200000, currency: 'JPY', source_ids: [priced.id] }]
    } });
    assert.equal(response.status(), 200, await response.text());
    await open();
    assert.equal(await page.getByRole('region', { name: /^Commercializzazione ·/ }).count(), 3);
    assert.match(await page.getByRole('region', { name: 'Commercializzazione · Stati Uniti', exact: true }).innerText(), /Data non disponibile · 3298 USD/);
    response = await page.request.put(api('/computers/' + id), { data: {
      model_name: model, manufacturer_id: raw.manufacturer_id,
      releases: [raw.releases[0], { ...raw.releases[1], price_type: 'listino successivo' }]
    } });
    assert.equal(response.status(), 200, await response.text());
    await open();
    assert.equal(await page.getByRole('region', { name: /^Commercializzazione ·/ }).count(), 2);
    assert.match(await page.getByRole('region', { name: 'Commercializzazione · Stati Uniti', exact: true }).innerText(), /Data non disponibile · 3298 USD/);
    assert.deepEqual(errors, []);
    console.log('PASS releases: one regional 1982/3298 USD summary, original source provenance, raw editor unchanged, ambiguous markets and later lists kept separate, mobile 320/390px.');
  } finally {
    if (id) await page.request.delete(api('/computers/' + id)).catch(() => {});
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
