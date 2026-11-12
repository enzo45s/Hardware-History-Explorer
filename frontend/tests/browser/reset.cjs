/* Intentionally destructive. Run only against a disposable local Compose project. */
const assert = require('node:assert/strict');
const { chromium } = require('playwright');
const fs = require('node:fs');
const path = require('node:path');

(async () => {
  assert.equal(process.env.HHE_ALLOW_TEST_RESET, '1', 'Set HHE_ALLOW_TEST_RESET=1 only for a disposable test database.');
  const base = process.env.HHE_BASE_URL || 'http://127.0.0.1:18080/';
  assert(['127.0.0.1', 'localhost', '[::1]'].includes(new URL(base).hostname), 'Reset browser test requires a loopback URL.');
  const artifactDir = process.env.HHE_ARTIFACT_DIR || path.resolve(__dirname, '../../test-results/imports');
  fs.mkdirSync(artifactDir, { recursive: true });
  const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROMIUM_PATH || undefined,
    args: ['--no-sandbox', '--disable-dev-shm-usage'] });
  const page = await browser.newPage({ viewport: { width: 390, height: 800 } });
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  try {
    await page.goto(base, { waitUntil: 'domcontentloaded' });
    await page.getByRole('button', { name: 'Catalogo', exact: true }).click();
    await page.locator('.catalog-card').nth(1).waitFor();
    await page.locator('.catalog-card').nth(0).getByRole('button', { name: '+ Confronta', exact: true }).click();
    await page.locator('.catalog-card').nth(1).getByRole('button', { name: '+ Confronta', exact: true }).click();
    await page.getByPlaceholder('Cerca un sistema…', { exact: true }).fill('Apple');
    await page.getByRole('button', { name: 'Amministrazione', exact: true }).click();
    await page.getByRole('button', { name: 'Importazioni', exact: true }).click();
    await page.getByText('Svuota archivio per un nuovo import', { exact: true }).click();
    await page.getByRole('button', { name: 'Prepara anteprima di svuotamento', exact: true }).click();
    const preview = page.getByRole('region', { name: 'Anteprima svuotamento archivio', exact: true });
    const reset = preview.getByRole('button', { name: 'Svuota i dati elencati', exact: true });
    assert.equal(await reset.isEnabled(), false);
    await preview.getByLabel('Motivazione dello svuotamento', { exact: true }).fill('Reset only the disposable synthetic browser test project.');
    await preview.getByLabel('Scrivi SVUOTA ARCHIVIO per confermare', { exact: true }).fill('SVUOTA ARCHIVIO');
    assert.equal(await reset.isEnabled(), false);
    await preview.getByLabel('Ho salvato un backup del database e delle fotografie', { exact: false }).check();
    assert.equal(await reset.isEnabled(), true);
    for (const width of [320, 390]) {
      await page.setViewportSize({ width, height: 800 });
      await page.evaluate(() => document.fonts.ready);
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), 'Archive reset preview must fit mobile.');
    }
    await page.screenshot({ path: path.join(artifactDir, 'reset-preview.png'), fullPage: true });
    await reset.click();
    await page.getByText('Archivio svuotato. Catalogo: 0 calcolatori.', { exact: false }).waitFor();
    assert.equal((await (await page.request.get(new URL('/api/computers', base).href)).json()).total, 0);
    await page.locator('.import-job').filter({ hasText: 'Archiviata dopo svuotamento' }).first().click();
    await page.locator('.import-detail h3').filter({ hasText: 'Archiviata dopo svuotamento' }).waitFor();
    await page.locator('.import-detail .import-row').first().getByText(/Fonti e verifiche/).click();
    assert.equal(await page.locator('.import-detail .import-review').count(), 0, 'Archived claims must be read-only.');
    await page.getByRole('button', { name: 'Confronta', exact: true }).click();
    await page.getByText('Cerca e seleziona almeno due calcolatori per visualizzare il confronto.', { exact: true }).waitFor();
    await page.getByRole('button', { name: 'Catalogo', exact: true }).click();
    assert.equal(await page.getByPlaceholder('Cerca un sistema…', { exact: true }).inputValue(), '');
    await page.reload({ waitUntil: 'domcontentloaded' });
    await page.getByRole('button', { name: 'Catalogo', exact: true }).click();
    assert.equal((await (await page.request.get(new URL('/api/computers', base).href)).json()).total, 0);
    await page.screenshot({ path: path.join(artifactDir, 'catalog-empty.png'), fullPage: true });
    assert.deepEqual(errors, []);
    console.log('Browser: reset requires preview, exact phrase and backup confirmation; catalog empty, selections/filters cleared, mobile controls fit; no JavaScript errors.');
  } catch (error) {
    await page.screenshot({ path: path.join(artifactDir, 'reset-failure.png'), fullPage: true });
    throw error;
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
