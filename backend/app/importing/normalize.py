import csv
import io
import json
import re
import unicodedata
from datetime import date
from pydantic import Field, field_validator, model_validator
from ..admin import Input, historical_date
from .vocabulary import unit_name, normalize_spec

MAX_BYTES = 8 * 1024 * 1024
MAX_ROWS = 1000


def name_key(value):
    return ' '.join(unicodedata.normalize('NFKC', value).split()).casefold()


def clean(value):
    return ' '.join(unicodedata.normalize('NFKC', value).split())


class Citation(Input):
    title: str = Field(min_length=2, max_length=300)
    url: str | None = Field(default=None, max_length=800)
    author: str | None = Field(default=None, max_length=180)
    publisher: str | None = Field(default=None, max_length=180)
    license: str | None = Field(default=None, max_length=300)
    source_type: str = Field(default='dataset', min_length=1, max_length=60)
    publication_date: date | None = None
    access_date: date | None = None

    @field_validator('url')
    @classmethod
    def safe_url(cls, value):
        from pydantic import HttpUrl
        if value is None:
            return None
        parsed = HttpUrl(value)
        if parsed.username or parsed.password:
            raise ValueError('Le fonti richiedono URL HTTP(S) senza credenziali')
        return str(parsed)


class Supported(Input):
    source: Citation | None = None
    evidence: str | None = Field(default=None, max_length=3000)
    estimated: bool = False


class Spec(Supported):
    component_type: str = Field(min_length=1, max_length=80)
    component_name: str | None = Field(default=None, max_length=160)
    property_name: str = Field(min_length=1, max_length=120)
    numeric_value: float | None = None
    text_value: str | None = Field(default=None, min_length=1, max_length=10000)
    unit: str | None = Field(default=None, max_length=30)

    @model_validator(mode='before')
    @classmethod
    def quantity(cls, data):
        data = normalize_spec(data)
        text = data.get('text_value')
        if isinstance(text, str) and data.get('numeric_value') is None and data['property_name'] not in (
            'Modello','Architettura','Modello emulato (MAME)','Modello riportato (Wikidata)',
            'Codice modello','Identificativo','SoC riportato'):
            match = re.fullmatch(r'([+-]?\d+(?:\.\d+)?)\s+([A-Za-z]+)', text.strip())
            if match and not data.get('unit'):
                data.update(numeric_value=float(match[1]), unit=match[2], text_value=None)
        return normalize_spec(data)

    @model_validator(mode='after')
    def one_value(self):
        if (self.numeric_value is None) == (self.text_value is None):
            raise ValueError('La specifica richiede un solo valore, numerico o testuale')
        return self


class Variant(Supported):
    variant_name: str = Field(min_length=1, max_length=140)
    description: str | None = Field(default=None, max_length=10000)
    specifications: list[Spec] = Field(default_factory=list, max_length=200)


class Dated(Supported):
    @field_validator('release_date', 'discontinuation_date', 'period_start', 'period_end', 'review_date', 'reference_date', check_fields=False)
    @classmethod
    def valid_date(cls, value):
        historical_date(value)
        return value


class CommercialRelease(Dated):
    market: str = Field(min_length=1, max_length=130)
    release_date: str | None = None
    discontinuation_date: str | None = None
    price: float | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, pattern=r'^[A-Z]{3}$')
    price_type: str | None = Field(default=None, max_length=30)

    @model_validator(mode='after')
    def chronology(self):
        if self.release_date and self.discontinuation_date:
            from calendar import monthrange
            start, _ = historical_date(self.release_date)
            end, precision = historical_date(self.discontinuation_date)
            upper = date(end.year, 12, 31) if precision == 'year' else date(end.year, end.month, monthrange(end.year, end.month)[1]) if precision == 'month' else end
            if upper < start:
                raise ValueError('Fine commercializzazione precedente al lancio')
        if self.price is not None and not self.currency:
            raise ValueError('Un prezzo richiede una valuta esplicita')
        return self


