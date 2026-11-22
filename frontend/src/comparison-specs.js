import { displaySpecification, displayConfigurations } from './catalog-display.js';
import { memorySpecifications, memoryText } from './ram-display.js';

// Missing values remain unknown; variants and units must never be silently merged.
export function selectedConfiguration(computer, requested) {
  if (requested == null || requested === 'all') return null;
  return displayConfigurations(computer).find(config => String(config.id) === String(requested)
    || config.configuration_ids?.some(id => String(id) === String(requested))) || null;
}

export function comparisonSpecifications(computer, requested = 'all') {
  const chosen = selectedConfiguration(computer, requested);
  const configurations = chosen ? [chosen] : displayConfigurations(computer);
  const groups = new Map();
  configurations.forEach((config, index) => {
    for (const original of memorySpecifications(config.specifications)) {
      const spec = displaySpecification(original);
      const numeric = spec.numeric_value != null;
      if (numeric && !Number.isFinite(spec.numeric_value)) continue;
      const raw = numeric ? spec.numeric_value : spec.text_value?.trim();
      if (raw == null || raw === '') continue;
      const unit = spec.unit?.trim() || '';
      const key = JSON.stringify([spec.component_type, spec.property_name]);
      if (!groups.has(key)) groups.set(key, { key, label: spec.component_type === 'RAM' && spec.property_name === 'Capacità' ? 'RAM' : spec.component_type + ' · ' + spec.property_name, values: new Map(), coverage: new Set(), notes: new Set() });
      const group = groups.get(key);
      if (original.memory_values) {
        group.memory = true;
        for (const value of original.memory_values) group.values.set(value.identity, value);
        for (const note of original.memory_notes) group.notes.add(note);
        if (original.memory_values.length) group.coverage.add(index);
        continue;
      }
      group.values.set(JSON.stringify([String(raw), unit]), { raw, numeric, unit });
      group.coverage.add(index);
    }
  });
  return new Map([...groups].map(([key, group]) => {
    if (group.memory) return [key, { label: group.label, text: memoryText([...group.values.values()]) || 'Non documentata',
      notes: [...group.notes], coverage: group.coverage.size, total: configurations.length, partial: group.coverage.size > 0 && group.coverage.size < configurations.length }];
    const values = [...group.values.values()].sort((a, b) => a.numeric && b.numeric && a.unit === b.unit
      ? a.raw - b.raw : (String(a.raw) + ' ' + a.unit).localeCompare(String(b.raw) + ' ' + b.unit, 'it', { numeric: true }));
    const oneUnit = new Set(values.map(value => value.unit)).size === 1;
    const text = oneUnit
      ? values.map(value => value.raw).join(' / ') + (values[0].unit ? ' ' + values[0].unit : '')
      : values.map(value => String(value.raw) + (value.unit ? ' ' + value.unit : '')).join(' / ');
    return [key, { label: group.label, text, coverage: group.coverage.size, total: configurations.length, partial: group.coverage.size < configurations.length }];
  }));
}

export function comparisonRows(comparisons) {
  const rows = [...new Map(comparisons.flatMap(specs => [...specs].map(([key, spec]) => [key, spec.label])))];
  const main = JSON.stringify(['RAM', 'Capacità']), options = JSON.stringify(['RAM', 'Opzioni di memoria']);
  const extra = rows.find(([key]) => key === options);
  if (!extra || !rows.some(([key]) => key === main)) return rows;
  const ordered = rows.filter(([key]) => key !== options);
  ordered.splice(ordered.findIndex(([key]) => key === main) + 1, 0, extra);
  return ordered;
}
