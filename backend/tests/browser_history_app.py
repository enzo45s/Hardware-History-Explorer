"""Disposable Italian-history fixture. No external HTTP or AI calls."""
from pathlib import Path
from tempfile import TemporaryDirectory
import os
import sys
if os.getenv('HHE_ALLOW_HISTORY_BROWSER_FIXTURE') != '1':
    raise SystemExit('Set HHE_ALLOW_HISTORY_BROWSER_FIXTURE=1 for this disposable fixture.')
files = TemporaryDirectory(prefix='hhe-history-browser-')
os.environ['DATABASE_URL'] = f'sqlite:///{files.name}/history_test.sqlite'
os.environ['UPLOAD_DIR'] = str(Path(files.name) / 'uploads')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.main import app
from app import history_sources
from fastapi import HTTPException
import uvicorn
calls = []
async def research(model, maker, *, attempt=0, full_title=None):
    calls.append(model)
    if len(calls) == 1:
        raise HTTPException(503, 'Pausa sintetica della fonte; puoi riprendere.', headers={'Retry-After': '2'})
    if model == 'Synthetic History Missing' and calls.count(model) == 1:
        return {'status': 'no_match', 'search_version': 2, 'reason': 'Vecchio esito sintetico da rivedere.',
                'candidates': [{'title': model, 'url': 'https://example.org/synthetic-history'}]}, {'query': {'pages': []}}
    assert model in ('Synthetic History Browser', 'Synthetic History Missing'), 'Curated descriptions must not be researched.'
    if model == 'Synthetic History Browser' and attempt == 0:
        return {'status': 'no_match', 'next_attempt': 1, 'search_version': history_sources.SEARCH_VERSION,
                'search': history_sources.search_plan(model, maker)[0]}, {'query': {'pages': []}}
    text = (f'{model} è un computer di {maker} introdotto nel 1981 nel contesto storico sintetico della prova browser. '
            'Lo sviluppo e il posizionamento commerciale sono descritti esclusivamente come dati sintetici per verificare il funzionamento della ricerca.')
    raw = {'query': {'pages': [{'ns': 0, 'title': model, 'extract': text, 'revisions': [{'revid': 456}]}]}}
    result = history_sources.select_result(model, maker, raw)
    result['search_version'] = history_sources.SEARCH_VERSION
    result['search'] = {'strategy': 'brand_model', 'query': f'{maker} {model}'}
    return result, raw
history_sources.research = research
@app.get('/__history_fixture')
def marker(): return {'fixture': 'italian-history-synthetic', 'isolated': True, 'calls': calls}
if __name__ == '__main__': uvicorn.run(app, host='127.0.0.1', port=18094)
