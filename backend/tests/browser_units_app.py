"""Disposable, opt-in unit-review fixture; never opens the operator's database."""
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from contextlib import asynccontextmanager

if os.getenv('HHE_ALLOW_UNIT_BROWSER_FIXTURE') != '1':
    raise SystemExit('Set HHE_ALLOW_UNIT_BROWSER_FIXTURE=1 for this disposable fixture.')
files = TemporaryDirectory(prefix='hhe-units-browser-')
os.environ['DATABASE_URL'] = f'sqlite:///{files.name}/browser_test.sqlite'
os.environ['UPLOAD_DIR'] = files.name + '/uploads'
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.main import app, engine, SessionLocal, Base  # noqa: E402
from app.models import Manufacturer, Computer, Configuration, Specification, Source, spec_source  # noqa: E402
from app.unit_review import load_proofs  # noqa: E402

Base.metadata.create_all(engine)
manifest = {}
with SessionLocal() as db:
    for model in ('KIM-1', 'BCS 2030'):
        rule = next(r for r in load_proofs()[0]['rules'] if r['model_name'] == model)
        maker = Manufacturer(name=rule['manufacturer'])
        spec = Specification(**rule['before'])
        computer = Computer(manufacturer=maker, model_name=model, description='Contesto sintetico da conservare.',
            configurations=[Configuration(variant_name=rule['configuration'], specifications=[spec])])
        source = Source(title='Fonte originale del campione sintetico', url=rule['original_source_url'], source_type='website')
        db.add_all([computer, source]); db.flush()
        db.execute(spec_source.insert().values(target_id=spec.id, source_id=source.id,
            verification_status='pending', evidence='Dato sintetico per la prova browser.'))
        manifest[model] = computer.id
    db.add(Computer(manufacturer=Manufacturer(name='Produttore sintetico'), model_name='Modello senza regola',
        configurations=[Configuration(variant_name='Base', specifications=[Specification(component_type='RAM',
            property_name='Capacità', numeric_value=64, unit='KB')])]))
    db.commit()

@asynccontextmanager
async def fixture_lifespan(_):
    yield
app.router.lifespan_context = fixture_lifespan

@app.get('/__unit_fixture')
def fixture():
    return manifest

from fastapi.staticfiles import StaticFiles  # noqa: E402
app.mount('/', StaticFiles(directory=str(Path(__file__).resolve().parents[2] / 'frontend/dist'), html=True), name='unit-test-frontend')

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='127.0.0.1', port=18098)
