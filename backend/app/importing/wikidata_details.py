"""Optional sourced details; qualified prices never become invented launch prices."""
from decimal import Decimal, InvalidOperation
import json
import re

LINKED_PROPERTIES=('P176','P880','P306','P2284','P2067','P2048','P2049','P2928')


def linked_ids(entities):
    ids=set()
    for entity in entities.values():
        for prop in LINKED_PROPERTIES:
            for s in entity.get('claims',{}).get(prop,[]):
                value=s.get('mainsnak',{}).get('datavalue',{}).get('value',{})
                if isinstance(value,dict):
                    if re.fullmatch(r'Q[1-9]\d*',value.get('id','')):ids.add(value['id'])
                    match=re.fullmatch(r'https?://www.wikidata.org/entity/(Q[1-9]\d*)',value.get('unit',''))
                    if match:ids.add(match[1])
            if prop=='P2928' and entity.get('claims',{}).get(prop):ids.add(prop)
    return ids


def amount(value):
    try:
        n=Decimal(str(value))
        return float(n) if n.is_finite() and 0<=n<=Decimal('1e100') else None
    except (InvalidOperation,ValueError,TypeError):return None


def augment(row,entity,entities,active,label):
    citation=row['source']
    def proof(statement):return json.dumps(statement,ensure_ascii=False)[:2900]
    prose=entity.get('descriptions',{}).get('it',{}).get('value')
    if isinstance(prose,str) and prose.strip():row['description']=prose.strip()
    specs=[]
    for prop,component,property_name in [('P880','CPU','Modello riportato (Wikidata)'),('P306','Sistema operativo','Nome riportato (Wikidata)')]:
        values=[];statements=[]
        for s in active(entity,prop):
            qid=s.get('mainsnak',{}).get('datavalue',{}).get('value',{}).get('id')
            name=label(entities.get(qid,{}))
            if name:values.append(name);statements.append(s)
        if values:specs.append({'component_type':component,'property_name':property_name,'text_value':' / '.join(dict.fromkeys(values)),
                               'source':citation,'evidence':proof(statements)})
    quantities=[('P2067','Fisico','Massa riportata (Wikidata)'),('P2048','Fisico','Altezza riportata (Wikidata)'),('P2049','Fisico','Larghezza riportata (Wikidata)')]
    # Verify this less-common property definition from the live payload itself.
    if entities.get('P2928',{}).get('labels',{}).get('en',{}).get('value','').casefold()=='memory capacity':
        quantities.append(('P2928','RAM','Capacità riportata (Wikidata)'))
    for prop,component,property_name in quantities:
        values=[]
        for s in active(entity,prop):
            value=s.get('mainsnak',{}).get('datavalue',{}).get('value',{})
            if not isinstance(value,dict):continue
            number=amount(value.get('amount'))
            match=re.fullmatch(r'https?://www.wikidata.org/entity/(Q[1-9]\d*)',value.get('unit',''))
            unit=label(entities.get(match[1],{})) if match else None
            if number is not None and unit and len(unit)<=30:
                values.append((s,value,number,unit))
        if len(values)==1 and not values[0][0].get('qualifiers'):
            s,value,number,unit=values[0]
            specs.append({'component_type':component,'property_name':property_name,'numeric_value':number,'unit':unit,
                          'source':citation,'evidence':proof(s),'estimated':any(value.get(k) is not None for k in ('lowerBound','upperBound'))})
        elif values:
            row.setdefault('facts',[]).extend({'fact_type':'Misura contestuale (Wikidata)','statement':f'{property_name}: {number:g} {unit}. Ambito e qualificatori da controllare nello statement {s.get("id", "")}.',
                                             'source':citation,'evidence':proof(s)} for s,value,number,unit in values)
    if specs:
        row['configurations']=[{'variant_name':'Wikidata · Dotazioni riportate','description':'Elenco delle dotazioni dichiarate negli statement, non attestazione di una singola configurazione ordinabile.',
                               'source':citation,'specifications':specs[:200]}]
    prices=[]
    for s in active(entity,'P2284'):
        value=s.get('mainsnak',{}).get('datavalue',{}).get('value',{})
        if not isinstance(value,dict):continue
        number=amount(value.get('amount'))
        if number is None:continue
        match=re.fullmatch(r'https?://www.wikidata.org/entity/(Q[1-9]\d*)',value.get('unit',''))
        currency=entities.get(match[1],{}) if match else {}
        values=[x.get('mainsnak',{}).get('datavalue',{}).get('value') for x in active(currency,'P498')]
        codes={code for code in values if isinstance(code,str) and re.fullmatch(r'[A-Z]{3}',code)}
        prices.append((s,number,next(iter(codes)) if len(codes)==1 else None))
    if len(prices)==1 and not prices[0][0].get('qualifiers') and prices[0][2]:
        statement,number,currency=prices[0]
        release=(row.get('releases') or [{'market':'Non specificato dalla fonte'}])[0]
        release.update(price=number,currency=currency,price_type='prezzo riportato',source=citation,
                       evidence='P2284 non qualificato; non è attestato come prezzo di lancio o MSRP. '+proof(statement))
        row['releases']=[release]
    elif prices:
        # The current Release schema cannot express configuration/date scopes
        # on arbitrary price statements without changing their meaning.
        row.setdefault('facts',[]).extend([{'fact_type':'Prezzo contestuale (Wikidata)',
                      'statement':f"Prezzo riportato: {number:g} {currency or ('(valuta non risolta: '+str(s.get('mainsnak',{}).get('datavalue',{}).get('value',{}).get('unit',''))+')')}. Ambito e qualificatori da controllare nello statement originale {s.get('id','')}; non classificato come prezzo di lancio.",
                      'source':citation,'evidence':proof(s)} for s,number,currency in prices[:100]])
