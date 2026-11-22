import { displaySpecification } from './catalog-display.js';

const exactBytes = { B: 1, KiB: 1024, MiB: 1048576, GiB: 1073741824 };
const baseLabels = new Set(['capacità', 'capacità riportata', 'dotazione', 'dotazioni riportate', 'dotazione di base', 'capacità installata', 'ram installata']);
const referenceLabels = new Set(['capacità di riferimento', 'capacità predefinita (mame)']);
const aliases = new Map([['Opzioni RAM emulatore (MAME)', 'Opzioni di memoria'], ['Capacità riportata (Wikidata)', 'Capacità riportata'], ['capacity', 'Capacità'], ['memory-capacity', 'Capacità']]);
const clean = value => String(value ?? '').trim().replace(/\s+/g, ' ');
const roleName = value => /^(?:ram|mainram|system ram|memoria principale)$/i.test(clean(value)) ? '' : clean(value);

// KB/MB/GB are the reader's historical labels for already explicit IEC values.
// Legacy KB and lower-case Kb are NOT interpreted as binary quantities here.
function entry(view, qualifier = '') {
  let number = view.numeric_value, unit = clean(view.unit), text = clean(view.text_value);
  if (number == null && unit && /^\d+$/.test(text)) { number = Number(text); text = ''; }
  if (number == null) {
    const scalar = text.match(/^(\d+(?:[.,]\d+)?)\s*(B|KiB|MiB|GiB|KB|kB|MB|GB|Kb|kb|Mb|mb|Gb|gb)$/);
    if (scalar && (!unit || unit === scalar[2])) { number = Number(scalar[1].replace(',', '.')); unit = scalar[2]; text = ''; }
  }
  if (number != null && !Number.isFinite(number)) return null;
  if (number == null && !text) return null;
  const role = roleName(view.component_name);
  const bytes = number != null && Object.hasOwn(exactBytes, unit) ? number * exactBytes[unit] : null;
  let shownNumber = number, shownUnit = ({ KiB: 'KB', MiB: 'MB', GiB: 'GB' }[unit] || unit);
  if (bytes != null && Number.isSafeInteger(bytes)) {
    const scale = bytes === 0 ? ['KB', 1024] : [['GB', 1073741824], ['MB', 1048576], ['KB', 1024], ['B', 1]].find(([, factor]) => bytes % factor === 0);
    [shownUnit, shownNumber] = [scale[0], bytes / scale[1]];
  }
  let shownText = number == null ? text.replace(/\b(KiB|MiB|GiB)\b/g, token => ({ KiB: 'KB', MiB: 'MB', GiB: 'GB' }[token])) : '';
  if (number == null && unit) {
    const inline = text.match(/\b(?:B|KiB|MiB|GiB|KB|kB|MB|GB|Kb|kb|Mb|mb|Gb|gb)\b/g) || [];
    if (!inline.length) shownText += ' ' + shownUnit;
    else if (inline.some(value => value !== unit)) shownText += ` (unità dichiarata: ${shownUnit})`;
  }
  return { number, unit, text, role, qualifier, bytes,
    shownNumber, shownUnit, shownText,
    identity: JSON.stringify([role.toLowerCase(), qualifier, bytes != null && Number.isSafeInteger(bytes) ? ['bytes', bytes] : [number, unit, text]]) };
}

export function memoryText(values) {
  const entries = [...new Map(values.map(value => [value.identity, value])).values()].sort((a, b) => {
    const prefix = (a.role + a.qualifier).localeCompare(b.role + b.qualifier, 'it');
    if (prefix) return prefix;
    if (a.bytes != null && b.bytes != null) return a.bytes - b.bytes;
    if (a.number != null && b.number != null && a.unit === b.unit) return a.number - b.number;
    return (a.shownText || `${a.shownNumber} ${a.shownUnit}`).localeCompare(b.shownText || `${b.shownNumber} ${b.shownUnit}`, 'it', { numeric: true });
  });
  const groups = new Map();
  for (const value of entries) {
    const identity = JSON.stringify([value.role, value.qualifier]);
    if (!groups.has(identity)) groups.set(identity, []);
    groups.get(identity).push(value);
  }
  return [...groups.values()].map(group => {
    const first = group[0];
    const common = group.every(value => value.shownNumber != null && value.shownUnit === first.shownUnit)
      && new Set(group.map(value => value.shownNumber)).size === group.length;
    const label = [first.role, first.qualifier].filter(Boolean).join(' · ');
    const text = common ? group.map(value => value.shownNumber).join(' / ') + (first.shownUnit ? ' ' + first.shownUnit : '')
      : group.map(value => value.shownNumber == null ? value.shownText
        : `${value.shownNumber}${value.shownUnit ? ' ' + value.shownUnit : ''}${group.some(other => other !== value && other.shownNumber === value.shownNumber && other.shownUnit === value.shownUnit) && value.bytes == null ? ' (unità originale)' : ''}`).join(' / ');
    return (label ? label + ': ' : '') + text;
  }).join('; ');
}

