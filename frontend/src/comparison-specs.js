// Missing values remain unknown; variants and units must never be silently merged.
export function selectedConfiguration(computer, requested) {
  if (requested == null || requested === 'all') return null;
  return computer.configurations.find(config => String(config.id) === String(requested)) || null;
}

export function comparisonSpecifications(computer, requested = 'all') {
  const chosen = selectedConfiguration(computer, requested);
  const configurations = chosen ? [chosen] : computer.configurations;
  const groups = new Map();
  configurations.forEach((config, index) => {
    for (const spec of config.specifications) {
      const numeric = spec.numeric_value != null;
      if (numeric && !Number.isFinite(spec.numeric_value)) continue;
      const raw = numeric ? spec.numeric_value : spec.text_value?.trim();
      if (raw == null || raw === '') continue;
      const unit = spec.unit?.trim() || '';
      const key = JSON.stringify([spec.component_type, spec.property_name]);
      if (!groups.has(key)) groups.set(key, { key, label: spec.component_type + ' · ' + spec.property_name, values: new Map(), coverage: new Set() });
      const group = groups.get(key);
      group.values.set(JSON.stringify([String(raw), unit]), { raw, numeric, unit });
      group.coverage.add(index);
    }
  });
  return new Map([...groups].map(([key, group]) => {
    const values = [...group.values.values()].sort((a, b) => a.numeric && b.numeric && a.unit === b.unit
      ? a.raw - b.raw : (String(a.raw) + ' ' + a.unit).localeCompare(String(b.raw) + ' ' + b.unit, 'it', { numeric: true }));
    const oneUnit = new Set(values.map(value => value.unit)).size === 1;
    const text = oneUnit
      ? values.map(value => value.raw).join(' / ') + (values[0].unit ? ' ' + values[0].unit : '')
      : values.map(value => String(value.raw) + (value.unit ? ' ' + value.unit : '')).join(' / ');
    return [key, { label: group.label, text, coverage: group.coverage.size, total: configurations.length, partial: group.coverage.size < configurations.length }];
  }));
}
