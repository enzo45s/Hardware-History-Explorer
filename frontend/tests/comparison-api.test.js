import { test } from 'node:test';
import assert from 'node:assert/strict';
import { comparisonSummary, comparisonSuggestions } from '../src/comparison-api.js';

test('suggestions request a bounded server search independent of catalog filters', async t => {
  const signal = new AbortController().signal;
  t.mock.method(globalThis, 'fetch', async (url, options) => {
    const parsed = new URL(url, 'http://localhost');
    assert.equal(parsed.pathname, '/api/computers/suggestions');
    assert.equal(parsed.searchParams.get('q'), 'IBM & PC');
    assert.equal(parsed.searchParams.get('limit'), '8');
    assert.deepEqual(parsed.searchParams.getAll('exclude_ids'), ['2', '4']);
    assert.equal(parsed.searchParams.has('category_id'), false);
    assert.equal(options.signal, signal);
    return Response.json({ items: [{ id: 8, model_name: 'IBM PC' }], has_more: true });
  });
  assert.deepEqual(await comparisonSuggestions('  IBM & PC  ', [2, 4], signal), { items: [{ id: 8, model_name: 'IBM PC' }], has_more: true });
});

test('selection keeps identifying labels without retaining the entire archived record', () => {
  const selected = comparisonSummary({ id: 5, model_name: 'Example', manufacturer: 'Maker', year: null, description: 'Long description', configurations: [{ specifications: [] }] });
  assert.deepEqual(selected, { id: 5, model_name: 'Example', manufacturer: 'Maker', year: null });
});
