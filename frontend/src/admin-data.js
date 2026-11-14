const optional = value => typeof value === 'string' ? value.trim() || null : value ?? null;

// Edit readable labels, but an unrelated save must not rename import keys or
// overwrite original descriptions. Deliberate operator edits still take effect.
function readable(entity, fields) {
  const result = { ...entity, _displayOriginal: {} };
  for (const [field, view] of Object.entries(fields)) {
    if (view === undefined || view === entity[field]) continue;
    result._displayOriginal[field] = { raw: entity[field], view };
    result[field] = view;
  }
  return result;
}
function stored(entity, field) {
  const previous = entity._displayOriginal?.[field];
  return previous && entity[field] === previous.view ? previous.raw : entity[field];
}

export function newComputer() {
  return { model_name: '', manufacturer_id: '', description: '', announcement_date: '', category_ids: [], source_ids: [], releases: [], configurations: [] };
}
export function newSource() {
  return { title: '', author: '', publisher: '', url: '', source_type: 'website', publication_date: '', access_date: '' };
}
export function computerDraft(computer) {
  return { ...readable(computer, { description: computer.display_description }), configurations: computer.configurations.map(cfg => ({
    ...readable(cfg, { variant_name: cfg.display_name, description: cfg.display_description }),
    specifications: cfg.specifications.map(spec => ({ ...readable(spec, { property_name: spec.display?.property_name }), value_kind: spec.numeric_value != null ? 'number' : 'text' }))
  })) };
}
export function computerPayload(draft) {
  return {
    model_name: draft.model_name.trim(), manufacturer_id: Number(draft.manufacturer_id),
    description: optional(stored(draft, 'description')), announcement_date: optional(draft.announcement_date),
    category_ids: draft.category_ids, source_ids: draft.source_ids,
    releases: draft.releases.map(r => ({
      ...(r.id ? { id: r.id } : {}), market_id: Number(r.market_id),
      release_date: optional(r.release_date), discontinuation_date: optional(r.discontinuation_date),
      price: optional(r.price) == null ? null : Number(r.price), currency: optional(r.currency)?.toUpperCase() ?? null,
      price_type: optional(r.price_type), source_ids: r.source_ids
    })),
    configurations: draft.configurations.map(cfg => ({
      ...(cfg.id ? { id: cfg.id } : {}), variant_name: stored(cfg, 'variant_name').trim(), description: optional(stored(cfg, 'description')),
      specifications: cfg.specifications.map(s => {
        const numeric = s.value_kind === 'number';
        if (numeric && (optional(s.numeric_value) == null || !Number.isFinite(Number(s.numeric_value)))) {
          throw Error('Inserisci un valore numerico valido per ogni specifica numerica.');
        }
        return {
          ...(s.id ? { id: s.id } : {}), component_type: s.component_type.trim(), component_name: optional(s.component_name),
          property_name: stored(s, 'property_name').trim(), numeric_value: numeric ? Number(s.numeric_value) : null,
          text_value: numeric ? null : optional(s.text_value), unit: optional(s.unit), source_ids: s.source_ids
        };
      })
    }))
  };
}
export function sourcePayload(draft) {
  return Object.fromEntries(['title', 'author', 'publisher', 'url', 'source_type', 'publication_date', 'access_date']
    .map(key => [key, optional(draft[key])]));
}
