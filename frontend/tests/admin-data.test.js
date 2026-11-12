import { test } from 'node:test';
import assert from 'node:assert/strict';
import { computerDraft, computerPayload, newComputer, sourcePayload } from '../src/admin-data.js';

test('editing preserves nested IDs, precision, zero values and source associations', () => {
  const dto = {
    id: 20, model_name: 'Example', manufacturer_id: 1, description: 'Saved', announcement_date: '1981-09',
    category_ids: [1, 2], source_ids: [3],
    releases: [{ id: 4, market_id: 2, release_date: '1982', discontinuation_date: null, price: 0, currency: 'USD', price_type: 'launch', source_ids: [3] }],
    configurations: [{ id: 5, variant_name: 'Base', description: null, specifications: [{
      id: 6, component_type: 'RAM', component_name: null, property_name: 'KB', numeric_value: 0, text_value: null, unit: 'KB', source_ids: [3]
    }] }]
  };
  const sent = computerPayload(computerDraft(dto));
  assert.equal(sent.id, undefined);
  assert.equal(sent.announcement_date, '1981-09');
  assert.equal(sent.releases[0].price, 0);
  assert.equal(sent.releases[0].id, 4);
  assert.equal(sent.configurations[0].specifications[0].numeric_value, 0);
  assert.equal(sent.configurations[0].specifications[0].id, 6);
  assert.deepEqual(sent.configurations[0].specifications[0].source_ids, [3]);
  assert.equal(sent.configurations[0].specifications[0].value_kind, undefined);
  assert.equal(dto.configurations[0].specifications[0].value_kind, undefined);
});

test('changing a specification value type clears the inactive value', () => {
  const draft = newComputer();
  draft.manufacturer_id = '2'; draft.model_name = '  Demo  ';
  draft.configurations = [{ variant_name: 'Base', specifications: [{
    component_type: 'CPU', property_name: 'Model', value_kind: 'text', text_value: '6502', numeric_value: 0
  }] }];
  const value = computerPayload(draft);
  assert.equal(value.manufacturer_id, 2);
  assert.equal(value.model_name, 'Demo');
  assert.equal(value.announcement_date, null);
  assert.equal(value.configurations[0].specifications[0].numeric_value, null);
  assert.equal(value.configurations[0].specifications[0].text_value, '6502');
  draft.configurations[0].specifications[0].value_kind = 'number';
  draft.configurations[0].specifications[0].numeric_value = '';
  assert.throws(() => computerPayload(draft), /valore numerico/);
});

test('source payload excludes server fields and keeps optional dates unknown', () => {
  const value = sourcePayload({ id: 8, title: ' Manuale ', source_type: 'book', author: 'Ada', publisher: '', url: '', publication_date: '', access_date: '2026-11-11' });
  assert.equal(value.id, undefined);
  assert.equal(value.title, 'Manuale');
  assert.equal(value.url, null);
  assert.equal(value.publication_date, null);
  assert.equal(value.access_date, '2026-11-11');
});
