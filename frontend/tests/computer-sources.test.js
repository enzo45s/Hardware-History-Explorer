import test from 'node:test';
import assert from 'node:assert/strict';
import { computerSources, commercializationSource } from '../src/computer-sources.js';

test('bibliography includes scoped technical and historical citations once, without claiming verification', () => {
  const root = { id: 1, title: 'Root' }, technical = { id: 2, title: 'Technical document' }, release = { id: 3, title: 'Price document' };
  const computer = { sources: [root], configurations: [{ specifications: [{ sources: [technical, root] }, { sources: [technical] }] }],
    releases: [{ sources: [release] }], sales: [{ sources: [root] }], reviews: [], facts: [] };
  assert.deepEqual(computerSources(computer), [root, technical, release]);
  assert.deepEqual(computerSources({}), []);
  assert.equal('verification_status' in technical, false);
});

test('commercialization uses one price citation even when the date citation is first', () => {
  const dated = { id: 1, title: 'Date', url: 'https://example.org/date' };
  const priced = { id: 2, title: 'Price', url: 'https://example.org/price' };
  assert.equal(commercializationSource({ price: 3298, sources: [dated, priced], field_sources: { price: [2], release_date: [1] } }), priced);
  assert.equal(commercializationSource({ price: 0, sources: [dated, priced], field_sources: { price: [2] } }), priced);
  assert.equal(commercializationSource({ sources: [priced, dated], field_sources: { release_date: [1] } }), dated);
  assert.equal(commercializationSource({ price: 100, sources: [dated] }), dated);
  assert.equal(commercializationSource({ sources: [{ id: 3, title: 'Without URL' }, dated] }), dated);
  assert.equal(commercializationSource({ sources: [] }), null);
  assert.equal(commercializationSource({}), null);
});
