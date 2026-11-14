/* Runs against an isolated Compose project. Uploads synthetic fixtures only. */
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

async function layoutDetails(page) {
  return page.evaluate(() => {
    const width = innerWidth;
    const overflow = [...document.querySelectorAll('body *')].filter(element => {
      const bounds = element.getBoundingClientRect();
      if (!bounds.width || bounds.right <= width || !element.getClientRects().length) return false;
      // Horizontal scrolling inside the mobile navigation is intentional.
      for (let parent = element.parentElement; parent; parent = parent.parentElement) {
        if (['auto', 'scroll', 'hidden', 'clip'].includes(getComputedStyle(parent).overflowX)) return false;
      }
      return true;
    }).slice(0, 20).map(element => ({ tag: element.tagName, className: element.getAttribute('class'),
      text: element.textContent?.trim().slice(0, 100), right: element.getBoundingClientRect().right }));
    const tabs = document.querySelector('.admin-tabs');
    return { viewport: width, documentWidth: document.documentElement.scrollWidth,
      fontFamily: getComputedStyle(document.body).fontFamily, fonts: document.fonts.status, overflow,
      tabs: tabs ? { left: tabs.getBoundingClientRect().left, right: tabs.getBoundingClientRect().right,
        buttons: [...tabs.children].map(button => ({ text: button.textContent,
          left: button.getBoundingClientRect().left, right: button.getBoundingClientRect().right })) } : null };
  });
}

async function assertMobileLayout(page) {
  await page.evaluate(() => document.fonts.ready);
  const layout = await layoutDetails(page);
  assert(layout.documentWidth <= layout.viewport, 'Horizontal overflow: ' + JSON.stringify(layout));
  // Controls must fit the content area as well as the viewport.
  const tabsFit = await page.locator('.admin-tabs').evaluate(tabs => {
    const bounds = tabs.getBoundingClientRect();
    return [...tabs.children].every(button => {
      const rect = button.getBoundingClientRect();
      return rect.left >= bounds.left && rect.right <= bounds.right;
    });
  });
  assert(tabsFit, 'Administrative tabs extend outside their container: ' + JSON.stringify(layout));
}

