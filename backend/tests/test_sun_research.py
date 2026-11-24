"""Sun note recovery and curated photos on disposable synthetic catalogs."""
import importlib
from datetime import date
import pytest
from sqlalchemy import select,func
from app.main import SessionLocal
from app.models import Computer,Manufacturer,Release,Market,Source,Fact,ComputerImage
from app.import_models import ImportJob,ImportClaim,CatalogReconciliation
from app.importing import sun_research as research

@pytest.fixture(autouse=True)
def no_seed(monkeypatch):
    monkeypatch.setattr(importlib.import_module('app.main'),'seed',lambda db:None)


def computer(db,name,maker=None,year=None,price=None):
    maker=maker or db.scalar(select(Manufacturer).where(Manufacturer.name=='Sun Microsystems')) or Manufacturer(name='Sun Microsystems')
    c=Computer(manufacturer=maker,model_name=name)
    if year or price:
        market=db.scalar(select(Market).where(Market.name=='Stati Uniti')) or Market(name='Stati Uniti')
        c.releases=[Release(market=market,release_date=date(year,1,1) if year else None,
            release_precision='year' if year else None,price=price,currency='USD' if price else None)]
    db.add(c);db.commit();return c


def context(db,c,year='1990',url='https://example.org/source'):
    f=Fact(computer=c,fact_type='Contesto del prezzo',statement=f'ID: 7; Modello: {c.model_name}; Anno lancio: {year}; Prezzo al lancio: 4995; Valuta: USD; Note: listino 1991, non dedurre la data dal testo libero.',
           sources=[Source(title='Synthetic existing external source',url=url,source_type='research_reference')])
    db.add(f);db.commit();return f


def test_package_has_qualified_chronology_and_correct_photographic_identity():
    data,_=research.load()
    assert len(data['models'])==24 and len(data['photos'])==11
    assert next(d for d in data['dates'] if d['model_name']=='Sun 3/260/280')['kind']=='reference'
    assert next(d for d in data['dates'] if d['model_name']=='Ultra 45')['release_date']=='2006'
    assert 'SPARCstation_10_motherboard' in data['wrong_automatic_photos']['SPARCstation 1'][0]
    assert data['photos']['SPARCstation 1'][0]['source_url'].startswith('https://www.1000bit.it/')
    assert 'licenza libera' in data['photos']['Sun 3/110'][0]['license_name']
    assert 'componente' in data['photos']['Sun 3/50'][0]['caption']


def test_note_year_fills_existing_offer_without_changing_price_and_repeats_cleanly(client):
    with SessionLocal() as db:
        c=computer(db,'SPARCstation SLC',price=4995);f=context(db,c);cid=c.id;rid=c.releases[0].id;sid=f.sources[0].id
        result=research.apply(db)
        assert result['dates_filled']==1 and result['release_rows_created']==0
        db.refresh(c);r=c.releases[0]
        assert r.id==rid and r.release_date==date(1990,1,1) and r.release_precision=='year'
        assert r.price==4995 and r.currency=='USD' and r.market.name=='Stati Uniti'
        assert r.catalog_details['date_scope']=='reference' and r.catalog_details['date_sources']==[sid]
        assert f.statement.endswith('dal testo libero.')
        claim=db.scalar(select(ImportClaim).where(ImportClaim.entity=='Release',ImportClaim.field=='release_date'))
        assert claim.status=='pending' and not claim.estimated and claim.source_id==sid
        assert db.scalar(select(func.count()).select_from(Computer))==1
        from app.catalog_cleanup import prepare,apply
        apply(db,prepare(db));db.refresh(r)
        assert r.catalog_details['date_scope']=='reference'
        assert r.catalog_details['date_evidence']['kind']=='reference'
        assert research.apply(db)['already_applied']
        assert db.scalar(select(func.count()).select_from(ImportJob))==1
    data=client.get('/api/computers/'+str(cid)).json()
    assert data['first_release']=='1990' and data['releases'][0]['price']==4995
    assert data['display_releases'][0]['date_scope']=='reference'


def test_catalog_bounds_not_misrepresented_as_launch_and_no_price_guesses(client):
    with SessionLocal() as db:
        c=computer(db,'Sun 3/260/280');context(db,c,'1988')
        result=research.apply(db);db.refresh(c)
        assert result['dates_filled']==1 and len(c.releases)==1
        assert c.releases[0].release_date==date(1986,1,1)
        assert c.releases[0].catalog_details['date_scope']=='reference'
        assert c.releases[0].price is None  # A variant price in the note is not the whole family price.
        assert 'ottobre 1986' in c.releases[0].catalog_details['reference_note']


