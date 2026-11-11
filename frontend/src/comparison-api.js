import { api } from './api.js';

export function comparisonSummary(computer) {
  return { id: computer.id, model_name: computer.model_name, manufacturer: computer.manufacturer, year: computer.year };
}

export function comparisonSuggestions(query, selectedIds, signal) {
  const params = new URLSearchParams({ q: query.trim(), limit: '8' });
  for (const id of selectedIds) params.append('exclude_ids', String(id));
  return api('/computers/suggestions?' + params, { signal });
}
