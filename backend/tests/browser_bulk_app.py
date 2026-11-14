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
import uvicorn
html=(Path(__file__).with_name('fixtures') / '1000bit-amiga1200.html').read_bytes()
def fake_fetch(url, limit):
 if url.endswith('/robots.txt'):return 200,b'User-agent: *\nAllow: /\nCrawl-delay: 5','text/plain',{}
 if '/database' in url:return 200,b'<a href="/scheda.asp?id=282">Amiga</a><a href="/scheda.asp?id=900001">Synthetic</a><a href="/scheda.asp?id=900002">Unknown</a>','text/html',{}
 if url==bulk.SEED:return 200,html,'text/html',{}
 if 'id=900001' in url:return 200,html.replace(b'Amiga 1200',b'Bulk Browser Fixture').replace(b'id=282',b'id=900001'),'text/html',{}
 if 'id=900002' in url:return 200,html.replace(b'Amiga 1200',b'Unrelated Browser Fixture').replace(b'id=282',b'id=900002'),'text/html',{}
 raise ValueError('Unexpected synthetic URL: '+url)
bulk.fetch=fake_fetch
@app.get('/__bulk_fixture')
def marker():
 return {'fixture': '1000bit-bulk-synthetic', 'isolated': True}
if __name__ == '__main__':
 uvicorn.run(app,host='127.0.0.1',port=18093)
