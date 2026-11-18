"""Disposable catalog-quality fixture; no access to the operator's archive."""
import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
if os.getenv('HHE_ALLOW_QUALITY_BROWSER_FIXTURE') != '1':
    raise SystemExit('Set HHE_ALLOW_QUALITY_BROWSER_FIXTURE=1 for this disposable fixture.')
files=TemporaryDirectory(prefix='hhe-quality-browser-')
os.environ['DATABASE_URL']=f'sqlite:///{files.name}/quality_test.sqlite'
os.environ['UPLOAD_DIR']=str(Path(files.name)/'uploads')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.main import app
import uvicorn
@app.get('/__quality_fixture')
def marker(): return {'fixture':'catalog-quality-synthetic','isolated':True}
if __name__=='__main__':uvicorn.run(app,host='127.0.0.1',port=18095)