(async () => {
  const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROMIUM_PATH || undefined,
    args: ['--no-sandbox', '--disable-dev-shm-usage'] });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  const artifactDir = process.env.HHE_ARTIFACT_DIR || path.resolve(__dirname, '../../test-results/imports');
  fs.mkdirSync(artifactDir, { recursive: true });
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  const model = `Synthetic Browser Fixture ${Date.now()}`;
  const record = { external_id: model, manufacturer: 'Synthetic Browser Test Manufacturer', model_name: model,
    source: { title: 'Synthetic browser fixture', url: 'https://example.org/browser-fixture' },
    releases: [{ market: 'Synthetic market', release_date: '1980' }],
    configurations: [{ variant_name: 'Synthetic variant', specifications: [{ component_type: 'RAM', property_name: 'Capacity', numeric_value: 4, unit: 'KB' }] }] };
  try {
    await page.goto(process.env.HHE_BASE_URL || 'http://127.0.0.1:18080/', { waitUntil: 'domcontentloaded' });
    await page.getByRole('button', { name: 'Amministrazione', exact: true }).click();
    await page.getByRole('button', { name: 'Importazioni', exact: true }).click();
    async function upload(data) {
      await page.getByLabel('Dataset CSV o JSON', { exact: false }).setInputFiles({ name: 'browser-fixture.json', mimeType: 'application/json', buffer: Buffer.from(JSON.stringify([data])) });
      await page.getByLabel('Ho verificato il diritto', { exact: false }).check();
      await page.getByRole('button', { name: 'Prepara anteprima dal file', exact: true }).click();
      await page.getByRole('button', { name: "Applica le righe pronte all'archivio", exact: true }).waitFor();
      assert.equal(await page.locator('.import-detail .import-row').count(), 1);
      await page.getByRole('button', { name: "Applica le righe pronte all'archivio", exact: true }).click();
      await page.locator('.import-detail h3').filter({ hasText: 'Completata' }).waitFor();
    }
    await upload(record);
    assert.match(await page.locator('.import-detail').innerText(), /Importata: 1/);
    const updated = JSON.parse(JSON.stringify(record));
    updated.configurations[0].specifications[0].numeric_value = 8;
    await upload(updated);
    const row = page.locator('.import-row');
    await row.getByText(/Fonti e verifiche/).click();
    const conflict = row.locator('.import-conflict');
    assert.equal(await conflict.count(), 1);
    await conflict.getByRole('textbox').fill('Verified against the synthetic browser fixture only.');
    await conflict.getByRole('button', { name: 'Accetta il valore della fonte e verifica' }).click();
    await page.waitForFunction(() => !document.querySelector('.import-conflict'));
    console.log('Browser: upload, staging, explicit apply, duplicate detection, sourced conflict and human review pass.');

    const alias = { ...updated, manufacturer: 'Synthetic Manufacturer Alternative' };
    await upload(alias);
    await page.locator('.import-row').getByText(/Fonti e verifiche/).click();
    const manufacturerConflict = page.locator('.import-conflict');
    assert.equal(await manufacturerConflict.count(), 1);
    assert.equal(await manufacturerConflict.locator('b').first().innerText(), 'Produttore');
    assert.deepEqual(await manufacturerConflict.locator('.import-values dd').allTextContents(),
      ['Synthetic Manufacturer Alternative', 'Synthetic Browser Test Manufacturer']);
    assert.match(await manufacturerConflict.innerText(), /Fonte a supporto: Synthetic browser fixture/);
    await manufacturerConflict.getByRole('textbox').fill('Keep the existing synthetic manufacturer name.');
    await manufacturerConflict.getByRole('button', { name: 'Mantieni il dato attuale', exact: true }).click();
    await page.waitForFunction(() => !document.querySelector('.import-conflict'));
    console.log('Browser: manufacturer names replace raw IDs, bibliography stays separate, retaining the current value records rejection.');

    for (const title of [/Ultime importazioni/i, /Duplicati già importati/i, /Completa le categorie/i, /Rifinisci catalogo/i]) {
      assert.equal(await page.locator('.imports h3, .imports summary').filter({ hasText: title }).count(), 0);
    }
    assert.equal(await page.getByText('Svuota archivio per un nuovo import', { exact: true }).count(), 1);
    console.log('Browser: simplified imports panel keeps the current result and archive reset, without history or maintenance sections.');

    await page.getByRole('button', { name: 'Tema: Fosfori verdi', exact: true }).click();
    await page.screenshot({ path: path.join(artifactDir, 'imports-desktop.png'), fullPage: true });
    for (const width of [320, 390]) {
      await page.setViewportSize({ width, height: 740 });
      await assertMobileLayout(page);
      // A wider local font catches tab sizing even when web fonts cannot load.
      const originalFamily = await page.evaluate(() => {
        const original = document.documentElement.style.fontFamily;
        document.documentElement.style.fontFamily = 'monospace';
        return original;
      });
      try { await assertMobileLayout(page); }
      finally { await page.evaluate(family => { document.documentElement.style.fontFamily = family; }, originalFamily); }
    }
    await page.setViewportSize({ width: 320, height: 740 });
    await page.screenshot({ path: path.join(artifactDir, 'imports-mobile.png'), fullPage: true });
    await page.getByRole('button', { name: 'Confronta', exact: true }).click();
    const search = page.getByRole('combobox', { name: 'Cerca un sistema da aggiungere' });
    await search.fill(model);
    await page.getByRole('option').filter({ hasText: model }).waitFor();

    // Real 1000bit excerpt supplied by the operator; applied only to this test DB.
    const endpoint = route => new URL(route, page.url()).href;
    const meta = await (await page.request.get(endpoint('/api/meta'))).json();
    const maker = meta.manufacturers.find(m => m.name === 'Commodore');
    assert(maker, 'The disposable seed must include Commodore.');
    const catalog = await (await page.request.get(endpoint('/api/computers?q=Amiga%201200'))).json();
    let amiga = catalog.items.find(c => c.model_name === 'Amiga 1200' && c.manufacturer_id === maker.id);
    if (!amiga) {
      const response = await page.request.post(endpoint('/api/computers'), { data: {
        model_name: 'Amiga 1200', manufacturer_id: maker.id, description: 'Scheda iniziale del test browser: da conservare.' } });
      assert.equal(response.status(), 201);
      amiga = await response.json();
    }
    const beforeAmiga = await (await page.request.get(endpoint('/api/computers/' + amiga.id))).json();
    const count = (await (await page.request.get(endpoint('/api/computers'))).json()).total;
    await page.getByRole('button', { name: 'Amministrazione', exact: true }).click();
    await page.getByRole('button', { name: 'Importazioni', exact: true }).click();
    await page.getByLabel('Fonte dati', { exact: true }).selectOption('1000bit');
    assert.equal(await page.getByLabel('Aggiorna solo calcolatori già presenti', { exact: true }).isChecked(), true);
    const remote = page.getByRole('button', { name: 'Recupera dalla fonte e prepara anteprima', exact: true });
    assert.equal(await remote.isEnabled(), false);
    await page.getByLabel('URL delle schede 1000bit', { exact: false }).fill('https://www.1000bit.it/scheda.asp?id=282');
    assert.equal(await remote.isEnabled(), true);
    async function uploadSheet() {
      await page.getByLabel('Scheda HTML o dataset CSV/JSON 1000bit', { exact: false })
        .setInputFiles(path.resolve(__dirname, '../../../backend/tests/fixtures/1000bit-amiga1200.html'));
      await page.getByLabel('Ho verificato il diritto', { exact: false }).check();
      await page.getByRole('button', { name: 'Prepara anteprima dal file', exact: true }).click();
      await page.getByRole('button', { name: "Applica le righe pronte all'archivio", exact: true }).waitFor();
      assert.match(await page.locator('.import-detail').innerText(), /Solo aggiornamenti/);
      assert.equal((await (await page.request.get(endpoint('/api/computers'))).json()).total, count);
      await page.getByRole('button', { name: "Applica le righe pronte all'archivio", exact: true }).click();
      await page.locator('.import-detail h3').filter({ hasText: 'Completata' }).waitFor();
    }
    await uploadSheet();
    assert.match(await page.locator('.import-detail').innerText(), /(?:Aggiornata|Invariata): 1/);
    await uploadSheet();
    assert.match(await page.locator('.import-detail').innerText(), /Invariata: 1/);
    const updatedAmiga = await (await page.request.get(endpoint('/api/computers/' + amiga.id))).json();
    const sheet = updatedAmiga.configurations.find(c => c.variant_name === 'Scheda tecnica');
    assert.equal(sheet.specifications.find(s => s.component_type === 'CPU' && s.property_name === 'Modello').text_value, '68EC020');
    assert.deepEqual(updatedAmiga.releases, beforeAmiga.releases, 'Production date and zero currency placeholder do not alter commercial releases.');
    assert(sheet.specifications.every(s => s.sources.some(c => c.url === 'https://www.1000bit.it/scheda.asp?id=282')));
    for (const width of [320, 390]) {
      await page.setViewportSize({ width, height: 740 });
      await assertMobileLayout(page);
    }
    await page.screenshot({ path: path.join(artifactDir, '1000bit-import-mobile.png'), fullPage: true });
    console.log('Browser: 1000bit HTML preview, existing-only update, sourced CPU, replay without duplicates and missing-price handling pass.');
    assert.deepEqual(errors, []);
    console.log('Browser: imported system searchable in comparison, dark/mobile layout fits at 320 px, no JavaScript errors.');
  } catch (error) {
    try {
      await page.screenshot({ path: path.join(artifactDir, 'failure.png'), fullPage: true });
      fs.writeFileSync(path.join(artifactDir, 'failure-layout.json'), JSON.stringify(await layoutDetails(page), null, 2));
    } catch (captureError) { console.error('Browser diagnostic capture failed:', captureError.message); }
    throw error;
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