function covered(reference, capacities) {
  if (capacities.some(value => value.identity === reference.identity)) return true;
  // A literal list/range can contain the reference as an explicit endpoint.
  // Do not invent intermediate configurations, infer a base, or read VRAM as RAM.
  return capacities.some(value => value.number == null && !reference.role && !value.role && !/\b(?:VRAM|SRAM|ROM)\b/i.test(value.text)
    && (value.text.match(/\d+(?:[.,]\d+)?\s*(?:B|KiB|MiB|GiB|KB|kB|MB|GB|Kb|kb|Mb|mb|Gb|gb)\b/g) || [])
      .some(token => entry({ numeric_value: null, text_value: token }).identity === reference.identity));
}

/** Two reader-facing RAM rows at most; originals, sources and scopes stay intact. */
export function memorySpecifications(specifications) {
  const memory = specifications.filter(spec => displaySpecification(spec).component_type === 'RAM');
  if (!memory.length) return specifications;
  const capacities = [], references = [], options = [], notes = [];
  const mainSources = [], optionSources = [];
  const add = (list, value, original, sources) => { if (value) { list.push(value); sources.push(original); } };
  for (const original of memory) {
    const view = displaySpecification(original);
    const prop = aliases.get(view.property_name) || view.property_name;
    const name = clean(prop).toLowerCase();
    if (baseLabels.has(name)) add(capacities, entry(view), original, mainSources);
    else if (referenceLabels.has(name)) add(references, entry(view), original, mainSources);
    else if (/opzioni|espansion|massim|minim|limite/.test(name)) {
      const qualifier = /introduzione|lancio/.test(name) ? 'Limite al lancio' : /massim|limite/.test(name) ? 'Massima' : /minim/.test(name) ? 'Minima' : /opzioni/.test(name) ? '' : prop;
      const parts = /opzioni/.test(name) && view.numeric_value == null ? clean(view.text_value).split(/\s*\/\s*/).map(text => entry({ ...view, text_value: text }, qualifier)) : [];
      if (parts.length > 1 && parts.every(value => value?.number != null && value.unit)) {
        for (const value of parts) add(options, value, original, optionSources);
      } else add(options, entry(view, qualifier), original, optionSources);
    } else {
      const value = entry(view);
      if (value) { notes.push(`${prop}: ${memoryText([value])}`); mainSources.push(original); }
    }
  }
  const values = capacities.length ? capacities : references;
  if (!capacities.length && references.length) notes.push('Valore di riferimento; dotazione di base non documentata.');
  if (capacities.length) {
    const distinct = references.filter(value => !covered(value, capacities));
    if (distinct.length) notes.push('Altri valori di riferimento: ' + memoryText(distinct) + '.');
  }
  const primary = [...new Map(values.map(value => [value.identity, value])).values()];
  if (primary.some(value => value.number != null && primary.some(other => other !== value && other.number != null
    && other.role.toLowerCase() === value.role.toLowerCase()))) notes.push('Quantità diverse riportate per questa configurazione.');
  // Equal options add no information when the main field already states them.
  const choices = new Set(options.filter(option => !option.qualifier).map(option => option.identity));
  const extra = options.filter(option => option.qualifier || choices.size > 1 || !values.some(value => value.identity === option.identity));
  mainSources.push(...options.flatMap((option, index) => extra.includes(option) ? [] : [optionSources[index]]));
  const ids = originals => [...new Set(originals.flatMap(spec => spec.specification_ids || (spec.id == null ? [] : [spec.id])))];
  const sources = originals => [...new Map(originals.flatMap(spec => spec.sources || []).map(source => [source.id ?? JSON.stringify([source.title, source.url]), source])).values()];
  function row(property, entries, originals, annotations = []) {
    const view = { component_type: 'RAM', component_name: null, property_name: property, numeric_value: null,
      text_value: memoryText(entries) || 'Non documentata', unit: null };
    return { id: `ram-${property}`, ...view, normalized: view, display: { component_type: 'RAM', property_name: property },
      memory_values: entries, memory_notes: [...new Set(annotations)], specification_ids: ids(originals), sources: sources(originals) };
  }
  const rows = [row('Capacità', values, mainSources, notes)];
  if (extra.length) rows.push(row('Opzioni di memoria', extra, optionSources));
  const first = specifications.indexOf(memory[0]);
  return specifications.flatMap((spec, index) => index === first ? rows : displaySpecification(spec).component_type === 'RAM' ? [] : [spec]);
}
