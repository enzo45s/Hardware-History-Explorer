/* Requires the isolated backend/tests/browser_bulk_app.py fixture, never a live website. */
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

(async () => {
  const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || undefined,
    args: ['--no-sandbox', '--disable-dev-shm-usage'] });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  page.setDefaultTimeout(60000);
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  const base = process.env.HHE_BASE_URL || 'http://127.0.0.1:8080/';
  const apiBase = process.env.HHE_BULK_API_URL || 'http://127.0.0.1:18093';
  const dir = process.env.HHE_ARTIFACT_DIR || path.resolve(__dirname, '../../test-results/imports');
  fs.mkdirSync(dir, { recursive: true });
  try {
    const fixture = await (await page.request.get(apiBase + '/__bulk_fixture')).json();
    assert.equal(fixture.fixture, '1000bit-bulk-synthetic');
    assert.equal(fixture.isolated, true);
    // Exercise the built frontend, forwarding API calls to a disposable fixture.
    await page.route('**/api/**', async route => {
      const original = new URL(route.request().url());
      const response = await route.fetch({ url: new URL(original.pathname + original.search, apiBase).href });
      await route.fulfill({ response });
    });
    const meta = await (await page.request.get(apiBase + '/api/meta')).json();
    const maker = meta.manufacturers.find(m => m.name === 'Commodore');
    for (const name of ['Amiga 1200', 'Bulk Browser Fixture']) {
      const response = await page.request.post(apiBase + '/api/computers', { data: {
        model_name: name, manufacturer_id: maker.id, description: 'Synthetic browser baseline description' } });
      assert.equal(response.status(), 201);
    }
    const before = (await (await page.request.get(apiBase + '/api/computers')).json()).total;
    async function openPanel() {
      await page.getByRole('button', { name: 'Amministrazione', exact: true }).click();
      await page.getByRole('button', { name: 'Importazioni', exact: true }).click();
      await page.getByLabel('Fonte dati', { exact: true }).selectOption('1000bit');
    }
    await page.goto(base);
    await openPanel();
    const panel = page.getByRole('region', { name: 'Arricchimento automatico del catalogo da 1000bit', exact: true });
    await panel.getByRole('button', { name: 'Avvia arricchimento di tutto il catalogo', exact: true }).click();
    await panel.getByText(/Richieste effettuate: 1 di/).waitFor();
    await panel.getByRole('button', { name: 'Metti in pausa la raccolta', exact: true }).click();
    await panel.getByRole('button', { name: 'Riprendi arricchimento del catalogo', exact: true }).waitFor();
    const paused = (await (await page.request.get(apiBase + '/api/admin/1000bit/bulk')).json()).job;
    assert.equal(paused.status, 'paused');
    assert(paused.requests >= 1 && paused.requests < 6, 'Pause must retain partial progress.');
    await page.reload();
    await openPanel();
    await panel.getByRole('button', { name: 'Riprendi arricchimento del catalogo', exact: true }).click();
    await panel.getByRole('heading', { name: /Visita terminata/ }).waitFor();
    const done = (await (await page.request.get(apiBase + '/api/admin/1000bit/bulk')).json()).job;
    assert.equal(done.id, paused.id);
    assert.equal(done.counts.updated, 2);
    assert.equal((await (await page.request.get(apiBase + '/api/computers')).json()).total, before);
    assert.equal(done.requests, 6);
    const report = await (await page.request.get(apiBase + `/api/admin/1000bit/bulk/${done.id}/report`)).json();
    assert.equal(report.targets.length, before);
    await page.screenshot({ path: path.join(dir, 'bulk-desktop.png'), fullPage: true });
    for (const width of [320, 390]) {
      await page.setViewportSize({ width, height: 844 });
      await page.evaluate(() => document.fonts.ready);
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), 'Mobile overflow');
    }
    await page.screenshot({ path: path.join(dir, 'bulk-mobile.png'), fullPage: true });
    assert.deepEqual(errors, []);
    fs.writeFileSync(path.join(dir, 'bulk-browser-validation.json'), JSON.stringify({ before, after: before, job: done, jsErrors: errors }, null, 2));
    console.log('Bulk browser: automatic traversal, pause/reload/resume, sourced updates, unchanged catalog size and desktop/mobile pass.');
  } catch (error) {
    await page.screenshot({ path: path.join(dir, 'bulk-failure.png'), fullPage: true });
    throw error;
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
