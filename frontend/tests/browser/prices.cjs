/* Synthetic workbook only; deletes only the three computers it creates. */
const assert = require('node:assert/strict');
const { chromium } = require('playwright');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const { execFileSync } = require('node:child_process');

(async () => {
  const base = process.env.HHE_BASE_URL || 'http://127.0.0.1:18081/';
  assert(['127.0.0.1', 'localhost', '[::1]'].includes(new URL(base).hostname));
  const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || undefined,
    args: ['--no-sandbox', '--disable-dev-shm-usage'] });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  const errors = []; page.on('pageerror', error => errors.push(error.message));
  const api = route => new URL('/api' + route, base).href;
  const files = fs.mkdtempSync(path.join(os.tmpdir(), 'hhe-price-browser-'));
  const ids = [];
  try {
    const meta = await (await page.request.get(api('/meta'))).json();
    const maker = meta.manufacturers[0];
    const prefix = 'SyntheticPriceBrowser-' + Date.now();
    for (const suffix of ['A', 'B', 'C']) {
      const response = await page.request.post(api('/computers'), { data: { model_name: prefix + '-' + suffix, manufacturer_id: maker.id } });
      assert.equal(response.status(), 201); ids.push((await response.json()).id);
    }
    const workbook = path.join(files, 'synthetic-prices.xlsx');
    const backend = path.resolve(__dirname, '../../../backend');
    execFileSync(process.env.HHE_PYTHON || 'python', [path.join(backend, 'tests/price_workbook_fixture.py'), workbook, maker.name, prefix],
      { env: { ...process.env, PYTHONPATH: backend } });
    await page.goto(base);
    await page.getByRole('button', { name: 'Amministrazione', exact: true }).click();
    await page.getByRole('button', { name: 'Importazioni', exact: true }).click();
    await page.getByLabel('Fonte dati', { exact: true }).selectOption('historical_prices');
    await page.getByLabel('Excel dei prezzi o dataset CSV/JSON', { exact: false }).setInputFiles(workbook);
    await page.getByLabel('Ho verificato il diritto', { exact: false }).check();
    await page.getByRole('button', { name: 'Prepara anteprima dal file', exact: true }).click();
    const report = page.getByRole('region', { name: 'Controllo Excel dei prezzi' });
    await report.waitFor();
    assert.match(await report.innerText(), /4 sistemi; 1 senza importo esclusi/);
    assert.match(await report.innerText(), /Prezzi numerici: 2; sole note: 1/);
    assert.match(await report.innerText(), /riallineate: 1/);
    const priceBefore = await (await page.request.get(api('/computers/' + ids[0]))).json();
    assert.equal(priceBefore.releases.length, 0, 'Preview must not apply prices.');
    const downloaded = page.waitForEvent('download');
    await page.getByRole('link', { name: 'Scarica originale conservato', exact: true }).click();
    const download = await downloaded;
    assert.equal(download.suggestedFilename(), 'import-original.xlsx');
    assert.deepEqual(fs.readFileSync(await download.path()), fs.readFileSync(workbook));
    await page.getByRole('button', { name: "Applica le righe pronte all'archivio", exact: true }).click();
    await page.locator('.import-detail h3').filter({ hasText: 'Completata' }).waitFor();
    const first = await (await page.request.get(api('/computers/' + ids[0]))).json();
    const second = await (await page.request.get(api('/computers/' + ids[1]))).json();
    const context = await (await page.request.get(api('/computers/' + ids[2]))).json();
    assert.equal(first.releases[0].price, 1000.5);
    assert.equal(first.releases[0].release_date, null); assert.equal(first.year, null);
    assert.equal(first.releases[0].sources[0].access_date, null);
    assert.match(first.facts[0].statement, /Synthetic configuration with monitor/);
    assert.equal(second.releases[0].price_type, 'listino successivo');
    assert.equal(context.releases.length, 0); assert.equal(context.facts.length, 1);
    await page.getByRole('button', { name: 'Riprova con una nuova anteprima', exact: true }).click();
    await page.getByRole('button', { name: "Applica le righe pronte all'archivio", exact: true }).click();
    await page.locator('.import-detail h3').filter({ hasText: 'Completata' }).waitFor();
    assert.match(await page.locator('.import-detail').innerText(), /Invariata: 3/);
    for (const width of [320, 390]) {
      await page.setViewportSize({ width, height: 900 });
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    }
    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.getByRole('button', { name: 'Catalogo', exact: true }).click();
    await page.getByPlaceholder('Cerca un sistema…', { exact: true }).fill(prefix + '-A');
    await page.locator('.catalog-card').filter({ has: page.getByRole('heading', { name: prefix + '-A', exact: true }) })
      .getByRole('button', { name: 'Dettagli', exact: true }).click();
    await page.getByRole('heading', { name: prefix + '-A', exact: true, level: 1 }).waitFor();
    const shown = await page.locator('main').innerText();
    assert.doesNotMatch(shown, /Ricerca da verificare/i);
    assert.match(shown, /Synthetic configuration with monitor/);
    assert.deepEqual(errors, []);
    console.log('PASS price browser: original Excel, price context without research badge, undated/later-list prices, unchanged replay, source preservation and mobile.');
  } finally {
    for (const id of ids) await page.request.delete(api('/computers/' + id)).catch(() => {});
    await browser.close();
    fs.rmSync(files, { recursive: true, force: true });
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
