"""Isolated synthetic website for browser tests; never connects to 1000bit."""
from pathlib import Path
from tempfile import TemporaryDirectory
import os
import sys
if os.getenv('HHE_ALLOW_BULK_BROWSER_FIXTURE') != '1':
    raise SystemExit('Set HHE_ALLOW_BULK_BROWSER_FIXTURE=1 to start the isolated fixture.')
files = TemporaryDirectory(prefix='hhe-bulk-browser-')
os.environ['DATABASE_URL'] = f'sqlite:///{files.name}/bulk_browser_test.sqlite'
os.environ['UPLOAD_DIR'] = str(Path(files.name) / 'uploads')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.main import app
from app.importing import bulk1000bit as bulk
from app.main import SessionLocal
from app.models import Computer, Manufacturer
from sqlalchemy import select
import uvicorn
html=(Path(__file__).with_name('fixtures') / '1000bit-amiga1200.html').read_bytes()
def fake_fetch(url, limit):
 if url.endswith('/robots.txt'):return 200,b'User-agent: *\nAllow: /\nCrawl-delay: 5','text/plain',{}
 if '/database' in url:return 200,b'<a href="/scheda.asp?id=282">Amiga</a><a href="/scheda.asp?id=900001">Synthetic</a><a href="/scheda.asp?id=900002">Unknown</a>','text/html',{}
 if url==bulk.SEED:return 200,html,'text/html',{}
 if url=='https://www.1000bit.it/scheda.asp?id=935':return 200,(Path(__file__).with_name('fixtures') / '1000bit-fujitsu935-names.html').read_bytes(),'text/html',{}
 if 'id=900001' in url:return 200,html.replace(b'Amiga 1200',b'Bulk Browser Fixture').replace(b'id=282',b'id=900001'),'text/html',{}
 if 'id=900002' in url:return 200,html.replace(b'Amiga 1200',b'Unrelated Browser Fixture').replace(b'id=282',b'id=900002'),'text/html',{}
 raise ValueError('Unexpected synthetic URL: '+url)
bulk.fetch=fake_fetch
@app.get('/__bulk_fixture')
def marker():
 return {'fixture': '1000bit-bulk-synthetic', 'isolated': True}

@app.post('/__bulk_fixture/legacy-fujitsu')
def legacy_fujitsu():
 # Reproduce the operator's old unmatched result, without downloading the site.
 from fastapi import HTTPException
 from datetime import timedelta
 with SessionLocal() as db:
  if db.scalar(select(bulk.BulkJob.id).where(bulk.BulkJob.active_key=='1000bit')):
   raise HTTPException(409,'Finish the synthetic traversal before preparing this fixture.')
  previous=db.scalar(select(bulk.BulkJob).order_by(bulk.BulkJob.id.desc()).limit(1))
  maker=Manufacturer(name='Fujitsu');db.add(maker);db.flush()
  computer=Computer(manufacturer=maker,model_name='FM-11 EX',description='Synthetic browser baseline description')
  db.add(computer);db.flush()
  job=bulk.BulkJob(status='completed',robots=dict(previous.robots),requests=previous.requests,
                   next_request_at=bulk.now()+timedelta(seconds=5))
  db.add(job);db.flush()
  for c in db.scalars(select(Computer)):
   db.add(bulk.BulkTarget(job_id=job.id,original_id=c.id,computer_id=c.id,model_name=c.model_name,
                         manufacturer=c.manufacturer.name,status='updated' if c.model_name in ('Amiga 1200','Bulk Browser Fixture') else 'not_found'))
  db.add(bulk.BulkPage(job_id=job.id,url='https://www.1000bit.it/scheda.asp?id=935',status='unmatched',
                       model_name='FM 11 EX',manufacturer='Fujitsu (Japan)'))
  db.commit()
  return {'job_id':job.id,'computer_id':computer.id,'requests':job.requests}
if __name__ == '__main__':
 uvicorn.run(app,host='127.0.0.1',port=18093)
