"""Historical identities and preservation when applying the scoped supplement."""
import json

from sqlalchemy import func, select

from app.main import SessionLocal
from app.models import Computer, Manufacturer, Source, manufacturer_source
from app.manufacturer_enrichment import PACKAGE, apply_enrichment, load_package


SUPPLEMENT = PACKAGE.with_name('manufacturers-deep-2026-11-v1.json')


def test_deep_research_retains_identity_and_image_rights_boundaries():
    package, _ = load_package(SUPPLEMENT)
    rows = {r['manufacturer_names'][0]: r for r in package['records']}
    # The old archive's Oric, US Timex Sinclair, Kaypro and Dragon marks do
    # not establish the identity of these distinct catalog attributions.
    for name in ('Tangerine', 'Timex of Portugal', 'Non-Linear Systems',
                 'Dragon Data / Tano', 'Osborne/Nuevo'):
        assert 'logo_url' not in rows.get(name, {}).get('fields', {})
    assert 'multitechElectronics' in rows['Multitech']['fields']['logo_url']
    for name in ('Alex Zhabin', 'Vladimir Drozdov', 'Kondor and Kramis',
                 'Dragon Data / Compusense'):
        assert 'logo_url' not in rows[name]['fields']
        assert 'founded' not in rows[name]['fields']
    assert '48K' in rows['Vladimir Drozdov']['fields']['description']
    assert '128K' not in rows['Vladimir Drozdov']['fields']['description']
    assert 'Nanjing Computer Factory' not in rows
    for row in package['records']:
        if 'logo_url' in row['fields']:
            assert 'licenza libera' in row['fields']['logo_license']
            assert 'logo_license_url' not in row['fields']
            assert row['fields']['logo_source_url'] in {
                source['url'] for source in row['sources']}


def test_supplement_fills_gaps_without_replacing_curated_data_or_claiming_false_sources(client):
    package, _ = load_package(SUPPLEMENT)
    rows = {r['manufacturer_names'][0]: r for r in package['records']}
    with SessionLocal() as db:
        history = Source(title='Synthetic curated history', url='https://example.org/manual-history')
        itt = Manufacturer(name='ITT Information Systems', description='Testo rivisto a mano.', sources=[history])
        terco = Manufacturer(name='Terco AB', website='https://example.org/curated')
        person = Manufacturer(name='Alex Zhabin')
        namesake = Manufacturer(name='ITT Inc.')
        timex = Manufacturer(name='Timex of Portugal')
        manual_logo = Manufacturer(name='Multitech', logo_url='https://example.org/manual-logo.png')
        system = Computer(manufacturer=itt, model_name='Synthetic XTRA', description='Scheda curata.')
        db.add_all([itt, terco, person, namesake, timex, manual_logo, system]); db.commit()
        mid = itt.id
        computers_before = db.scalar(select(func.count()).select_from(Computer))
        result = apply_enrichment(db, path=SUPPLEMENT, explicit=True)
        assert result['matched'] == 4 and result['updated'] == 3
        for item in (itt, terco, person, namesake, timex, manual_logo, system): db.refresh(item)
        assert itt.description == 'Testo rivisto a mano.' and itt.description_author is None
        assert itt.logo_url == rows[itt.name]['fields']['logo_url']
        assert history in itt.sources
        assert {source.url for source in itt.sources} == {
            history.url, rows[itt.name]['fields']['logo_source_url']}
        # XTRA's technical article must not be linked as support for the
        # existing independently curated description, which was not applied.
        assert 'https://www.1000bit.it/scheda.asp?id=788' not in {s.url for s in itt.sources}
        assert terco.website == 'https://example.org/curated'
        assert terco.founded.year == 1963 and terco.founded_precision == 'year'
        assert person.description and person.logo_url is None and person.founded is None
        assert namesake.description is None and namesake.logo_url is None
        assert timex.logo_url is None
        assert manual_logo.logo_url == 'https://example.org/manual-logo.png' and manual_logo.logo_author is None
        assert not manual_logo.sources
        assert system.manufacturer_id == mid and system.description == 'Scheda curata.'
        for link in db.execute(select(manufacturer_source).where(manufacturer_source.c.target_id == mid)).mappings():
            if link['source_id'] != history.id:
                assert link['verification_status'] == 'pending'
                assert all(field.startswith('logo_') for field in json.loads(link['evidence'])['fields'])
        source_count = db.scalar(select(func.count()).select_from(Source)); db.commit()
        assert apply_enrichment(db, path=SUPPLEMENT, explicit=True)['updated'] == 0
        assert db.scalar(select(func.count()).select_from(Source)) == source_count
        assert db.scalar(select(func.count()).select_from(Computer)) == computers_before
    profile = client.get(f'/api/manufacturers/{mid}/profile').json()
    assert profile['description'] == 'Testo rivisto a mano.'
    assert profile['logo_source_url'] == rows['ITT Information Systems']['fields']['logo_source_url']
    assert profile['computer_count'] == 1
