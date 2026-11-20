"""Italian portable-computer vocabulary must not select an unrelated namesake."""
import asyncio
import json
from copy import deepcopy
from pathlib import Path
import httpx
import pytest
from sqlalchemy import select, func
from app import history_sources as h
from app.main import SessionLocal
from app.models import Computer, Manufacturer
from app.import_models import ImportClaim


def fixture(name):
    return json.loads((Path(__file__).parent/'fixtures'/name).read_text(encoding='utf-8'))


def test_real_portfolio_uses_the_computer_article_and_preserves_revision_and_license():
    computer=fixture('wikipedia-it-atari-portfolio.json')
    unrelated=fixture('wikipedia-it-portfolio-generic.json')
    combined=deepcopy(computer)
    combined['query']['pages']+=unrelated['query']['pages']
    for payload in [computer,combined]:
        result=h.select_result('Portfolio','Atari',payload,full_page=True)
        assert result['status']=='found' and result['title']=='Atari Portfolio'
        assert 'handheld PC' in result['description'] and '1989' in result['description']
        assert result['revision_id']==138561566 and 'oldid=138561566' in result['url']
        assert result['license_url'].endswith('/by-sa/4.0/')
    assert h.select_result('Portfolio','Atari',unrelated,full_page=True)['status']=='no_match'
    assert h.select_result('Portfolio','Other maker',computer)['status']=='no_match'
    assert h.select_result('Portfolio 2','Atari',computer)['status']=='no_match'


@pytest.mark.parametrize('device',['handheld PC','pocket PC','tablet PC','personal digital assistant','palmare','palmtop','notebook','netbook','laptop','organizzatore elettronico','homecomputer'])
def test_device_vocabulary_is_general_and_still_requires_exact_identity_and_history(device):
    text=(f'Synthetic Portable è un {device} di IBM presentato nel 1989 per questo test. '
          'Il contesto storico sintetico ne illustra lo sviluppo e la destinazione commerciale senza dichiarare fatti su macchine reali.')
    payload={'query':{'pages':[{'title':'Synthetic Portable','ns':0,'revisions':[{'revid':123}],'extract':text}]}}
    assert h.select_result('Synthetic Portable','IBM',payload)['status']=='found'
    assert h.select_result('Synthetic Portable X','IBM',payload)['status']=='no_match'
    payload['query']['pages'][0]['extract']=(f'Un {device} di IBM con una descrizione tecnica sintetica; questo testo non contiene date né eventi storici. ')*3
    assert h.select_result('Synthetic Portable','IBM',payload)['status']=='no_match'


def test_bare_pc_and_financial_prose_do_not_count_as_computer_context():
    text='Nel 1989 il portfolio documentava i lavori di IBM e i rapporti del PC, una sigla politica riportata nel testo originale. '*3
    assert h.intro(text) is None


def test_portable_search_remembers_the_matching_title_without_following_a_generic_namesake(monkeypatch):
    computer=fixture('wikipedia-it-atari-portfolio.json')
    short=deepcopy(computer);short['query']['pages'][0]['extract']="L'Atari Portfolio è un handheld PC dell'Atari commercializzato nel 1989."
    seen=[]
    def handler(request):
        seen.append(dict(request.url.params))
        return httpx.Response(200,json=short if len(seen)==1 else computer)
    original=httpx.AsyncClient
    monkeypatch.setattr(h.httpx,'AsyncClient',lambda **kw:original(transport=httpx.MockTransport(handler),**kw))
    first,_=asyncio.run(h.research('Portfolio','Atari'))
    assert first['status']=='no_match' and first['full_title']=='Atari Portfolio'
    result,_=asyncio.run(h.research('Portfolio','Atari',attempt=len(h.search_plan('Portfolio','Atari'))-1,full_title=first['full_title']))
    assert seen[1]['titles']=='Atari Portfolio' and result['status']=='found'


def test_portfolio_updates_through_the_real_queue_with_pending_claim_and_preserved_original(client,monkeypatch):
    with SessionLocal() as db:
        maker=Manufacturer(name='Atari');computer=Computer(manufacturer=maker,model_name='Portfolio',description='Portfolio è un calcolatore di Atari.')
        db.add(computer);db.commit();cid=computer.id
    original=httpx.AsyncClient
    monkeypatch.setattr(h.httpx,'AsyncClient',lambda **kw:original(transport=httpx.MockTransport(lambda request:httpx.Response(200,json=fixture('wikipedia-it-atari-portfolio.json'))),**kw))
    job=client.post('/api/admin/history').json()
    result=client.post(f'/api/admin/history/{job["id"]}/step').json()
    assert result['status']=='completed' and result['counts']['updated']==1
    data=client.get(f'/api/computers/{cid}').json()
    assert 'handheld PC' in data['description'] and data['description_attribution']['title']=='Atari Portfolio'
    with SessionLocal() as db:
        claim=db.scalar(select(ImportClaim).where(ImportClaim.computer_id==cid))
        assert claim.status=='pending' and claim.previous['value']=='Portfolio è un calcolatore di Atari.'
        assert db.scalar(select(func.count()).select_from(ImportClaim))==1
    assert client.post('/api/admin/history').json()['counts']['preserved']==11


def test_previous_rejection_can_be_targeted_once_after_the_vocabulary_upgrade():
    old={'search_version':4,'candidates':[{'title':'Portfolio'}]}
    assert h.improved_retry('Portfolio','Atari',old)
    assert not h.improved_retry('Portfolio','Atari',{**old,'search_version':h.SEARCH_VERSION})
