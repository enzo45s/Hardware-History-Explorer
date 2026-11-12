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
