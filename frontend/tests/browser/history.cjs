/* Built frontend with a disposable Italian-history API; no live-source requests. */
const assert = require('node:assert/strict');
const { chromium } = require('playwright');
(async () => {
  const base = process.env.HHE_BASE_URL || 'http://127.0.0.1:8080/';
  const apiBase = process.env.HHE_HISTORY_API_URL || 'http://127.0.0.1:18094';
  assert(['127.0.0.1', 'localhost'].includes(new URL(apiBase).hostname));
  const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || undefined, args: ['--no-sandbox', '--disable-dev-shm-usage'] });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  const errors = []; page.on('pageerror', error => errors.push(error.message));
  try {
    const marker = await (await page.request.get(apiBase + '/__history_fixture')).json();
    assert.equal(marker.fixture, 'italian-history-synthetic'); assert.equal(marker.isolated, true);
    await page.route('**/api/**', async route => {
      const original = new URL(route.request().url());
      const response = await route.fetch({ url: new URL(original.pathname + original.search, apiBase).href });
      await route.fulfill({ response });
    });
    const meta = await (await page.request.get(apiBase + '/api/meta')).json();
    const maker = meta.manufacturers.find(m => m.name === 'IBM');
    const ids = [];
    for (const [name, description] of [['Synthetic History Browser', 'Synthetic History Browser è un calcolatore di IBM.'], ['Synthetic History Missing', ''], ['Synthetic History Existing', 'Introduzione storica scritta a mano.']]) {
      const r = await page.request.post(apiBase + '/api/computers', { data: { manufacturer_id: maker.id, model_name: name, description } });
      assert.equal(r.status(), 201); ids.push((await r.json()).id);
    }
    async function open() {
      await page.getByRole('button', { name: 'Amministrazione', exact: true }).click();
      await page.getByRole('button', { name: 'Cenni storici', exact: true }).click();
      await page.getByRole('heading', { name: 'Cenni storici in italiano' }).waitFor();
    }
    await page.goto(base); await open();
    await page.getByRole('button', { name: 'Cerca cenni storici', exact: true }).click();
    await page.getByRole('alert').filter({ hasText: 'Pausa sintetica' }).waitFor();
    await page.getByRole('button', { name: 'Riprendi ricerca storica' }).waitFor();
    await page.reload(); await open();
    assert.match(await page.getByRole('region', { name: 'Avanzamento ricerca storica' }).innerText(), /In pausa/);
    await page.getByRole('button', { name: 'Riprendi ricerca storica' }).click();
    await page.getByText('Tentativo 2 · Ricerca: IBM Synthetic History Browser', { exact: true }).waitFor();
    await page.getByRole('heading', { name: /Ricerca #\d+ · Completata/ }).waitFor();
    const panel = await page.getByRole('region', { name: 'Avanzamento ricerca storica' }).innerText();
    assert.match(panel, /Descrizioni aggiornate: 1/); assert.match(panel, /Senza testo adatto: 1/);
    assert.match(panel, /Saltate: 0/); assert.match(panel, /Modificate o rimosse: 0/); assert.match(panel, /Query rifiutate: 0/);
    const snapshot = await (await page.request.get(apiBase + '/api/admin/history')).json();
    const report = await (await page.request.get(apiBase + `/api/admin/history/${snapshot.job.id}/report`)).json();
    assert.equal(report.items.find(item => item.model_name === 'Synthetic History Existing').status, 'preserved');
    const sourceCalls = (await (await page.request.get(apiBase + '/__history_fixture')).json()).calls;
    assert.deepEqual(sourceCalls, ['Synthetic History Browser', 'Synthetic History Browser', 'Synthetic History Browser', 'Synthetic History Missing']);
    assert.equal(snapshot.job.retry_suggested, 1);
    for (const width of [320, 390]) {
      await page.setViewportSize({ width, height: 900 });
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    }
    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.getByRole('button', { name: 'Riprova gli abbinamenti migliorati (1)', exact: true }).click();
    await page.getByRole('region', { name: 'Avanzamento ricerca storica' }).filter({ hasText: 'Descrizioni aggiornate: 2' }).waitFor();
    const retried = await (await page.request.get(apiBase + `/api/admin/history/${snapshot.job.id}/report`)).json();
    assert.equal(retried.items.find(item => item.model_name === 'Synthetic History Missing').previous_runs, 1);
    await page.getByRole('button', { name: 'Fonti e verifica · Synthetic History Browser', exact: true }).click();
    const verification = page.getByRole('region', { name: 'Verifica della descrizione storica' });
    await verification.waitFor();
    assert.match(await verification.innerText(), /Da verificare/);
    await page.getByRole('button', { name: 'Chiudi verifica', exact: true }).click();
    for (const width of [320, 390]) {
      await page.setViewportSize({ width, height: 900 });
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    }
    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.getByRole('button', { name: 'Catalogo', exact: true }).click();
    await page.getByPlaceholder('Cerca un sistema…', { exact: true }).fill('Synthetic History Browser');
    await page.locator('.catalog-card').filter({ has: page.getByRole('heading', { name: 'Synthetic History Browser', exact: true }) }).getByRole('button', { name: 'Dettagli', exact: true }).click();
    await page.getByRole('heading', { name: 'Synthetic History Browser', level: 1, exact: true }).waitFor();
    assert.match(await page.locator('main').innerText(), /contesto storico sintetico/);
    assert.equal(await page.getByRole('link', { name: 'CC BY-SA 4.0', exact: true }).count(), 1);
    await open();
    const callsBeforeRestart = (await (await page.request.get(apiBase + '/__history_fixture')).json()).calls;
    await page.getByRole('button', { name: 'Ricomincia ricerca storica', exact: true }).click();
    await page.waitForFunction(oldId => {
      const heading = document.querySelector('[aria-label="Avanzamento ricerca storica"] h3');
      return heading && !heading.textContent.includes(`Ricerca #${oldId} ·`) && heading.textContent.includes('Completata');
    }, snapshot.job.id);
    const restarted = (await (await page.request.get(apiBase + '/api/admin/history')).json()).job;
    assert.notEqual(restarted.id, snapshot.job.id);
    assert.deepEqual(restarted.counts, { preserved: retried.items.length });
    const archived = await (await page.request.get(apiBase + `/api/admin/history/${snapshot.job.id}/report`)).json();
    assert.equal(archived.job.status, 'archived');
    assert.deepEqual(archived.items, retried.items);
    assert.deepEqual((await (await page.request.get(apiBase + '/__history_fixture')).json()).calls, callsBeforeRestart);
    assert.deepEqual(errors, []);
    console.log('PASS history browser: durable fallback, pause/reload/resume, targeted legacy retry, restart preserving text and reports, source attribution and mobile.');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
