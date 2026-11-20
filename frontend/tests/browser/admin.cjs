/* Uses and deletes only its own synthetic records. Run against an isolated local instance. */
const assert = require('node:assert/strict');
const { chromium } = require('playwright');

(async () => {
  const base = process.env.HHE_BASE_URL || 'http://127.0.0.1:18081/';
  assert(['127.0.0.1', 'localhost', '[::1]'].includes(new URL(base).hostname));
  const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROMIUM_PATH || undefined,
    args: ['--no-sandbox', '--disable-dev-shm-usage'] });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  const errors = []; page.on('pageerror', error => errors.push(error.message));
  const api = path => new URL('/api' + path, base).href;
  const suffix = Date.now();
  const initialName = `Synthetic manufacturer ${suffix}`;
  const makerName = `Synthetic systems ${suffix}`;
  const model = `SyntheticAdmin-${suffix}`;
  const computerIds = [];
  let manufacturerId;
  const confirm = async (button, accepted) => {
    page.once('dialog', dialog => accepted ? dialog.accept() : dialog.dismiss());
    await button.click();
  };
  try {
    await page.goto(base, { waitUntil: 'domcontentloaded' });
    const baseline = (await (await page.request.get(api('/computers'))).json()).total;
    await page.getByRole('button', { name: 'Amministrazione', exact: true }).click();
    await page.getByRole('button', { name: 'Produttori', exact: true }).click();
    await page.getByRole('button', { name: 'Nuovo produttore', exact: true }).click();
    await page.getByLabel('Nome del produttore', { exact: true }).fill(initialName);
    await page.getByLabel('Paese', { exact: true }).fill('Italia');
    await page.getByLabel('Data di fondazione', { exact: true }).fill('1980-02-03');
    await page.getByLabel('Sito web', { exact: true }).fill('https://example.org');
    await page.getByRole('button', { name: 'Salva produttore', exact: true }).click();
    await page.getByText('Produttore salvato.', { exact: true }).waitFor();
    const makers = await (await page.request.get(api('/manufacturers'))).json();
    manufacturerId = makers.find(maker => maker.name === initialName).id;
    await page.getByLabel('Nome del produttore', { exact: true }).fill('ibm');
    await page.getByRole('button', { name: 'Salva produttore', exact: true }).click();
    await page.getByRole('alert').filter({ hasText: 'già presente' }).waitFor();
    assert.equal((await (await page.request.get(api('/manufacturers/' + manufacturerId))).json()).name, initialName);
    await page.getByLabel('Nome del produttore', { exact: true }).fill(makerName);
    await page.getByRole('button', { name: 'Salva produttore', exact: true }).click();
    await page.getByText('Produttore salvato.', { exact: true }).waitFor();
    assert.equal((await (await page.request.get(api('/manufacturers/' + manufacturerId))).json()).founded, '1980-02-03');
    await page.getByRole('button', { name: 'Calcolatori', exact: true }).click();
    await page.getByRole('button', { name: 'Nuovo calcolatore', exact: true }).click();
    await page.getByLabel('Nome del modello', { exact: true }).fill(model + '-A');
    await page.getByLabel('Produttore', { exact: true }).selectOption(String(manufacturerId));
    await page.getByRole('button', { name: 'Salva calcolatore', exact: true }).click();
    await page.getByText('Calcolatore salvato.', { exact: true }).waitFor();
    const created = (await (await page.request.get(api('/computers?q=' + model))).json()).items[0];
    computerIds.push(created.id);
    const extra = await page.request.post(api('/computers'), { data: { model_name: model + '-B', manufacturer_id: manufacturerId } });
    assert.equal(extra.status(), 201); computerIds.push((await extra.json()).id);
    await page.getByRole('button', { name: 'Produttori', exact: true }).click();
    await page.getByLabel('Cerca produttori', { exact: true }).fill(makerName);
    await page.locator('.admin-records button').filter({ hasText: makerName }).click();
    assert.equal(await page.getByRole('button', { name: 'Elimina produttore', exact: true }).isEnabled(), false);
    assert.match(await page.locator('.admin-editor').innerText(), /riassegna prima/);
    for (const width of [320, 390]) {
      await page.setViewportSize({ width, height: 900 });
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), 'Admin controls must fit mobile.');
    }
    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.getByRole('button', { name: 'Catalogo', exact: true }).click();
    await page.getByPlaceholder('Cerca un sistema…', { exact: true }).fill(model);
    await page.locator('.catalog-card').filter({ hasText: model + '-A' }).getByRole('button', { name: '+ Confronta', exact: true }).click();
    await page.locator('.catalog-card').filter({ hasText: model + '-B' }).getByRole('button', { name: '+ Confronta', exact: true }).click();
    await page.getByRole('button', { name: 'Amministrazione', exact: true }).click();
    await page.getByLabel('Cerca calcolatori', { exact: true }).fill(model + '-A');
    await page.locator('.admin-records button').filter({ hasText: model + '-A' }).click();
    await confirm(page.getByRole('button', { name: 'Elimina calcolatore', exact: true }), false);
    assert.equal((await page.request.get(api('/computers/' + computerIds[0]))).status(), 200);
    await confirm(page.getByRole('button', { name: 'Elimina calcolatore', exact: true }), true);
    await page.getByText('Calcolatore eliminato dal catalogo.', { exact: true }).waitFor();
    assert.equal((await page.request.get(api('/computers/' + computerIds[0]))).status(), 404);
    await page.locator('nav').getByRole('button', { name: /^Confronta/ }).click();
    await page.getByText('Aggiungi un altro sistema per visualizzare il confronto.', { exact: true }).waitFor();
    assert.equal(await page.getByText(model + '-A', { exact: true }).count(), 0);
    assert.equal(await page.getByText(model + '-B', { exact: true }).count(), 1);
    await page.getByRole('button', { name: 'Amministrazione', exact: true }).click();
    await page.getByLabel('Cerca calcolatori', { exact: true }).fill(model + '-B');
    await page.locator('.admin-records button').filter({ hasText: model + '-B' }).click();
    await confirm(page.getByRole('button', { name: 'Elimina calcolatore', exact: true }), true);
    await page.getByText('Calcolatore eliminato dal catalogo.', { exact: true }).waitFor();
    await page.getByRole('button', { name: 'Produttori', exact: true }).click();
    await page.getByLabel('Cerca produttori', { exact: true }).fill(makerName);
    await page.locator('.admin-records button').filter({ hasText: makerName }).click();
    await confirm(page.getByRole('button', { name: 'Elimina produttore', exact: true }), false);
    assert.equal((await page.request.get(api('/manufacturers/' + manufacturerId))).status(), 200);
    await confirm(page.getByRole('button', { name: 'Elimina produttore', exact: true }), true);
    await page.getByText('Produttore eliminato.', { exact: true }).waitFor();
    assert.equal((await page.request.get(api('/manufacturers/' + manufacturerId))).status(), 404);
    assert.equal((await (await page.request.get(api('/computers'))).json()).total, baseline);
    await page.reload();
    assert.equal((await page.request.get(api('/manufacturers/' + manufacturerId))).status(), 404);
    assert.deepEqual(errors, []);
    console.log('PASS browser: manufacturer create/edit/duplicate protection/counts/delete, linked maker protection, computer create/delete/cancel, comparison selection cleanup, persistence and mobile layout.');
  } finally {
    for (const id of computerIds) await page.request.delete(api('/computers/' + id)).catch(() => {});
    if (manufacturerId) await page.request.delete(api('/manufacturers/' + manufacturerId)).catch(() => {});
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
