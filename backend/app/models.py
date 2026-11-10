from datetime import date, datetime, timezone
from sqlalchemy import String, Integer, Float, Boolean, Date, DateTime, ForeignKey, Text, UniqueConstraint, CheckConstraint, Table, Column
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase): pass
computer_category = Table('computer_category', Base.metadata, Column('computer_id', ForeignKey('computers.id',ondelete='CASCADE'),primary_key=True),Column('category_id',ForeignKey('categories.id',ondelete='CASCADE'),primary_key=True))

def link_table(name, target):
 return Table(name,Base.metadata,Column('source_id',ForeignKey('sources.id',ondelete='CASCADE'),primary_key=True),Column('target_id',ForeignKey(f'{target}.id',ondelete='CASCADE'),primary_key=True),Column('evidence',Text),Column('verification_status',String(20),nullable=False,server_default='pending'))
computer_source=link_table('computer_sources','computers')
spec_source=link_table('specification_sources','specifications')
release_source=link_table('release_sources','releases')
sale_source=link_table('sale_sources','sales')
review_source=link_table('review_sources','reviews')
fact_source=link_table('fact_sources','facts')

class Manufacturer(Base):
 __tablename__='manufacturers'
 id:Mapped[int]=mapped_column(primary_key=True)
 name:Mapped[str]=mapped_column(String(160),unique=True,index=True)
 country:Mapped[str|None]=mapped_column(String(100))
 founded:Mapped[date|None]=mapped_column(Date)
 website:Mapped[str|None]=mapped_column(String(500))
class Category(Base):
 __tablename__='categories'
 id:Mapped[int]=mapped_column(primary_key=True)
 name:Mapped[str]=mapped_column(String(100),unique=True)
 description:Mapped[str|None]=mapped_column(Text)
class Computer(Base):
 __tablename__='computers'
 id:Mapped[int]=mapped_column(primary_key=True)
 manufacturer_id:Mapped[int]=mapped_column(ForeignKey('manufacturers.id'))
 model_name:Mapped[str]=mapped_column(String(180),index=True)
 description:Mapped[str|None]=mapped_column(Text)
 announcement_date:Mapped[date|None]=mapped_column(Date)
 announcement_precision:Mapped[str|None]=mapped_column(String(12))
 image_url:Mapped[str|None]=mapped_column(String(800))  # Campo legacy, compatibilità con vecchi database
 images=relationship('ComputerImage',back_populates='computer',cascade='all,delete-orphan',order_by='ComputerImage.display_order')
 manufacturer=relationship('Manufacturer')
 categories=relationship('Category',secondary=computer_category)
 configurations=relationship('Configuration',back_populates='computer',cascade='all,delete-orphan')
 releases=relationship('Release',back_populates='computer',cascade='all,delete-orphan')
 sales=relationship('Sale',back_populates='computer',cascade='all,delete-orphan')
 reviews=relationship('Review',back_populates='computer',cascade='all,delete-orphan')
 facts=relationship('Fact',back_populates='computer',cascade='all,delete-orphan')
 sources=relationship('Source',secondary=computer_source)
class Configuration(Base):
 __tablename__='configurations'
 __table_args__=(UniqueConstraint('computer_id','variant_name'),)
 id:Mapped[int]=mapped_column(primary_key=True)
 computer_id:Mapped[int]=mapped_column(ForeignKey('computers.id',ondelete='CASCADE'))
 variant_name:Mapped[str]=mapped_column(String(140))
 description:Mapped[str|None]=mapped_column(Text)
 computer=relationship('Computer',back_populates='configurations')
 specifications=relationship('Specification',back_populates='configuration',cascade='all,delete-orphan')
class Specification(Base):
 __tablename__='specifications'
 __table_args__=(CheckConstraint('(numeric_value IS NOT NULL) <> (text_value IS NOT NULL)','one_spec_value'),)
 id:Mapped[int]=mapped_column(primary_key=True)
 configuration_id:Mapped[int]=mapped_column(ForeignKey('configurations.id',ondelete='CASCADE'))
 component_type:Mapped[str]=mapped_column(String(80))
 component_name:Mapped[str|None]=mapped_column(String(160))
 property_name:Mapped[str]=mapped_column(String(120))
 numeric_value:Mapped[float|None]=mapped_column(Float)
 text_value:Mapped[str|None]=mapped_column(Text)
 unit:Mapped[str|None]=mapped_column(String(30))
 configuration=relationship('Configuration',back_populates='specifications')
 sources=relationship('Source',secondary=spec_source)
class Market(Base):
 __tablename__='markets'
 id:Mapped[int]=mapped_column(primary_key=True)
 name:Mapped[str]=mapped_column(String(130),unique=True)
 country:Mapped[str|None]=mapped_column(String(100))
 region:Mapped[str|None]=mapped_column(String(100))
