"""Synthetic statements; no claim of live Wikidata access or historical verification."""
import json
import pytest
from app.importing.providers import wikidata_records,fetch_provider
from app.importing.normalize import Record


def statement(value,**extra):return {'mainsnak':{'datavalue':{'value':value}},**extra}


def payload():
    return {'requested_ids':['Q1'],'entities':{
        'Q1':{'labels':{'en':{'value':'Synthetic System'}},'descriptions':{'it':{'value':'Calcolatore sintetico per test'}},'claims':{
            'P176':[statement({'id':'Q2'})],'P880':[statement({'id':'Q3'})],'P306':[statement({'id':'Q4'})],
            'P2284':[statement({'amount':'+1234','unit':'http://www.wikidata.org/entity/Q5'},id='Q1$price')]}},
        'Q2':{'labels':{'en':{'value':'Synthetic maker'}}},'Q3':{'labels':{'en':{'value':'Synthetic CPU'}}},
        'Q4':{'labels':{'en':{'value':'Synthetic OS'}}},
        'Q5':{'labels':{'en':{'value':'Synthetic currency'}},'claims':{'P498':[statement('USD')]}}
    }}


def test_resolved_single_price_cpu_os_and_italian_prose():
    row=wikidata_records(payload())[0];Record.model_validate(row)
    assert row['description']=='Calcolatore sintetico per test'
    assert row['releases']==[{'market':'Non specificato dalla fonte','price':1234.0,'currency':'USD','price_type':'prezzo riportato',
        'source':row['source'],'evidence':row['releases'][0]['evidence']}]
    assert 'release_date' not in row['releases'][0]
    specs=row['configurations'][0]['specifications']
    assert [s['text_value'] for s in specs]==['Synthetic CPU','Synthetic OS']
    assert all(s['source']['license']=='CC0' for s in specs)
    data=payload();data['entities']['Q3']['labels']['en']['value']='6800 CPU'
    parsed=Record.model_validate(wikidata_records(data)[0])
    assert parsed.configurations[0].specifications[0].text_value=='6800 CPU'
    data['entities']['Q1']['claims']['P880'].append(statement({'id':'Q7'}))
    data['entities']['Q7']={'labels':{'en':{'value':'Alternative CPU'}}}
    parsed=Record.model_validate(wikidata_records(data)[0])
    cpus=[s for s in parsed.configurations[0].specifications if s.component_type=='CPU']
    assert len(cpus)==1 and cpus[0].text_value=='6800 CPU / Alternative CPU'


@pytest.mark.parametrize('mode',['qualified','multiple','unresolved_currency'])
def test_scoped_or_unresolved_prices_remain_sourced_context_not_launch_prices(mode):
    data=payload();claims=data['entities']['Q1']['claims']
    if mode=='qualified':claims['P2284'][0]['qualifiers']={'P585':[{'datavalue':{'value':{'time':'+2000-01-01T00:00:00Z'}}}]}
    if mode=='multiple':claims['P2284'].append(statement({'amount':'+1500','unit':'http://www.wikidata.org/entity/Q5'},id='Q1$other-price'))
    if mode=='unresolved_currency':data['entities']['Q5']['claims']={}
    row=wikidata_records(data)[0];Record.model_validate(row)
    assert 'releases' not in row and row['facts']
    assert all('non classificato come prezzo di lancio' in f['statement'] and f['source']['license']=='CC0' for f in row['facts'])


def test_unknown_memory_property_definition_is_not_assumed_and_units_are_preserved():
    data=payload();e=data['entities'];e['Q1']['claims']['P2928']=[statement({'amount':'+4','unit':'http://www.wikidata.org/entity/Q6'})]
    e['Q6']={'labels':{'en':{'value':'KiB'}}};e['P2928']={'labels':{'en':{'value':'Some other property'}}}
    assert not any(s['component_type']=='RAM' for s in wikidata_records(data)[0]['configurations'][0]['specifications'])
    e['P2928']['labels']['en']['value']='memory capacity'
    row=wikidata_records(data)[0];ram=next(s for s in row['configurations'][0]['specifications'] if s['component_type']=='RAM')
    assert ram['numeric_value']==4 and ram['unit']=='KiB'


def test_deprecated_and_nonfinite_prices_never_imported():
    for changes in [{'rank':'deprecated'},{}]:
        data=payload();claim=data['entities']['Q1']['claims']['P2284'][0];claim.update(changes)
        if not changes:claim['mainsnak']['datavalue']['value']['amount']='NaN'
        row=wikidata_records(data)[0]
        assert not row.get('releases') and not row.get('facts')


def test_fetch_resolves_linked_currency_claims_without_inventing_codes(monkeypatch):
    import app.importing.providers as module
    data=payload();seen=[]
    def get_json(url,params):
        assert url=='https://www.wikidata.org/w/api.php' and params['maxlag']=='5'
        ids=params['ids'].split('|');seen.append(ids)
        result={'entities':{qid:data['entities'][qid] for qid in ids}}
        return json.dumps(result).encode(),result
    monkeypatch.setattr(module,'get_json',get_json)
    raw,rows=fetch_provider('wikidata',{'ids':['Q1']})
    assert rows[0]['releases'][0]['currency']=='USD'
    assert len(seen)==2 and set(seen[1])=={'Q2','Q3','Q4','Q5'}
    assert 'Q5' in json.loads(raw)['entities']
