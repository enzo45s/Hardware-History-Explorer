const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const apiBase = 'http://127.0.0.1:18098';
const base = apiBase + '/';
(async () => {
  const browser = await chromium.launch({ ...(process.env.HHE_BROWSER_EXECUTABLE ? { executablePath: process.env.HHE_BROWSER_EXECUTABLE } : {}), args: ['--no-sandbox'] });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  const errors = []; page.on('pageerror', error => errors.push(error.message));
  try {
    const manifestResponse = await page.request.get(apiBase + '/__unit_fixture');
    assert.equal(manifestResponse.status(), 200);
    const ids = await manifestResponse.json();
    await page.goto(base);
    await page.getByRole('button', { name: 'Amministrazione', exact: true }).click();
    await page.getByRole('button', { name: 'RAM e varianti', exact: true }).click();
    const panel = page.getByRole('region', { name: 'Revisione delle unità di memoria' });
    await panel.getByRole('button', { name: 'Controlla unità di memoria', exact: true }).click();
    await panel.getByText('2 modifiche su 2 sistemi:', { exact: false }).waitFor();
    await panel.getByText('1 specifiche ancora ambigue', { exact: false }).waitFor();
    await panel.getByText('Valori prima e dopo (2)', { exact: true }).click();
    await panel.getByLabel('Filtra le proposte per modello').fill('KIM');
    await panel.getByRole('heading', { name: 'KIM-1 · ROM', exact: true }).waitFor();
    assert.equal(await panel.getByRole('heading', { name: 'BCS 2030 · RAM', exact: true }).count(), 0);
    await panel.getByLabel('Filtra le proposte per modello').fill('');
    const download = page.waitForEvent('download');
    await panel.getByRole('link', { name: 'Scarica il resoconto con originali e fonti', exact: true }).click();
    const file = await download;
    const report = JSON.parse(await fs.readFile(await file.path(), 'utf8'));
    assert.equal(report.summary.documented_corrections, 2);
    assert.equal(report.changes.find(row => row.model === 'KIM-1').before.text_value, '1 Kb');
    await panel.getByRole('button', { name: 'Applica la revisione documentata delle unità', exact: true }).click();
    await panel.getByRole('status').filter({ hasText: 'Revisione applicata a 2 specifiche' }).waitFor();
    await panel.getByText('0 modifiche su 0 sistemi:', { exact: false }).waitFor();
    await panel.getByText('1 indicazioni non quantificabili', { exact: false }).waitFor();
    for (const model of ['KIM-1', 'BCS 2030']) {
      const response = await page.request.get(apiBase + `/api/admin/computers/${ids[model]}`);
      const computer = await response.json();
      assert.equal(computer.description, 'Contesto sintetico da conservare.');
      const spec = computer.configurations[0].specifications[0];
      if (model === 'KIM-1') { assert.equal(spec.numeric_value, 2); assert.equal(spec.unit, 'KiB'); }
      else { assert.equal(spec.numeric_value, null); assert.equal(spec.property_name, 'Annotazione sulla memoria'); }
    }
    for (const width of [320, 390]) {
      await page.setViewportSize({ width, height: 900 });
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `Overflow at ${width}px`);
    }
    assert.deepEqual(errors, []);
    console.log('Browser units: preview, model filter, original report download, documented correction, non-quantitative annotation, unknown model preserved, repeat and mobile pass.');
  } catch (error) {
    const dir = path.join('test-results', 'imports', 'units'); await fs.mkdir(dir, { recursive: true });
    await page.screenshot({ path: path.join(dir, 'failure.png'), fullPage: true });
    await fs.writeFile(path.join(dir, 'failure.txt'), String(error) + '\n' + await page.locator('body').innerText());
    throw error;
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
