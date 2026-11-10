import os
os.environ['DATABASE_URL']='sqlite:///./test_hhe.db'
from fastapi.testclient import TestClient
from app.main import app

def test_catalog_and_analysis():
 with TestClient(app) as c:
  r=c.get('/api/computers');assert r.status_code==200
  assert r.json()['total']>=10
  assert c.get('/api/analytics').json()['total']>=10
  assert c.get('/api/computers/1').status_code==200
  assert c.get('/api/compare?ids=1,2').status_code==200
  assert c.get('/api/compare?ids=1').status_code==400
