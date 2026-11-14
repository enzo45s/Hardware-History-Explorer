"""Build a bounded, licensed enrichment snapshot. Never writes to the database."""
import argparse
from datetime import date
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from app.importing.identity import computer_key
from app.importing.normalize import Record

MAME='758c8a169a44f0ce3abfd28e8b5c44cc49148eba'
APPLE='5fb98e557f544b7ed783e7855e78c9db9d05ee57'


def blob(root,rev,path):
    return subprocess.check_output(['git','-C',str(root),'show',f'{rev}:{path}']).decode()


def prepare(mame,apple,output,xml=None):
    catalog=json.loads((Path(__file__).resolve().parents[1]/'docs/datasets/mame-0276/manifest.json').read_text(encoding='utf-8'))['index']
    models={computer_key(r['manufacturer'],r['model_name']):r for r in catalog}
    entries={};files={};today=date.today().isoformat()
    def entry(maker,name,citation,original):
        key=computer_key(maker,name)
        if key not in models:return None
        if key not in entries:
            target=models[key]
            entries[key]={'manufacturer':target['manufacturer'],'model_name':target['model_name'],'source':citation,
                          'configurations':[],'releases':[],'facts':[],'evidence':'Fonti secondarie; sintesi italiana HHE. Nessuna verifica storica automatica.'}
        originals.setdefault(key,[]).append(original)
        return entries[key]
    def cite(repo,rev,path,title,start=None):
        text=blob(mame if repo=='mamedev/mame' else apple,rev,path)
        files[repo+'/'+path]={'repository':repo,'revision':rev,'path':path,'sha256':hashlib.sha256(text.encode()).hexdigest(),
                              'copyright_and_license_header':'\n'.join(text.splitlines()[:4]) if repo=='mamedev/mame' else 'MIT — Copyright (c) 2022 emiyl'}
        return {'title':title,'url':f'https://github.com/{repo}/blob/{rev}/{path}'+(f'#L{start}' if start else ''),
                'publisher':'MAME' if repo=='mamedev/mame' else 'AppleDB','license':'BSD-3-Clause' if repo=='mamedev/mame' else 'MIT','access_date':today}
    originals={}
    paths=subprocess.check_output(['git','-C',str(apple),'ls-tree','-r','--name-only',APPLE,'deviceFiles']).decode().splitlines()
    computer_folders={'Macintosh','iMac','PowerMac','PowerBook','Mac Pro','Mac mini','Mac Studio','Macbook','Macbook Pro','Macbook Air','eMac','iBook'}
    for path in paths:
        if not path.endswith('.json') or path.split('/')[1] not in computer_folders:continue
        data=json.loads(blob(apple,APPLE,path))
        if data.get('internal') or not isinstance(data.get('name'),str):continue
        if computer_key('Apple',data['name']) not in models:continue
        citation=cite('littlebyteorg/appledb',APPLE,path,'AppleDB — '+data['name'])
        record=entry('Apple',data['name'],citation,{'path':path,'data':data})
        specs=[]
        for field,component,prop in [('model','Sistema','Codice modello'),('identifier','Sistema','Identificativo'),('arch','CPU','Architettura'),('soc','CPU','SoC riportato')]:
            values=data.get(field,[]);values=values if isinstance(values,list) else [values]
            values=list(dict.fromkeys(value for value in values if isinstance(value,str) and value))
            if values:specs.append({'component_type':component,'property_name':prop,'text_value':' / '.join(values),'source':citation,
                                    'evidence':f'Campo {field} del JSON originale AppleDB; valori alternativi conservati insieme. Originale nello snapshot.'})
        if specs:record['configurations'].append({'variant_name':'AppleDB · Identificativi e architettura','source':citation,'specifications':specs})
        released=data.get('released');discontinued=data.get('discontinued')
        if isinstance(released,str) and re.fullmatch(r'\d{4}(?:-\d{2}(?:-\d{2})?)?',released):
            release={'market':'Non specificato dalla fonte (AppleDB)','release_date':released,'source':citation,'evidence':'Campi released/discontinued AppleDB, non data di annuncio.'}
            if isinstance(discontinued,str) and re.fullmatch(r'\d{4}(?:-\d{2}(?:-\d{2})?)?',discontinued):release['discontinuation_date']=discontinued
            record['releases'].append(release)
        model=data.get('model');model=', '.join(model) if isinstance(model,list) else model
        record['description']=f"{record['model_name']} è un calcolatore Apple."
        if isinstance(released,str):record['description']+=f' AppleDB indica la data di rilascio {released}.'
        if model:record['description']+=f' Codice modello riportato: {model}.'
    def documented(maker,name,path,start,end,description,specs=None,variant='Documentazione tecnica MAME'):
        citation=cite('mamedev/mame',MAME,path,'MAME · Documentazione '+name,start)
        excerpt='\n'.join(blob(mame,MAME,path).splitlines()[start-1:end])
        record=entry(maker,name,citation,{'path':path,'start_line':start,'end_line':end,'excerpt':excerpt})
        if record is None:return None
        record['source']=citation
        record['evidence']='Sintesi italiana HHE dei commenti tecnici MAME, fonte secondaria da verificare. '+excerpt[:2600]
        record['description']=description
        if specs:
            record['configurations'].append({'variant_name':variant,'source':citation,'description':'Dati dai commenti tecnici del driver; non valori dedotti dal default emulato.',
                'specifications':[{**spec,'source':citation,'evidence':excerpt[:2900]} for spec in specs]})
        return record,citation,excerpt
    def spec(component,prop,value,unit=None):
        return {'component_type':component,'property_name':prop,**({'text_value':value} if isinstance(value,str) else {'numeric_value':value}),**({'unit':unit} if unit else {})}
    macs={'Macintosh 128K':128,'Macintosh 512K':512,'Macintosh 512ke':512,'Macintosh Plus':None,'Macintosh SE':None,'Macintosh SE (FDHD)':None,'Macintosh Classic':None}
    for name,ram in macs.items():
        specs=[spec('CPU','Modello','Motorola 68000'),spec('Video','Risoluzione riportata','512 × 342 pixel')]
        if ram:specs.append(spec('RAM','Capacità riportata',ram,'KB'))
        descriptions={
            'Macintosh Plus':('Macintosh compatto Apple con interfaccia SCSI, memoria espandibile tramite SIMM e unità floppy da 800 KB.',[spec('Archiviazione','Interfaccia','SCSI'),spec('RAM','Espansione','Slot SIMM'),spec('Floppy','Capacità riportata',800,'KB')]),
            'Macintosh SE':('Macintosh compatto Apple che introduce ADB per tastiera e mouse e uno slot di espansione rispetto al Macintosh Plus.',[spec('I/O','Interfaccia tastiera e mouse','ADB'),spec('Espansione','Slot riportati',1)]),
            'Macintosh SE (FDHD)':('Versione del Macintosh SE con controller SWIM e unità SuperDrive da 1,44 MB, distinta dal modello con floppy da 800 KB.',[spec('Floppy','Controller','SWIM'),spec('Floppy','Supporto riportato','1.44MB SuperDrive')]),
            'Macintosh 512ke':('Macintosh compatto Apple con 512 KB di RAM, floppy da 800 KB e ROM derivate dal Macintosh Plus.',[spec('Floppy','Capacità riportata',800,'KB')])}
        prose,extra=descriptions.get(name,(f'{name} è uno dei Macintosh compatti Apple basati su Motorola 68000, con video e audio della famiglia originale.',[]))
        documented('Apple',name,'src/mame/apple/mac128.cpp',8,91,prose,specs+extra)
    for name in ['Macintosh LC','Macintosh LC II','Macintosh Classic II','Macintosh Color Classic','Macintosh TV']:
        limit=8 if name=='Macintosh TV' else 10
        documented('Apple',name,'src/mame/apple/maclc.cpp',5,19,
            f'{name} appartiene alla famiglia Apple basata sul controller V8. La documentazione tecnica del driver indica un limite hardware di {limit} MB per la RAM.',
            [spec('Sistema','Controller riportato','V8'),spec('RAM','Limite hardware riportato',limit,'MB')])
    for name in ['Macintosh Quadra 700','Macintosh Quadra 900','Macintosh Quadra 950']:
        documented('Apple',name,'src/mame/apple/macquadra700.cpp',5,20,
            f'{name} è un Macintosh Apple con video ed Ethernet integrati e slot NuBus 90, descritto dalla documentazione tecnica come appartenente alla fascia workstation.',
            [spec('Rete','Interfaccia riportata','Ethernet integrata'),spec('Espansione','Bus riportato',"NuBus '90")])
    for name in ['Macintosh Quadra 630','Macintosh LC/Performa 580']:
        documented('Apple',name,'src/mame/apple/macquadra630.cpp',5,18,
            f'{name} utilizza il sottosistema video Valkyrie e un disco ATA/IDE al posto del tradizionale disco SCSI dei Macintosh precedenti.',
            [spec('Video','Chip riportato','Valkyrie'),spec('Archiviazione','Interfaccia riportata','ATA/IDE')])
    for name,slots,minram,maxram,drives in [('IBM PC 5150',5,16,64,'Unità floppy opzionali da 160 o 360 KB'),('IBM XT 5160',8,64,256,'Una unità floppy interna da 360 KB')]:
        documented('IBM',name,'src/mame/pc/ibmpc.cpp',24 if slots==5 else 44,39 if slots==5 else 62,
            f'{name} è un personal computer IBM con processore Intel 8088 a 4,77 MHz e {slots} slot ISA. Sono documentate più revisioni della scheda madre e diverse possibilità di espansione.',
            [spec('CPU','Modello','Intel 8088'),spec('CPU','Frequenza',4.77,'MHz'),spec('Espansione','Slot ISA riportati',slots),
             spec('RAM','Capacità minima riportata',minram,'KB'),spec('RAM','Capacità massima riportata',maxram,'KB'),spec('Floppy','Dotazione riportata',drives)],'Scheda madre revisione A · documentazione MAME')
    for model,month,amount,ram,hdd in [('010','1986-01',11700,'1M/4M','40M'),('015','1986-11',10050,'2M/4M','70M'),('020','1986-01',14945,'1M/4M','40M'),('025','1986-01',17940,'2M/4M','70M'),('A25','1986-01',19510,'2M/4M','70M')]:
        name='IBM RT PC Model '+model
        result=documented('IBM',name,'src/mame/ibm/rtpc.cpp',18,42,
            f'{name} è un sistema della famiglia IBM RT PC. La tabella tecnica riporta RAM {ram}, disco {hdd} e un prezzo di '+f'{amount:,}'.replace(',','.')+' dollari nel contesto degli annunci IBM per gli Stati Uniti.',
            [spec('CPU','Variante riportata','032 (SGP)'),spec('RAM','Dotazioni riportate',ram),spec('Archiviazione','Capacità riportata',hdd)])
        if result:
            record,citation,excerpt=result
            record['releases'].append({'market':'Stati Uniti','release_date':month,'price':amount,'currency':'USD','price_type':'prezzo riportato',
                'source':citation,'evidence':'Tabella secondaria MAME con rimandi agli annunci IBM ENUS (mercato USA); questi annunci non sono stati riletti. Valuta USD dal contesto ENUS, nessuna conversione. '+excerpt[:2100]})
    # Additional emulator metadata remains explicitly separate from historical specifications.
    corpus=Path(__file__).resolve().parents[1]/'docs/datasets/mame-0276'
    manifest=json.loads((corpus/'manifest.json').read_text(encoding='utf-8'))
    if xml:
        with xml.open('rb') as stream:
            if hashlib.file_digest(stream,'sha256').hexdigest()!=manifest['xml_sha256']:raise ValueError('XML diverso dall’export MAME registrato nel corpus')
        selected={};audit_files={}
        for batch in manifest['batches']:
            payload=json.loads((corpus/batch['file']).read_text(encoding='utf-8'))
            audits={r['model_id']:r for r in payload['_metadata']['original_records']}
            for item in payload['_metadata']['original_files']:audit_files[item['path']]=item
            for r in payload['records']:
                raw=audits[r['external_id']]['originals']
                assert len(raw)==len(r['configurations'])
                for cfg,original in zip(r['configurations'],raw):selected[original['shortname']]=(r,cfg)
        for event,node in ET.iterparse(xml,events=('end',)):
            if node.tag!='machine':continue
            name=node.get('name')
            if name in selected:
                r,cfg=selected[name];citation=cfg['source'];specs=[]
                raw={'machine':name,'display':[dict(d.attrib) for d in node.findall('display')],
                     'sound_chips':[dict(c.attrib) for c in node.findall('chip') if c.get('type')=='audio'],
                     'ram_options':[{'attributes':dict(v.attrib),'bytes':v.text or ''} for v in node.findall('ramoption')]}
                for d in raw['display']:
                    if d.get('width','').isdigit() and d.get('height','').isdigit():
                        specs.append({**spec('Video','Risoluzione emulata (MAME)',f"{d['width']} × {d['height']} pixel"),'component_name':d.get('tag')})
                    if re.fullmatch(r'\d+(?:\.\d+)?',d.get('refresh','')):
                        specs.append({**spec('Video','Frequenza video emulata (MAME)',float(d['refresh']),'Hz'),'component_name':d.get('tag')})
                # Do not present MAME's cassette/floppy noise, speakers, slots
                # and generic filters as additional physical sound chips.
                sound_names=sorted({chip['name'] for chip in raw['sound_chips'] if re.search(
                    r'^(?:YM\d|AY-|SN\d|MOS |Atari .*POKEY|Votrax |TMS\d|ASC$|Apple Digitally|LMC\d|OKI )',chip.get('name',''))})
                if sound_names:specs.append(spec('Audio','Chip audio emulati (MAME)','; '.join(sound_names)))
                ram=[int(o['bytes'])/1024 for o in raw['ram_options'] if re.fullmatch(r'\d{1,15}',o['bytes']) and int(o['bytes'])>0]
                if ram:specs.append(spec('RAM','Opzioni RAM emulatore (MAME)',' / '.join(f'{v:g} KiB' for v in sorted(set(ram)))))
                if specs:
                    record=entry(r['manufacturer'],r['model_name'],r['source'],{'xml_sha256':manifest['xml_sha256'],'metadata':raw})
                    proof=json.dumps({'xml_sha256':manifest['xml_sha256'],'metadata':raw,'note':'Configurazione emulata, non attestazione della dotazione commerciale.'},ensure_ascii=False)
                    record['configurations'].append({'variant_name':cfg['variant_name'],'source':citation,'evidence':proof[:2900],
                        'specifications':[{**s,'source':citation} for s in specs]})
            node.clear()
    else:audit_files={}
    records=list(entries.values())
    for r in records:Record.model_validate(r)
    result={'version':'catalog-enrichment-v1','prepared_on':today,
        'metadata':{'sources':list(files.values()),'emulator_files':list(audit_files.values()),'licenses':{**manifest['licenses'],'AppleDB-MIT':blob(apple,APPLE,'LICENSE')},
          'limitations':['Fonti secondarie, tutte le asserzioni restano da verificare.','Solo modelli esistenti corrispondenti: nessun nuovo sistema.',
             'Cinque prezzi IBM RT da tabella MAME; USD dal contesto degli annunci ENUS, non conversione o verifica dei documenti primari.'],
          'originals':[{'manufacturer':r['manufacturer'],'model_name':r['model_name'],'records':originals[k]} for k,r in entries.items()]},
        'records':records}
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    output.chmod(0o644)
    print(json.dumps({'records':len(records),'configurations':sum(len(r['configurations']) for r in records),'specifications':sum(len(v['specifications']) for r in records for v in r['configurations']),
      'prices':sum(x.get('price') is not None for r in records for x in r['releases']),'releases':sum(len(r['releases']) for r in records),'bytes':output.stat().st_size}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mame',type=Path,required=True);parser.add_argument('--appledb',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--xml',type=Path)
    args=parser.parse_args();prepare(args.mame,args.appledb,args.output,args.xml)
