import test from 'node:test';
import assert from 'node:assert/strict';
import { memorySpecifications } from '../src/ram-display.js';
import { comparisonSpecifications, comparisonRows } from '../src/comparison-specs.js';
const key = prop => JSON.stringify(['RAM', prop]);
const spec = (id, property, value, unit = null, role = null) => ({ id, component_type: 'RAM', component_name: role,
  property_name: property, numeric_value: typeof value === 'number' ? value : null,
  text_value: typeof value === 'string' ? value : null, unit, sources: [{ id, title: `Documento ${id}` }] });
const compare = specs => comparisonSpecifications({ configurations: [{ id: 1, specifications: specs }] });

test('installed, reported and reference values share one RAM field and preserve every citation', () => {
  const original = [spec(1, 'Capacità', 4096, 'KiB'), spec(2, 'Capacità riportata', '4 MiB'), spec(3, 'Capacità di riferimento', 4, 'MiB'), spec(4, 'Opzioni di memoria', 4096, 'KiB')];
  const before = structuredClone(original), rows = memorySpecifications(original);
  assert.equal(rows.length, 1); assert.equal(rows[0].text_value, '4 MB');
  assert.deepEqual(rows[0].specification_ids, [1, 2, 3, 4]);
  assert.deepEqual(rows[0].sources.map(source => source.id), [1, 2, 3, 4]);
  assert.deepEqual(original, before); assert.equal(compare(original).size, 1);
});

test('limits and expansion choices share one optional row, without turning a maximum into installed RAM', () => {
  const rows = compare([spec(1, 'Capacità riportata', 16, 'KiB'), spec(2, 'Capacità massima riportata', 64, 'KiB'), spec(3, 'Capacità minima riportata', 8, 'KiB'), spec(4, 'Opzioni di memoria', '16 / 32 / 64 KiB')]);
  assert.equal(rows.size, 2); assert.equal(rows.get(key('Capacità')).label, 'RAM');
  assert.equal(rows.get(key('Capacità')).text, '16 KB');
  assert.match(rows.get(key('Opzioni di memoria')).text, /Massima: 64 KB/);
  assert.match(rows.get(key('Opzioni di memoria')).text, /Minima: 8 KB/);
  assert.match(rows.get(key('Opzioni di memoria')).text, /16 \/ 32 \/ 64 KB/);
  const maximum = compare([spec(1, 'Limite hardware riportato', 64, 'KiB')]);
  assert.equal(maximum.get(key('Capacità')).text, 'Non documentata');
  assert.equal(maximum.get(key('Capacità')).coverage, 0);
  assert.equal(maximum.get(key('Opzioni di memoria')).text, 'Massima: 64 KB');
});

test('reference values are a qualified fallback, never a fabricated expansion option', () => {
  const reference = compare([spec(1, 'Capacità di riferimento', 128, 'KiB')]);
  assert.equal(reference.size, 1); assert.equal(reference.get(key('Capacità')).text, '128 KB');
  assert.match(reference.get(key('Capacità')).notes.join(' '), /dotazione di base non documentata/);
  const reported = compare([spec(1, 'Capacità riportata', 64, 'KiB'), spec(2, 'Capacità di riferimento', 128, 'KiB')]);
  assert.equal(reported.size, 1); assert.equal(reported.get(key('Capacità')).text, '64 KB');
  assert.match(reported.get(key('Capacità')).notes.join(' '), /riferimento: 128 KB/);
  assert.equal(reported.has(key('Opzioni di memoria')), false);
});

test('real conflicts remain in the same RAM field with both citations', () => {
  const [row] = memorySpecifications([spec(1, 'Capacità', 16, 'KiB'), spec(2, 'Capacità riportata', 32, 'KiB')]);
  assert.equal(row.text_value, '16 / 32 KB'); assert.match(row.memory_notes.join(' '), /Quantità diverse/);
  assert.deepEqual(row.sources.map(source => source.id), [1, 2]);
});

