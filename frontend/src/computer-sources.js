// Every scoped citation belongs in the bibliography; its presence is not verification.
export function computerSources(computer) {
  const sources = new Map();
  const add = list => (list || []).forEach(source => sources.set(source.id, source));
  add(computer.sources);
  (computer.configurations || []).forEach(config => (config.specifications || []).forEach(spec => add(spec.sources)));
  for (const field of ['releases', 'sales', 'reviews', 'facts']) {
    (computer[field] || []).forEach(item => add(item.sources));
  }
  return [...sources.values()];
}

// One citation per commercialization; prefer documented price evidence when present.
export function commercializationSource(release) {
  const sources = release.sources || [];
  const field = release.price != null ? 'price' : 'release_date';
  const supports = new Set(release.field_sources?.[field] || []);
  return sources.find(source => supports.has(source.id) && source.url)
    || sources.find(source => supports.has(source.id))
    || sources.find(source => source.url)
    || sources[0]
    || null;
}
