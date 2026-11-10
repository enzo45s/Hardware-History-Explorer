from datetime import date
from sqlalchemy import select
from sqlalchemy.orm import Session
from .models import Manufacturer,Category,Computer,Configuration,Specification,Market,Release,Fact,Source

# Esempi dimostrativi: valori indicativi, non un corpus verificato.
DATA=[
 ('IBM','IBM System/360','Mainframe',1964,'Famiglia di mainframe che ha segnato la standardizzazione delle architetture aziendali.', [('CPU','Architettura','32-bit')]),
 ('MITS','Altair 8800','Microcomputer',1975,'Kit di microcomputer basato su Intel 8080.', [('CPU','Modello','Intel 8080'),('RAM','Capacità',256,'B')]),
 ('Apple','Apple II','Home computer',1977,'Computer domestico a 8 bit con ampia diffusione nel mercato educativo.', [('CPU','Modello','MOS 6502'),('CPU','Frequenza',1.0,'MHz')]),
 ('Commodore','Commodore 64','Home computer',1982,'Home computer a 8 bit noto per grafica e audio.', [('CPU','Modello','MOS 6510'),('RAM','Capacità',64,'KB')]),
 ('IBM','IBM PC 5150','Personal computer',1981,'Personal computer IBM che ha influenzato l’ecosistema PC compatibile.', [('CPU','Modello','Intel 8088'),('CPU','Frequenza',4.77,'MHz')]),
 ('Apple','Macintosh 128K','Personal computer',1984,'Personal computer con interfaccia grafica e mouse.', [('CPU','Modello','Motorola 68000'),('RAM','Capacità',128,'KB')]),
 ('Sun Microsystems','Sun-1','Workstation',1982,'Prima famiglia di workstation Sun.', [('CPU','Modello','Motorola 68000')]),
 ('Compaq','Compaq Portable','Portable',1983,'Computer trasportabile compatibile con l’ecosistema IBM PC.', [('CPU','Modello','Intel 8088')]),
 ('Cray Research','Cray-1','Supercomputer',1976,'Supercomputer vettoriale per calcolo scientifico.', [('CPU','Architettura','Vettoriale')]),
 ('Digital Equipment Corporation','PDP-11','Minicomputer',1970,'Famiglia di minicomputer a 16 bit.', [('CPU','Architettura','16-bit')]),
]
def seed(db:Session):
 if db.scalar(select(Computer.id).limit(1)) is not None:return
 world=Market(name='Globale',region='Globale'); db.add(world)
 makers={};cats={}
 for brand,model,category,year,description,specs in DATA:
  if brand not in makers:
   makers[brand]=Manufacturer(name=brand);db.add(makers[brand])
  if category not in cats:
   cats[category]=Category(name=category);db.add(cats[category])
  c=Computer(manufacturer=makers[brand],model_name=model,description=description,categories=[cats[category]])
  cfg=Configuration(variant_name='Configurazione rappresentativa',computer=c)
  for item in specs:
   typ,prop,value,*unit=item
   cfg.specifications.append(Specification(component_type=typ,property_name=prop,numeric_value=float(value) if isinstance(value,(int,float)) else None,text_value=value if isinstance(value,str) else None,unit=unit[0] if unit else None))
  c.releases.append(Release(market=world,release_date=date(year,1,1),release_precision='year',price_type='launch'))
  db.add(c)
 db.commit()
