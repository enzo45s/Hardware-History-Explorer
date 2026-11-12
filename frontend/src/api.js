export async function api(path, options = {}) {
  const isForm = options.body instanceof FormData;
  const response = await fetch('/api' + path, {
    ...options,
    headers: { ...(isForm ? {} : { 'Content-Type': 'application/json' }), ...options.headers }
  });
  if (!response.ok) {
    let explanation = 'Errore ' + response.status;
    try {
      const payload = await response.json();
      if (typeof payload.detail === 'string') explanation = payload.detail;
      else if (Array.isArray(payload.detail)) explanation = payload.detail.map(e => e.msg).join('; ');
    } catch { /* risposta non JSON */ }
    throw Error(explanation);
  }
  return response.status === 204 ? null : response.json();
}

// Abort obsolete fetches and ignore responses even if a transport ignores abort.
export function latestRequest(load, onSuccess, onError) {
  const controller = new AbortController();
  Promise.resolve().then(() => load(controller.signal)).then(value => {
    if (!controller.signal.aborted) onSuccess(value);
  }).catch(error => {
    if (!controller.signal.aborted) onError(error);
  });
  return () => controller.abort();
}

export async function allComputers(filters = new URLSearchParams(), signal) {
  const params = new URLSearchParams(filters);
  params.set('limit', '100');
  let items = [];
  let page;
  do {
    params.set('offset', String(items.length));
    page = await api('/computers?' + params, { signal });
    items = items.concat(page.items);
  } while (page.items.length && items.length < page.total);
  return items;
}
