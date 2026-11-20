/* Synthetic records on a disposable local Compose project; no external requests. */
const assert = require('node:assert/strict');
const { chromium } = require('playwright');
(async () => {
  const base = process.env.HHE_BASE_URL || 'http://127.0.0.1:8080/';
  assert(['127.0.0.1', 'localhost'].includes(new URL(base).hostname));
  const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || undefined, args: ['--no-sandbox', '--disable-dev-shm-usage'] });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  const errors = [], ids = [];
  let maker;
  page.on('pageerror', e => errors.push(e.message));
  async function get(path) { const r = await page.request.get(new URL('api/' + path, base).href); assert(r.ok(), await r.text()); return r.json(); }
  async function post(path, data) { const r = await page.request.post(new URL('api/' + path, base).href, { data }); assert(r.ok(), await r.text()); return r.json(); }
  try {
    let meta = await get('meta');
    const generic = meta.categories.find(c => c.name === 'Calcolatore') || await post('categories', { name: 'Calcolatore' });
    const portable = meta.categories.find(c => c.name === 'Portable');
    const name = `Category fixture ${Date.now()}`;
    maker = await post('manufacturers', { name });
    for (const [suffix, categories, description] of [
      ['Work', [generic.id], 'workstation progettata per la grafica.'],
      ['Manual', [generic.id, portable.id], 'personal computer documentato.'],
      ['Unknown', [generic.id], 'sistema senza una tipologia esplicita.'],
    ]) {
      const model = name + ' ' + suffix;
      const c = await post('computers', { manufacturer_id: maker.id, model_name: model, category_ids: categories,
        description: `${model} è una ${description}`, configurations: [{ variant_name: 'Base', specifications: [{ component_type: 'RAM', property_name: 'Capacità', numeric_value: 16, unit: 'KB' }] }] });
      ids.push(c.id);
    }
    const before = await get('computers/' + ids[0]);
    await page.goto(base);
    await page.getByRole('button', { name: 'Amministrazione', exact: true }).click();
    await page.getByRole('button', { name: 'Categorie', exact: true }).click();
    await page.getByRole('region', { name: 'Riepilogo categorie', exact: true }).waitFor();
    await page.getByLabel('Filtra i sistemi da classificare', { exact: true }).fill(name);
    await page.getByText(`${name} · ${name} Work → Workstation`, { exact: true }).waitFor();
    await page.getByRole('button', { name: 'Applica la classificazione al catalogo', exact: true }).click();
    await page.waitForFunction(() => document.querySelector('.classification-panel button[disabled]') === null || document.querySelector('.classification-panel [role="status"]'));
    await page.getByRole('button', { name: 'Aggiorna analisi categorie', exact: true }).waitFor({ state: 'visible' });
    await page.waitForFunction(() => ![...document.querySelectorAll('button')].find(b => b.textContent === 'Aggiorna analisi categorie')?.disabled);
    const after = await get('computers/' + ids[0]);
    assert.deepEqual(after.categories, ['Workstation']);
    assert.deepEqual(after.configurations, before.configurations);
    assert.equal(after.description, before.description);
    assert.deepEqual((await get('computers/' + ids[1])).categories, ['Portable']);
    assert.deepEqual((await get('computers/' + ids[2])).categories, ['Calcolatore']);
    const remaining = page.getByRole('region', { name: 'Sistemi da esaminare', exact: true });
    await remaining.getByRole('button', { name: 'Modifica categorie · ' + name + ' Unknown', exact: true }).waitFor();
    for (const width of [320, 390]) {
      await page.setViewportSize({ width, height: 900 });
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    }
    await remaining.getByRole('button', { name: 'Modifica categorie · ' + name + ' Unknown', exact: true }).click();
    const choices = page.getByRole('group', { name: 'Categorie', exact: true });
    await choices.getByLabel('Calcolatore', { exact: true }).uncheck();
    await choices.getByLabel('Home computer', { exact: true }).check();
    await page.getByRole('button', { name: 'Salva calcolatore', exact: true }).click();
    await page.getByRole('status').filter({ hasText: 'Calcolatore salvato.' }).waitFor();
    assert.deepEqual((await get('computers/' + ids[2])).categories, ['Home computer']);
    meta = await get('meta');
    const categoryId = meta.categories.find(c => c.name === 'Workstation').id;
    const filtered = await get(`computers?category_id=${categoryId}&q=${encodeURIComponent(name)}`);
    assert.deepEqual(filtered.items.map(c => c.id), [ids[0]]);
    assert.deepEqual(errors, []);
    console.log('PASS categories browser: explicit role, generic cleanup, preserved manual category/specs, review editor, working category filter and mobile.');
  } finally {
    for (const id of ids) await page.request.delete(new URL('api/computers/' + id, base).href);
    if (maker) await page.request.delete(new URL('api/manufacturers/' + maker.id, base).href);
    await browser.close();
  }
})().catch(e => { console.error(e); process.exitCode = 1; });