test('ranges, explicit reference endpoints and video memory retain their original scope', () => {
  const rows = compare([spec(1, 'Capacità riportata', '16 - 48 KiB'), spec(2, 'Capacità di riferimento', 48, 'KiB')]);
  assert.equal(rows.size, 1); assert.equal(rows.get(key('Capacità')).text, '16 - 48 KB');
  assert.deepEqual(rows.get(key('Capacità')).notes, []);
  assert.equal(compare([spec(1, 'Capacità riportata', '64 KiB RAM + 16 KiB VRAM')]).get(key('Capacità')).text, '64 KB RAM + 16 KB VRAM');
});

test('named banks and VRAM are not summed or silently deduplicated', () => {
  const rows = compare([spec(1, 'Capacità', 16, 'KiB', 'Banco A'), spec(2, 'Capacità', 16, 'KiB', 'Banco B'), spec(3, 'Capacità', 4, 'KiB', 'VRAM')]);
  assert.equal(rows.size, 1); assert.equal(rows.get(key('Capacità')).text, 'Banco A: 16 KB; Banco B: 16 KB; VRAM: 4 KB');
  assert.deepEqual(rows.get(key('Capacità')).notes, []);
});

test('memory annotations and attributes remain sourced notes, and other hardware stays untouched', () => {
  const original = [spec(1, 'Annotazione sulla memoria', 'Capacità non quantificabile.'), spec(2, 'Tipo', 'DRAM'),
    { id: 10, component_type: 'ROM', property_name: 'Capacità', numeric_value: 32, unit: 'KiB' }];
  const before = structuredClone(original), rows = memorySpecifications(original);
  assert.equal(rows.length, 2); assert.equal(rows[0].text_value, 'Non documentata');
  assert.match(rows[0].memory_notes.join(' '), /Capacità non quantificabile/);
  assert.match(rows[0].memory_notes.join(' '), /Tipo: DRAM/);
  assert.deepEqual(rows[0].specification_ids, [1, 2]);
  assert.deepEqual(rows[1], original[2]); assert.deepEqual(original, before);
});

test('bits, legacy KB and native words stay distinct from exact IEC byte quantities', () => {
  const rows = compare([spec(1, 'Capacità', 64, 'KiB'), spec(2, 'Capacità riportata', 64, 'KB'), spec(3, 'Capacità riportata', 64, 'Kb'), spec(4, 'Capacità riportata', '1024 parole')]);
  const text = rows.get(key('Capacità')).text;
  assert.match(text, /64 KB \(unità originale\)/); assert.match(text, /64 Kb/); assert.match(text, /1024 parole/);
  assert.equal(memorySpecifications([spec(1, 'Capacità', 1.125, 'KiB')])[0].text_value, '1152 B');
});

test('source-specific capacity labels align across different systems', () => {
  for (const property of ['Capacità', 'Capacità riportata', 'Capacità di riferimento', 'Dotazioni riportate']) {
    const rows = compare([spec(1, property, 64, 'KiB')]);
    assert.equal(rows.size, 1); assert.equal(rows.get(key('Capacità')).text, '64 KB');
  }
});

test('explicit option lists use readable common units and retain the base among the available choices', () => {
  const rows = compare([spec(1, 'Capacità', 4096, 'KiB'), spec(2, 'Opzioni di memoria', '4096 KiB / 8192 KiB / 16384 KiB')]);
  assert.equal(rows.get(key('Capacità')).text, '4 MB');
  assert.equal(rows.get(key('Opzioni di memoria')).text, '4 / 8 / 16 MB');
});

test('RAM options stay next to RAM even when supplied only by a later comparison column', () => {
  const first = compare([spec(1, 'Capacità', 64, 'KiB'), { component_type: 'CPU', property_name: 'Modello', text_value: 'CPU A' }]);
  const second = compare([spec(2, 'Capacità', 64, 'KiB'), spec(3, 'Capacità massima riportata', 128, 'KiB')]);
  assert.deepEqual(comparisonRows([first, second]).map(([id]) => id), [key('Capacità'), key('Opzioni di memoria'), JSON.stringify(['CPU', 'Modello'])]);
  assert.deepEqual(comparisonRows([]), []);
});
