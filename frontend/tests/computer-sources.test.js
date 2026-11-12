import test from 'node:test';
import assert from 'node:assert/strict';
import { computerSources } from '../src/computer-sources.js';

test('bibliography includes scoped technical and historical citations once, without claiming verification', () => {
  const root = { id: 1, title: 'Root' }, technical = { id: 2, title: 'Technical document' }, release = { id: 3, title: 'Price document' };
  const computer = { sources: [root], configurations: [{ specifications: [{ sources: [technical, root] }, { sources: [technical] }] }],
    releases: [{ sources: [release] }], sales: [{ sources: [root] }], reviews: [], facts: [] };
  assert.deepEqual(computerSources(computer), [root, technical, release]);
  assert.deepEqual(computerSources({}), []);
  assert.equal('verification_status' in technical, false);
});
