/* Runs against an isolated Compose project. Uploads synthetic fixtures only. */
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');

(async () => {
  const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROMIUM_PATH || undefined,
    args: ['--no-sandbox', '--disable-dev-shm-usage'] });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  const model = `Synthetic Browser Fixture ${Date.now()}`;
  const record = { manufacturer: 'Synthetic Browser Test Manufacturer', model_name: model,
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

    await page.getByRole('button', { name: 'Tema: Fosfori verdi', exact: true }).click();
    if (process.env.HHE_ARTIFACT_DIR) {
      fs.mkdirSync(process.env.HHE_ARTIFACT_DIR, { recursive: true });
      await page.screenshot({ path: `${process.env.HHE_ARTIFACT_DIR}/imports-desktop.png`, fullPage: true });
    }
    await page.setViewportSize({ width: 320, height: 740 });
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    if (process.env.HHE_ARTIFACT_DIR) await page.screenshot({ path: `${process.env.HHE_ARTIFACT_DIR}/imports-mobile.png`, fullPage: true });
    await page.getByRole('button', { name: 'Confronta', exact: true }).click();
    const search = page.getByRole('combobox', { name: 'Cerca un sistema da aggiungere' });
    await search.fill(model);
    await page.getByRole('option').filter({ hasText: model }).waitFor();
    assert.deepEqual(errors, []);
    console.log('Browser: imported system searchable in comparison, dark/mobile layout fits at 320 px, no JavaScript errors.');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
