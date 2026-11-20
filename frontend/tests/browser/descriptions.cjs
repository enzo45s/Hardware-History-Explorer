/* Synthetic descriptions only; deletes only the three cards it creates. */
const assert = require('node:assert/strict');
const { chromium } = require('playwright');

(async () => {
  const base = process.env.HHE_BASE_URL || 'http://127.0.0.1:8080/';
  assert(['127.0.0.1', 'localhost', '[::1]'].includes(new URL(base).hostname));
  const api = path => new URL('/api' + path, base).href;
  const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || undefined,
    args: ['--no-sandbox', '--disable-dev-shm-usage'] });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  const ids = [], errors = [];
  page.on('pageerror', error => errors.push(error.message));
  try {
    const meta = await (await page.request.get(api('/meta'))).json();
    const maker = meta.manufacturers.find(m => m.name === 'IBM');
    const prefix = 'SyntheticDescriptionBrowser' + Date.now();
    const models = ['Missing', 'Template', 'Curated'].map(suffix => prefix + suffix);
    for (let i = 0; i < models.length; i++) {
      const description = i === 1 ? `${models[i]} è un calcolatore di IBM.` : i === 2 ? 'Testo curato manualmente da conservare.' : '';
      const r = await page.request.post(api('/computers'), { data: { manufacturer_id: maker.id, model_name: models[i], description } });
      assert.equal(r.status(), 201); ids.push((await r.json()).id);
    }
    const records = [...models, prefix + 'Unmatched'].map((model, i) => ({
      manufacturer: 'International Business Machines Corporation', model_name: 'IBM ' + model,
      description: `Introduzione sintetica ${i}: questo testo verifica il caricamento JSON senza attribuire fatti a computer reali.\nSecondo paragrafo della prova.`,
      source: { title: 'Fonte sintetica descrizioni browser', url: 'https://example.org/synthetic-description-browser', source_type: 'website' },
    }));
    const payload = { name: 'synthetic-descriptions.json', mimeType: 'application/json', buffer: Buffer.from(JSON.stringify(records)) };
    await page.goto(base);
    await page.getByRole('button', { name: 'Amministrazione', exact: true }).click();
    await page.getByRole('button', { name: 'Importazioni', exact: true }).click();
    await page.getByLabel('Fonte dati', { exact: true }).selectOption('historical_descriptions');
    await page.getByLabel('JSON delle descrizioni', { exact: false }).setInputFiles(payload);
    await page.getByLabel('Ho verificato il diritto', { exact: false }).check();
    await page.getByRole('button', { name: 'Prepara anteprima dal file', exact: true }).click();
    const preview = page.getByRole('region', { name: 'Anteprima descrizione riga 1', exact: true });
    await preview.waitFor();
    assert.match(await preview.innerText(), /Descrizione mancante/);
    assert.match(await page.getByRole('region', { name: 'Anteprima descrizione riga 2', exact: true }).innerText(), /Testo preimpostato/);
    assert.match(await page.getByRole('region', { name: 'Anteprima descrizione riga 3', exact: true }).innerText(), /Descrizione già curata/);
    assert.match(await page.getByRole('region', { name: 'Anteprima descrizione riga 4', exact: true }).innerText(), /Nessun abbinamento/);
    assert.equal((await (await page.request.get(api('/computers/' + ids[0]))).json()).description, '');
    const downloaded = page.waitForEvent('download');
    await page.getByRole('link', { name: 'Scarica originale conservato', exact: true }).click();
    const download = await downloaded;
    assert.equal(download.suggestedFilename(), 'import-original.json');
    const rows = page.locator('.import-row');
    await page.getByRole('button', { name: "Applica le righe pronte all'archivio", exact: true }).click();
    await page.locator('.import-detail h3').filter({ hasText: 'Completata' }).waitFor();
    const panel = await page.locator('.import-detail').innerText();
    assert.match(panel, /Aggiornata: 2/); assert.match(panel, /Invariata: 1/); assert.match(panel, /Esclusa: 1/);
    assert.equal((await (await page.request.get(api('/computers/' + ids[0]))).json()).description, records[0].description);
    assert.equal((await (await page.request.get(api('/computers/' + ids[1]))).json()).description, records[1].description);
    assert.equal((await (await page.request.get(api('/computers/' + ids[2]))).json()).description, 'Testo curato manualmente da conservare.');
    await rows.nth(2).locator('summary').filter({ hasText: /^Fonti e verifiche/ }).click();
    await rows.nth(2).getByLabel('Motivazione della decisione', { exact: true }).fill('Confronto manuale della fonte sintetica browser.');
    await rows.nth(2).getByRole('button', { name: 'Accetta il valore della fonte e verifica', exact: true }).click();
    await rows.nth(2).getByText('Verificata', { exact: true }).waitFor();
    assert.equal((await (await page.request.get(api('/computers/' + ids[2]))).json()).description, records[2].description);
    await page.getByRole('button', { name: 'Riprova con una nuova anteprima', exact: true }).click();
    await page.getByRole('button', { name: "Applica le righe pronte all'archivio", exact: true }).click();
    await page.locator('.import-detail h3').filter({ hasText: 'Completata' }).waitFor();
    assert.match(await page.locator('.import-detail').innerText(), /Invariata: 3/);
    for (const width of [320, 390]) {
      await page.setViewportSize({ width, height: 900 });
      const layout = await page.evaluate(() => ({ width: innerWidth, scroll: document.documentElement.scrollWidth,
        overflow: [...document.querySelectorAll('main *')].filter(element => {
          const r = element.getBoundingClientRect();
          return r.width && r.right > innerWidth + 1 && element.getClientRects().length;
        }).slice(0, 10).map(element => ({ tag: element.tagName, class: element.className, text: element.textContent.slice(0, 80) })) }));
      assert(layout.scroll <= layout.width, JSON.stringify(layout));
    }
    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.getByRole('button', { name: 'Catalogo', exact: true }).click();
    await page.getByPlaceholder('Cerca un sistema…', { exact: true }).fill(models[0]);
    await page.locator('.catalog-card').filter({ has: page.getByRole('heading', { name: models[0], exact: true }) })
      .getByRole('button', { name: 'Dettagli', exact: true }).click();
    await page.getByRole('heading', { name: models[0], exact: true, level: 1 }).waitFor();
    assert.match(await page.locator('main').innerText(), /Introduzione sintetica 0/);
    assert.match(await page.locator('main').innerText(), /Fonte sintetica descrizioni browser/);
    assert.deepEqual(errors, []);
    console.log('PASS description import browser: JSON upload, preview, placeholder replacement, conflict review, original download, unchanged replay, catalog sources and mobile.');
  } finally {
    for (const id of ids) await page.request.delete(api('/computers/' + id)).catch(() => {});
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
