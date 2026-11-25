/* Local synthetic fixtures only: self-citations and conditional RetroFlops use. */
const assert = require('node:assert/strict');
const { chromium } = require('playwright');

(async () => {
  const base = process.env.HHE_BASE_URL || 'http://127.0.0.1:18181/';
  assert(['127.0.0.1', 'localhost', '[::1]'].includes(new URL(base).hostname));
  const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || undefined,
    args: ['--no-sandbox', '--disable-dev-shm-usage'] });
  const page = await browser.newPage({ viewport: { width: 1280, height: 1000 } });
  const errors = []; page.on('pageerror', error => errors.push(error.message));
  const api = route => new URL('/api' + route, base).href;
  const computerIds = [];
  try {
    const suffix = Date.now();
    const meta = await (await page.request.get(api('/meta'))).json();
    const maker = meta.manufacturers[0];
    const post = async (route, data) => {
      const response = await page.request.post(api(route), { data });
      assert.equal(response.status(), 201, await response.text());
      return response.json();
    };
    const unused = await post('/sources', { title: 'RetroFlops — unused ' + suffix, url: 'https://retroflops.github.io/' });
    const used = await post('/sources', { title: 'RetroFlops — referenced ' + suffix, url: 'https://retroflops.github.io/' });
    const independent = await post('/sources', { title: 'Independent unused manual ' + suffix, url: 'https://example.org/manual' });
    const computer = await post('/computers', { model_name: 'SyntheticSources-' + suffix,
      manufacturer_id: maker.id, description: 'Synthetic reference fixture', source_ids: [used.id] });
    computerIds.push(computer.id);
    const hheTitle = 'HHE · Synthetic editorial summary ' + suffix;
    const upload = await page.request.post(api('/admin/imports/upload'), { multipart: {
      provider: 'manual', rights_confirmed: 'true', file: { name: 'synthetic-hhe.json', mimeType: 'application/json',
        buffer: Buffer.from(JSON.stringify([{ manufacturer: maker.name, model_name: 'SyntheticEditorial-' + suffix,
          description: 'Synthetic editorial description',
          source: { title: hheTitle, publisher: 'Hardware History Explorer', source_type: 'editorial_summary' }
        }])) }
    } });
    assert.equal(upload.status(), 201, await upload.text());
    const job = await upload.json();
    const applied = await page.request.post(api('/admin/imports/' + job.id + '/apply'));
    assert.equal(applied.status(), 200, await applied.text());
    const detail = await (await page.request.get(api('/admin/imports/' + job.id))).json();
    const editorialId = detail.rows[0].computer_id;
    assert(editorialId); computerIds.push(editorialId);
    assert.deepEqual(detail.verification_counts, {});
    assert.deepEqual(detail.rows[0].claims, []);
    assert.equal((await (await page.request.get(api('/computers/' + editorialId))).json()).description, 'Synthetic editorial description');
    const sourceIds = async () => (await (await page.request.get(api('/sources'))).json()).map(row => row.id);
    assert((await sourceIds()).includes(used.id));
    assert(!(await sourceIds()).includes(unused.id));
    assert((await sourceIds()).includes(independent.id));
    assert.equal((await page.request.get(api('/sources/' + unused.id))).status(), 404);
    const openSources = async () => {
      await page.goto(base);
      await page.getByRole('button', { name: 'Amministrazione', exact: true }).click();
      await page.getByRole('button', { name: 'Fonti', exact: true }).click();
      await page.getByRole('button', { name: 'Nuova fonte', exact: true }).waitFor();
      await page.getByText(independent.title, { exact: true }).waitFor();
    };
    await openSources();
    assert(await page.getByText(used.title, { exact: true }).isVisible());
    assert.equal(await page.getByText(unused.title, { exact: true }).count(), 0);
    assert.equal(await page.getByText(hheTitle, { exact: true }).count(), 0);
    const raw = await (await page.request.get(api('/admin/computers/' + computer.id))).json();
    const payload = { ...raw, source_ids: [] }; delete payload.id;
    let response = await page.request.put(api('/computers/' + computer.id), { data: payload });
    assert.equal(response.status(), 200, await response.text());
    assert(!(await sourceIds()).includes(used.id));
    assert.equal((await page.request.get(api('/sources/' + used.id))).status(), 404);
    await openSources();
    assert.equal(await page.getByText(used.title, { exact: true }).count(), 0);
    assert(await page.getByText(independent.title, { exact: true }).isVisible());
    response = await page.request.put(api('/computers/' + computer.id), { data: { ...payload, source_ids: [used.id] } });
    assert.equal(response.status(), 200, await response.text());
    assert((await sourceIds()).includes(used.id));
    await openSources();
    assert(await page.getByText(used.title, { exact: true }).isVisible());
    assert.deepEqual(errors, []);
    console.log('PASS source policy: HHE self-citations absent; unused RetroFlops hidden, referenced RetroFlops retained, unlink/relink updates panel; independent sources and model descriptions preserved.');
  } finally {
    for (const id of computerIds) await page.request.delete(api('/computers/' + id)).catch(() => {});
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
