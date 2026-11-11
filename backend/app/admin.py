"""Local single-user catalog editing, sharing the existing relational schema."""
from datetime import date
from uuid import uuid4
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .models import Category, Computer, Configuration, Manufacturer, Market, Release, Source, Specification

PositiveID = Annotated[int, Field(gt=0)]
IDs = Annotated[list[PositiveID], Field(max_length=500)]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=180)]


def historical_date(value):
    """Keep unknown dates unknown and preserve year/month/day precision."""
    if value is None:
        return None, None
    if not isinstance(value, str):
        raise ValueError('Usa AAAA, AAAA-MM oppure AAAA-MM-GG')
    try:
        parts = value.split('-')
        if [len(p) for p in parts] not in ([4], [4, 2], [4, 2, 2]) or not all(p.isascii() and p.isdigit() for p in parts):
            raise ValueError()
        parsed = date(int(parts[0]), int(parts[1]) if len(parts) > 1 else 1, int(parts[2]) if len(parts) > 2 else 1)
    except (ValueError, TypeError) as exc:
        raise ValueError('Data non valida: usa AAAA, AAAA-MM oppure AAAA-MM-GG') from exc
    return parsed, ('year', 'month', 'day')[len(parts) - 1]


class Input(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True, allow_inf_nan=False)


class SpecificationInput(Input):
    id: PositiveID | None = None
    component_type: str = Field(min_length=1, max_length=80)
    component_name: str | None = Field(default=None, max_length=160)
    property_name: str = Field(min_length=1, max_length=120)
    numeric_value: float | None = None
    text_value: str | None = Field(default=None, min_length=1, max_length=10000)
    unit: str | None = Field(default=None, max_length=30)
    source_ids: IDs | None = None

    @model_validator(mode='after')
    def one_value(self):
        if (self.numeric_value is None) == (self.text_value is None):
            raise ValueError('Ogni specifica richiede un valore numerico oppure un valore testuale')
        return self


class ConfigurationInput(Input):
    id: PositiveID | None = None
    variant_name: str = Field(min_length=1, max_length=140)
    description: str | None = Field(default=None, max_length=10000)
    specifications: list[SpecificationInput] = Field(default_factory=list, max_length=500)


class ReleaseInput(Input):
    id: PositiveID | None = None
    market_id: PositiveID
    release_date: str | None = None
    discontinuation_date: str | None = None
    price: float | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, pattern=r'^[A-Z]{3}$')
    price_type: str | None = Field(default=None, max_length=30)
    source_ids: IDs | None = None

    @field_validator('release_date', 'discontinuation_date')
    @classmethod
    def valid_date(cls, value):
        historical_date(value)
        return value

    @model_validator(mode='after')
    def valid_period(self):
        start, _ = historical_date(self.release_date)
        end, _ = historical_date(self.discontinuation_date)
        if start and end:
            # A year/month end denotes a range, not its first day.
            end_upper = date(end.year, 12, 31) if len(self.discontinuation_date) == 4 else end
            if len(self.discontinuation_date) == 7:
                from calendar import monthrange
                end_upper = date(end.year, end.month, monthrange(end.year, end.month)[1])
            if start > end_upper:
                raise ValueError('La fine della commercializzazione precede il lancio')
        return self


class ComputerInput(Input):
    model_name: Name
    manufacturer_id: PositiveID
    description: str | None = Field(default=None, max_length=20000)
    announcement_date: str | None = None
    category_ids: IDs | None = None
    source_ids: IDs | None = None
    configurations: list[ConfigurationInput] | None = Field(default=None, max_length=100)
    releases: list[ReleaseInput] | None = Field(default=None, max_length=100)

    @field_validator('announcement_date')
    @classmethod
    def valid_date(cls, value):
        historical_date(value)
        return value

    @model_validator(mode='after')
    def unique_rows(self):
        def unique_ids(rows):
            ids = [r.id for r in rows if r.id is not None]
            if len(ids) != len(set(ids)):
                raise ValueError('Lo stesso elemento compare più volte')
        unique_ids(self.releases or [])
        unique_ids(self.configurations or [])
        names = [r.variant_name for r in self.configurations or []]
        if len(names) != len(set(names)):
            raise ValueError('I nomi delle configurazioni devono essere diversi')
        for config in self.configurations or []:
            unique_ids(config.specifications)
        return self


class ReferenceInput(Input):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


def references(db, model, ids):
    ordered = list(dict.fromkeys(ids))
    rows = {r.id: r for r in db.scalars(select(model).where(model.id.in_(ordered)))}
    if len(rows) != len(ordered):
        raise HTTPException(422, f'Riferimenti inesistenti: {model.__tablename__}')
    return [rows[i] for i in ordered]


def date_text(value, precision):
    if value is None:
        return None
    return str(value.year).zfill(4) if precision == 'year' else f'{value.year:04d}-{value.month:02d}' if precision == 'month' else value.isoformat()