def test_correction_only_for_exact_unverified_base_date(client):
    with SessionLocal() as db:
        c=computer(db,'Ultra 45',year=1996,price=3695);r=c.releases[0];db.flush()
        old=Source(title='MAME old base chronology',url='https://github.com/mamedev/mame/blob/old/ultra45.cpp')
        job=ImportJob(provider='manual',filename='synthetic',format='json',checksum='a'*64,raw_payload='[]')
        from app.import_models import ImportRow
        row=ImportRow(position=1,raw={},normalized={},computer_id=c.id,status='imported')
        job.rows.append(row)
        row.claims.append(ImportClaim(computer_id=c.id,source=old,entity='Release',target_id=r.id,field='release_date',
            value={'value':'1996-01-01','precision':'year'},previous={'value':None},status='pending',estimated=False))
        db.add(job);db.commit()
        result=research.apply(db);db.refresh(r)
        assert result['dates_corrected']==1 and r.release_date==date(2006,1,1)
        assert r.price==3695 and r.currency=='USD'
        assert row.claims[0].value['value']=='1996-01-01'  # Original claim retained.
        assert len(list(db.scalars(select(ImportClaim))))==2


def test_curated_dates_manual_covers_unrelated_makers_and_ambiguous_notes_are_preserved(client):
    with SessionLocal() as db:
        c=computer(db,'SPARCstation IPC',year=1995,price=777);context(db,c,'1990')
        c.releases[0].catalog_details={'date_manual':True}
        c.images=[ComputerImage(remote_url='https://example.org/manual.jpg',is_primary=True,caption='Manual cover',license_name='Synthetic permission',source_url='https://example.org/')]
        other=computer(db,'SPARCstation SLC',maker=Manufacturer(name='Samsung'),price=999);context(db,other,'1980')
        ambiguous=computer(db,'SPARCstation SLC');context(db,ambiguous,'1990');context(db,ambiguous,'1991',url='https://example.org/other')
        db.commit();research.apply(db);db.refresh(c);db.refresh(other);db.refresh(ambiguous)
        assert c.releases[0].release_date==date(1995,1,1) and c.releases[0].price==777
        assert next(i for i in c.images if i.is_primary).remote_url=='https://example.org/manual.jpg'
        assert len(c.images)==2
        assert other.releases[0].release_date is None and not other.images
        assert not ambiguous.releases


def test_only_known_automatic_wrong_photos_retired_and_metadata_audited(client):
    with SessionLocal() as db:
        c=computer(db,'Sun 3/80');data,_=research.load();wrong=data['wrong_automatic_photos']['Sun 3/80'][0]
        c.images=[ComputerImage(remote_url='https://example.org/wrong.jpg',source_url=wrong,caption=research.AUTO_PHOTO+' old',license_name='Synthetic',is_primary=True),
                  ComputerImage(remote_url='https://example.org/manual.jpg',source_url=wrong,caption='Curated reference photo',license_name='Synthetic',is_primary=False)]
        db.commit();result=research.apply(db);db.refresh(c)
        assert result['wrong_automatic_photos_retired']==1 and result['photos_added']==1
        assert 'https://example.org/manual.jpg' in [i.remote_url for i in c.images]
        assert 'https://example.org/wrong.jpg' not in [i.remote_url for i in c.images]
        audit=db.scalar(select(CatalogReconciliation).where(CatalogReconciliation.entity==research.ENTITY))
        assert audit.snapshot['photo_changes'][0]['before']['remote_url']=='https://example.org/wrong.jpg'


def test_late_failure_rolls_back_dates_images_sources_and_audit(client,monkeypatch):
    def fail(*a,**k):raise RuntimeError('synthetic refresh failure')
    with SessionLocal() as db:
        c=computer(db,'SPARCstation IPC',price=6995);context(db,c,'1990');cid=c.id
        monkeypatch.setattr('app.catalog_store.refresh_pending',fail)
        with pytest.raises(RuntimeError,match='synthetic refresh failure'):research.apply(db)
        c=db.get(Computer,cid)
        assert c.releases[0].release_date is None and not c.images
        assert not db.scalar(select(ImportJob.id)) and not db.scalar(select(CatalogReconciliation.id))
        assert db.scalar(select(func.count()).select_from(Source))==1


def test_ambiguous_manufacturer_aborts_and_absent_computers_never_created(client):
    with SessionLocal() as db:
        db.add_all([Manufacturer(name='Sun Microsystems'),Manufacturer(name='Sun')]);db.commit()
        with pytest.raises(ValueError,match='ambiguo'):research.apply(db)
        assert not db.scalar(select(Computer.id)) and not db.scalar(select(ImportJob.id))
