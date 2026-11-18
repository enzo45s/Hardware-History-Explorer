import test from 'node:test';
import assert from 'node:assert/strict';
import { releaseGroups } from '../src/release-groups.js';
import { displayConfigurations } from '../src/catalog-display.js';
import { comparisonSpecifications, selectedConfiguration } from '../src/comparison-specs.js';

test('Europe has one panel while distinct offers and other regions retain their rows', () => {
  const releases = [{ id: 1, market: 'Europa', price: 100, currency: 'EUR' },
    { id: 2, market: 'USA', price: 100, currency: 'USD' },
    { id: 3, market: 'Europa', price: 200, currency: 'GBP' }, { id: 4, market: 'Japan' }];
  const before = structuredClone(releases);
  const groups = releaseGroups(releases);
  assert.equal(groups.length, 3);
  assert.deepEqual(groups[0].releases, [releases[0], releases[2]]);
  assert.deepEqual(groups.slice(1).map(group => group.market), ['USA', 'Japan']);
  assert.deepEqual(releases, before);
});

test('comparison uses consolidated profiles and preserves selections of old regional IDs', () => {
  const spec = { component_type: 'RAM', property_name: 'Capacità', numeric_value: 64, unit: 'KiB' };
  const computer = { configurations: [{ id: 1 }, { id: 2 }, { id: 3 }], display_configurations: [
    { id: 1, configuration_ids: [1, 2], display_name: 'Europa', specifications: [spec] },
    { id: 3, configuration_ids: [3], display_name: 'USA', specifications: [] }
  ] };
  assert.equal(displayConfigurations(computer).length, 2);
  assert.equal(selectedConfiguration(computer, '2').display_name, 'Europa');
  assert.equal(selectedConfiguration(computer, '999'), null);
  const key = JSON.stringify(['RAM', 'Capacità']);
  assert.equal(comparisonSpecifications(computer, '2').get(key).text, '64 KiB');
  assert.equal(comparisonSpecifications(computer).get(key).total, 2);
  assert.equal(comparisonSpecifications(computer).get(key).coverage, 1);
  assert.deepEqual(displayConfigurations({ configurations: [] }), []);
});