def editable(c):
    return {
        'id': c.id, 'model_name': c.model_name, 'manufacturer_id': c.manufacturer_id,
        'description': c.description, 'announcement_date': date_text(c.announcement_date, c.announcement_precision),
        'category_ids': [r.id for r in c.categories], 'source_ids': [r.id for r in c.sources],
        'releases': [{
            'id': r.id, 'market_id': r.market_id, 'release_date': date_text(r.release_date, r.release_precision),
            'discontinuation_date': date_text(r.discontinuation_date, r.discontinuation_precision),
            'price': r.price, 'currency': r.currency, 'price_type': r.price_type, 'source_ids': [s.id for s in r.sources]
        } for r in sorted(c.releases, key=lambda r: r.id)],
        'configurations': [{
            'id': cfg.id, 'variant_name': cfg.variant_name, 'description': cfg.description,
            'specifications': [{
                'id': s.id, 'component_type': s.component_type, 'component_name': s.component_name,
                'property_name': s.property_name, 'numeric_value': s.numeric_value,
                'text_value': s.text_value, 'unit': s.unit, 'source_ids': [r.id for r in s.sources]
            } for s in sorted(cfg.specifications, key=lambda s: s.id)]
        } for cfg in sorted(c.configurations, key=lambda cfg: cfg.id)]
    }


def apply_computer(db, c, data):
    """Resolve every reference before applying changes; a failed save is atomic."""
    manufacturer = references(db, Manufacturer, [data.manufacturer_id])[0]
    categories = references(db, Category, data.category_ids) if data.category_ids is not None else None
    sources = references(db, Source, data.source_ids) if data.source_ids is not None else None
    releases = {r.id: r for r in c.releases}
    configs = {r.id: r for r in c.configurations}
    for r in data.releases or []:
        if r.id is not None and r.id not in releases:
            raise HTTPException(422, 'Commercializzazione non appartenente al calcolatore')
        references(db, Market, [r.market_id])
        if r.source_ids is not None:
            references(db, Source, r.source_ids)
    for cfg in data.configurations or []:
        if cfg.id is not None and cfg.id not in configs:
            raise HTTPException(422, 'Configurazione non appartenente al calcolatore')
        specs = {s.id for s in configs[cfg.id].specifications} if cfg.id else set()
        for s in cfg.specifications:
            if s.id is not None and s.id not in specs:
                raise HTTPException(422, 'Specifica non appartenente alla configurazione')
            if s.source_ids is not None:
                references(db, Source, s.source_ids)
    c.model_name = data.model_name
    c.manufacturer = manufacturer
    c.description = data.description
    c.announcement_date, c.announcement_precision = historical_date(data.announcement_date)
    if categories is not None:
        c.categories = categories
    if sources is not None:
        c.sources = sources
    if data.releases is not None:
        updated = []
        for entry in data.releases:
            r = releases.get(entry.id) or Release()
            for field in ('market_id', 'price', 'currency', 'price_type'):
                setattr(r, field, getattr(entry, field))
            r.release_date, r.release_precision = historical_date(entry.release_date)
            r.discontinuation_date, r.discontinuation_precision = historical_date(entry.discontinuation_date)
            if entry.source_ids is not None:
                r.sources = references(db, Source, entry.source_ids)
            updated.append(r)
        c.releases = updated
    if data.configurations is not None:
        updated = []
        # Free variant names first so rename/swap/remove can respect the unique constraint.
        for cfg in c.configurations:
            cfg.variant_name = f'__editing_{uuid4().hex}_{cfg.id}__'
        db.flush()
        for entry in data.configurations:
            cfg = configs.get(entry.id) or Configuration()
            cfg.variant_name, cfg.description = entry.variant_name, entry.description
            specs = {s.id: s for s in cfg.specifications}
            children = []
            for value in entry.specifications:
                s = specs.get(value.id) or Specification()
                for field in ('component_type', 'component_name', 'property_name', 'numeric_value', 'text_value', 'unit'):
                    setattr(s, field, getattr(value, field))
                if value.source_ids is not None:
                    s.sources = references(db, Source, value.source_ids)
                children.append(s)
            cfg.specifications = children
            updated.append(cfg)
        c.configurations = updated
    db.add(c)


def create_admin_router(get_db):
    router = APIRouter(prefix='/api', tags=['Amministrazione locale'])

    def commit(db):
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(409, 'Dati in conflitto con un elemento esistente; ricarica e riprova') from exc

    @router.get('/admin/computers/{computer_id}')
    def edit_computer(computer_id: int, db: Session = Depends(get_db)):
        c = db.get(Computer, computer_id)
        if c is None:
            raise HTTPException(404, 'Calcolatore non trovato')
        return editable(c)

    @router.post('/computers', status_code=201)
    def create_computer(data: ComputerInput, db: Session = Depends(get_db)):
        c = Computer()
        apply_computer(db, c, data)
        commit(db)
        return editable(c)

    @router.put('/computers/{computer_id}')
    def update_computer(computer_id: int, data: ComputerInput, db: Session = Depends(get_db)):
        c = db.scalar(select(Computer).where(Computer.id == computer_id).with_for_update())
        if c is None:
            raise HTTPException(404, 'Calcolatore non trovato')
        apply_computer(db, c, data)
        commit(db)
        return editable(c)

    def reference_endpoint(model):
        def create(data: ReferenceInput, db: Session = Depends(get_db)):
            if db.scalar(select(model.id).where(model.name == data.name)) is not None:
                raise HTTPException(409, 'Questo nome è già presente')
            item = model(name=data.name)
            db.add(item)
            commit(db)
            return {'id': item.id, 'name': item.name}
        return create
    for path, model in [('manufacturers', Manufacturer), ('categories', Category), ('markets', Market)]:
        router.add_api_route('/' + path, reference_endpoint(model), methods=['POST'], status_code=201)
    return router