class Sales(Dated):
    market: str = Field(min_length=1, max_length=130)
    period_start: str | None = None
    period_end: str | None = None
    units_sold: int | None = Field(default=None, ge=0)
    metric_type: str = Field(default='units_sold', min_length=1, max_length=30)

    @model_validator(mode='after')
    def chronology(self):
        for value in (self.period_start, self.period_end):
            if value and len(value) != 10:
                raise ValueError('I periodi di vendita richiedono date complete; le date parziali restano nel file originale')
        if self.period_start and self.period_end and self.period_end < self.period_start:
            raise ValueError('Intervallo vendite non valido')
        return self


class Assessment(Dated):
    publication: str = Field(min_length=1, max_length=160)
    review_date: str | None = None
    score: float | None = Field(default=None, ge=0)
    max_score: float | None = Field(default=None, gt=0)
    summary: str | None = Field(default=None, max_length=10000)

    @model_validator(mode='after')
    def scale(self):
        if self.score is not None and (self.max_score is None or self.score > self.max_score):
            raise ValueError('Punteggio privo di scala valida')
        if self.review_date and len(self.review_date) != 10:
            raise ValueError('Data recensione completa richiesta dallo schema corrente')
        return self


class HistoricalFact(Dated):
    fact_type: str = Field(min_length=1, max_length=60)
    statement: str = Field(min_length=1, max_length=10000)
    reference_date: str | None = None

    @model_validator(mode='after')
    def precision(self):
        if self.reference_date and len(self.reference_date) != 10:
            raise ValueError('Data del fatto completa richiesta dallo schema corrente')
        return self


class Record(Supported):
    source: Citation
    external_id: str | None = Field(default=None, min_length=1, max_length=200)
    manufacturer: str = Field(min_length=1, max_length=160)
    model_name: str = Field(min_length=1, max_length=180)
    description: str | None = Field(default=None, max_length=20000)
    announcement_date: str | None = None
    categories: list[str] = Field(default_factory=list, max_length=20)
    configurations: list[Variant] = Field(default_factory=list, max_length=100)
    releases: list[CommercialRelease] = Field(default_factory=list, max_length=100)
    sales: list[Sales] = Field(default_factory=list, max_length=100)
    reviews: list[Assessment] = Field(default_factory=list, max_length=100)
    facts: list[HistoricalFact] = Field(default_factory=list, max_length=100)

    @field_validator('manufacturer', 'model_name')
    @classmethod
    def normalized_name(cls, value):
        return clean(value)

    @field_validator('categories')
    @classmethod
    def normalized_categories(cls, values):
        if any(not clean(v) or len(clean(v)) > 100 for v in values):
            raise ValueError('Categoria non valida')
        return list(dict.fromkeys(clean(v) for v in values))

    @field_validator('announcement_date')
    @classmethod
    def valid_date(cls, value):
        historical_date(value)
        return value

    @model_validator(mode='after')
    def distinct_variants(self):
        keys = [name_key(v.variant_name) for v in self.configurations]
        if len(keys) != len(set(keys)):
            raise ValueError('Nomi configurazione duplicati nella stessa riga')
        return self


def parse_payload(raw, format):
    if len(raw) > MAX_BYTES:
        raise ValueError('Massimo 8 MB per importazione')
    text = raw.decode('utf-8-sig')
    if format == 'json':
        data = json.loads(text, parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Numero non finito')))
        if isinstance(data, dict):
            data = data.get('records', data)
    elif format == 'csv':
        reader = csv.DictReader(io.StringIO(text))
        if not reader.fieldnames or len(reader.fieldnames) != len(set(reader.fieldnames)):
            raise ValueError('Intestazione CSV mancante o duplicata')
        data = []
        for row in reader:
            if None in row:
                raise ValueError('Numero di colonne CSV non coerente')
            row = {k: v for k, v in row.items() if v != ''}
            for key in ('source', 'configurations', 'releases', 'sales', 'reviews', 'facts'):
                if key in row:
                    row[key] = json.loads(row[key])
            if 'categories' in row:
                row['categories'] = row['categories'].split('|')
            data.append(row)
            if len(data) > MAX_ROWS:
                raise ValueError('Massimo 1000 righe; suddividi il dataset')
    else:
        raise ValueError('Formato supportato: csv oppure json')
    if not isinstance(data, list) or not 1 <= len(data) <= MAX_ROWS or not all(isinstance(r, dict) for r in data):
        raise ValueError('Serve un elenco di 1–1000 oggetti')
    return text, data
