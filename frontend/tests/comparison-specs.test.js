import { test } from 'node:test';
import assert from 'node:assert/strict';
import { comparisonSpecifications, selectedConfiguration } from '../src/comparison-specs.js';

const spec = (component, property, numeric, text = null, unit = null) => ({ component_type: component, property_name: property, numeric_value: numeric, text_value: text, unit });
const key = (component, property) => JSON.stringify([component, property]);

test('backend normalized views align legacy labels and equivalent units without mutating raw data', () => {
  const computer = { configurations: [{ id: 1, specifications: [
    { ...spec('main-cpu', 'clock-frequency', 1000000, null, 'Hz'), normalized: spec('CPU', 'Frequenza', 1, null, 'MHz') },
    spec('CPU', 'Frequenza', 1, null, 'MHz')
  ] }] };
  const before = JSON.stringify(computer);
  const result = comparisonSpecifications(computer);
  assert.equal(result.size, 1);
  assert.equal(result.get(key('CPU', 'Frequenza')).text, '1 MHz');
  assert.equal(JSON.stringify(computer), before);
});
const family = {
  configurations: [48, 4, 8, 12, 16, 20, 24, 32, 36].map((ram, index) => ({
    id: index + 1, variant_name: `RAM ${ram} KB`, specifications: [spec('RAM', 'Capacità', ram, null, 'KB'), spec('CPU', 'Modello', null, 'MOS 6502')]
  }))
};

test('all configurations retain every distinct RAM value, sorted numerically, with a common unit once', () => {
  const before = JSON.stringify(family);
  const result = comparisonSpecifications(family);
  assert.equal(result.get(key('RAM', 'Capacità')).text, '4 / 8 / 12 / 16 / 20 / 24 / 32 / 36 / 48 KB');
  assert.equal(result.get(key('CPU', 'Modello')).text, 'MOS 6502');
  assert.equal(result.get(key('RAM', 'Capacità')).partial, false);
  assert.equal(JSON.stringify(family), before);
});

test('an explicit configuration uses only its own specifications', () => {
  const result = comparisonSpecifications(family, '2');
  assert.equal(selectedConfiguration(family, '2').variant_name, 'RAM 4 KB');
  assert.equal(result.get(key('RAM', 'Capacità')).text, '4 KB');
  assert.equal(result.get(key('RAM', 'Capacità')).total, 1);
  assert.equal(result.get(key('CPU', 'Modello')).partial, false);
});

test('missing properties are marked partial and never inherited into another variant', () => {
  const computer = { configurations: [
    { id: 1, specifications: [spec('RAM', 'Capacità', 0, null, 'KB'), spec('CPU', 'Modello', null, '6502')] },
    { id: 2, specifications: [spec('RAM', 'Capacità', 8, null, 'KB')] },
    { id: 3, specifications: [] }
  ] };
  const result = comparisonSpecifications(computer);
  assert.equal(result.get(key('RAM', 'Capacità')).text, '0 / 8 KB');
  assert.equal(result.get(key('RAM', 'Capacità')).coverage, 2);
  assert.equal(result.get(key('RAM', 'Capacità')).total, 3);
  assert.equal(result.get(key('CPU', 'Modello')).coverage, 1);
  assert.equal(comparisonSpecifications(computer, '2').has(key('CPU', 'Modello')), false);
  assert.equal(comparisonSpecifications(computer, '3').size, 0);
});

test('mixed units are kept explicit without conversions or false deduplication', () => {
  const computer = { configurations: [
    { id: 1, specifications: [spec('RAM', 'Capacità', 1, null, 'MB')] },
    { id: 2, specifications: [spec('RAM', 'Capacità', 1024, null, 'KB')] },
    { id: 3, specifications: [spec('RAM', 'Capacità', 1, null, 'MB')] }
  ] };
  assert.equal(comparisonSpecifications(computer).get(key('RAM', 'Capacità')).text, '1 MB / 1024 KB');
});

test('deleted or invalid choices fall back to all; computers without configurations remain empty', () => {
  assert.equal(selectedConfiguration(family, 'all'), null);
  assert.equal(selectedConfiguration(family, 'missing'), null);
  assert.equal(comparisonSpecifications(family, 'missing').get(key('RAM', 'Capacità')).coverage, 9);
  assert.equal(comparisonSpecifications({ configurations: [] }).size, 0);
});

test('repeated properties inside one configuration do not overwrite values or inflate coverage', () => {
  const computer = { configurations: [{ id: 1, specifications: [
    spec('Storage', 'Capacità', 10, null, 'GB'), spec('Storage', 'Capacità', 20, null, 'GB'),
    spec('Storage', 'Capacità', 10, null, 'GB'), spec('CPU', 'Modello', null, '  ')
  ] }] };
  const value = comparisonSpecifications(computer).get(key('Storage', 'Capacità'));
  assert.equal(value.text, '10 / 20 GB');
  assert.equal(value.coverage, 1);
  assert.equal(value.partial, false);
});