class Release(Base):
 __tablename__='releases'
 __table_args__=(CheckConstraint('price IS NULL OR price >= 0','positive_price'),)
 id:Mapped[int]=mapped_column(primary_key=True)
 computer_id:Mapped[int]=mapped_column(ForeignKey('computers.id',ondelete='CASCADE'))
 market_id:Mapped[int]=mapped_column(ForeignKey('markets.id'))
 release_date:Mapped[date|None]=mapped_column(Date)
 release_precision:Mapped[str|None]=mapped_column(String(12))
 discontinuation_date:Mapped[date|None]=mapped_column(Date)
 discontinuation_precision:Mapped[str|None]=mapped_column(String(12))
 price:Mapped[float|None]=mapped_column(Float)
 currency:Mapped[str|None]=mapped_column(String(3))
 price_type:Mapped[str|None]=mapped_column(String(30))
 computer=relationship('Computer',back_populates='releases')
 market=relationship('Market')
 sources=relationship('Source',secondary=release_source)
class Sale(Base):
 __tablename__='sales'
 __table_args__=(CheckConstraint('units_sold IS NULL OR units_sold >= 0','positive_sales'),CheckConstraint('period_end IS NULL OR period_start IS NULL OR period_end >= period_start','valid_period'))
 id:Mapped[int]=mapped_column(primary_key=True)
 computer_id:Mapped[int]=mapped_column(ForeignKey('computers.id',ondelete='CASCADE'))
 market_id:Mapped[int]=mapped_column(ForeignKey('markets.id'))
 period_start:Mapped[date|None]=mapped_column(Date)
 period_end:Mapped[date|None]=mapped_column(Date)
 units_sold:Mapped[int|None]=mapped_column(Integer)
 metric_type:Mapped[str]=mapped_column(String(30),default='units_sold')
 estimated:Mapped[bool]=mapped_column(Boolean,default=False)
 computer=relationship('Computer',back_populates='sales')
 market=relationship('Market')
 sources=relationship('Source',secondary=sale_source)
class Review(Base):
 __tablename__='reviews'
 __table_args__=(CheckConstraint('score IS NULL OR (max_score > 0 AND score >= 0 AND score <= max_score)','valid_score'),)
 id:Mapped[int]=mapped_column(primary_key=True)
 computer_id:Mapped[int]=mapped_column(ForeignKey('computers.id',ondelete='CASCADE'))
 publication:Mapped[str]=mapped_column(String(160))
 review_date:Mapped[date|None]=mapped_column(Date)
 score:Mapped[float|None]=mapped_column(Float)
 max_score:Mapped[float|None]=mapped_column(Float)
 summary:Mapped[str|None]=mapped_column(Text)
 computer=relationship('Computer',back_populates='reviews')
 sources=relationship('Source',secondary=review_source)
class Fact(Base):
 __tablename__='facts'
 id:Mapped[int]=mapped_column(primary_key=True)
 computer_id:Mapped[int]=mapped_column(ForeignKey('computers.id',ondelete='CASCADE'))
 fact_type:Mapped[str]=mapped_column(String(60))
 statement:Mapped[str]=mapped_column(Text)
 reference_date:Mapped[date|None]=mapped_column(Date)
 computer=relationship('Computer',back_populates='facts')
 sources=relationship('Source',secondary=fact_source)
class Source(Base):
 __tablename__='sources'
 id:Mapped[int]=mapped_column(primary_key=True)
 title:Mapped[str]=mapped_column(String(300))
 author:Mapped[str|None]=mapped_column(String(180))
 publisher:Mapped[str|None]=mapped_column(String(180))
 url:Mapped[str|None]=mapped_column(String(800))
 source_type:Mapped[str]=mapped_column(String(60),default='website')
 publication_date:Mapped[date|None]=mapped_column(Date)
 access_date:Mapped[date|None]=mapped_column(Date)

class ComputerImage(Base):
 __tablename__='computer_images'
 __table_args__=(CheckConstraint('(remote_url IS NOT NULL AND local_filename IS NULL) OR (remote_url IS NULL AND local_filename IS NOT NULL)',name='image_exactly_one_location'),)
 id:Mapped[int]=mapped_column(primary_key=True)
 computer_id:Mapped[int]=mapped_column(ForeignKey('computers.id',ondelete='CASCADE'),index=True)
 remote_url:Mapped[str|None]=mapped_column(String(1600))
 thumbnail_url:Mapped[str|None]=mapped_column(String(1600))
 local_filename:Mapped[str|None]=mapped_column(String(120),unique=True)
 caption:Mapped[str|None]=mapped_column(String(300))
 author:Mapped[str|None]=mapped_column(String(350))
 license_name:Mapped[str|None]=mapped_column(String(160))
 license_url:Mapped[str|None]=mapped_column(String(800))
 source_url:Mapped[str|None]=mapped_column(String(1600))
 is_primary:Mapped[bool]=mapped_column(Boolean,nullable=False,default=False)
 display_order:Mapped[int]=mapped_column(Integer,nullable=False,default=0)
 created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc),nullable=False)
 computer=relationship('Computer',back_populates='images')
