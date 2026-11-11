import { test } from 'node:test';
import assert from 'node:assert/strict';
import { api, allComputers, latestRequest } from '../src/api.js';

const tick = () => new Promise(resolve => setImmediate(resolve));

test('obsolete search cannot overwrite a newer response even if abort is ignored', async () => {
  let oldResolve;
  const old = new Promise(resolve => { oldResolve = resolve; });
  const results = [];
  const errors = [];
  const cancel = latestRequest(() => old, value => results.push(value), error => errors.push(error));
  await tick();
  cancel();
  latestRequest(() => Promise.resolve('Apple'), value => results.push(value), error => errors.push(error));
  await tick();
  oldResolve('IBM');
  await tick();
  assert.deepEqual(results, ['Apple']);
  assert.deepEqual(errors, []);
});

test('unmount aborts transport and suppresses stale errors', async () => {
  let signal;
  const errors = [];
  const cancel = latestRequest(s => {
    signal = s;
    return new Promise((resolve, reject) => s.addEventListener('abort', () => reject(Error('cancelled'))));
  }, () => assert.fail('cancelled request completed'), e => errors.push(e));
  await tick();
  cancel();
  await tick();
  assert.equal(signal.aborted, true);
  assert.deepEqual(errors, []);
});

test('catalog loads all pages while preserving filters and signal', async t => {
  const signal = new AbortController().signal;
  const urls = [];
  t.mock.method(globalThis, 'fetch', async (url, options) => {
    assert.equal(options.signal, signal);
    urls.push(url);
    const offset = Number(new URL(url, 'http://localhost').searchParams.get('offset'));
    return Response.json({ total: 102, items: Array.from({ length: offset ? 2 : 100 }, (_, i) => ({ id: offset + i })) });
  });
  const rows = await allComputers(new URLSearchParams({ q: 'IBM' }), signal);
  assert.equal(rows.length, 102);
  assert.equal(rows[101].id, 101);
  assert.equal(urls.length, 2);
  assert.equal(new URL(urls[1], 'http://localhost').searchParams.get('q'), 'IBM');
});

test('multipart uploads let the browser set its boundary; 204 has no JSON body', async t => {
  const body = new FormData();
  t.mock.method(globalThis, 'fetch', async (url, options) => {
    assert.equal(options.body, body);
    assert.equal(options.headers['Content-Type'], undefined);
    return new Response(null, { status: 204 });
  });
  assert.equal(await api('/upload', { method: 'POST', body }), null);
});

test('validation errors explain rejected input', async t => {
  t.mock.method(globalThis, 'fetch', async () => Response.json({ detail: [{ msg: 'Year out of range' }] }, { status: 422 }));
  await assert.rejects(api('/computers?year_from=-1'), /Year out of range/);
});
