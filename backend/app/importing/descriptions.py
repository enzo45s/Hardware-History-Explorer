"""Offline, description-only enrichment with explicit sources and no new cards."""
from collections import defaultdict
from pydantic import Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from ..admin import Input
from ..models import Computer
from ..import_models import ComputerAlias, ImportClaim
from .. import history_sources
from .normalize import Citation, Record


class DescriptionRecord(Input):
    manufacturer: str = Field(min_length=1, max_length=160)
    model_name: str = Field(min_length=1, max_length=180)
    description: str = Field(min_length=1, max_length=20000)
    source: Citation
    evidence: str | None = Field(default=None, max_length=3000)

    @model_validator(mode='after')
    def source_url(self):
        if not self.source.url:
            raise ValueError('Ogni descrizione richiede il titolo e un URL HTTP(S) della fonte')
        return self


def normalize_record(original):
    # Unknown fields (prices, configurations, supplied database IDs or a
    # "verified" flag) are rejected rather than changing unrelated data.
    incoming = DescriptionRecord.model_validate(original)
    return Record.model_validate(incoming.model_dump(mode='json', exclude_none=True)).model_dump(mode='json', exclude_none=True)


def candidate_index(db):
    """Build once per preview, including operator-approved former names."""
    index = defaultdict(list)
    computers = {c.id: c for c in db.scalars(select(Computer).options(selectinload(Computer.manufacturer)))}
    for computer in computers.values():
        index[history_sources.model_key(computer.manufacturer.name, computer.model_name)].append(computer.id)
    for alias in db.scalars(select(ComputerAlias)):
        computer = computers.get(alias.computer_id)
        if not computer:
            continue
        maker = alias.original.get('manufacturer_name') or alias.manufacturer_key
        key = history_sources.model_key(maker, alias.original_name)
        if key[0] == history_sources.model_key(computer.manufacturer.name, computer.model_name)[0] and computer.id not in index[key]:
            index[key].append(computer.id)
    return index


def preview(db, row):
    if not row.normalized:
        return None
    computer = db.get(Computer, row.computer_id) if row.computer_id else None
    if computer is None:
        action = 'ambiguous' if row.status == 'ambiguous' else 'unmatched'
    elif computer.description == row.normalized['description']:
        action = 'unchanged'
    elif history_sources.replaceable(computer.model_name, computer.manufacturer.name, computer.description):
        action = 'replace_template' if (computer.description or '').strip() else 'fill'
    else:
        action = 'conflict'
    return {'action': action, 'current': computer.description if computer else None,
            'proposed': row.normalized['description'], 'source': row.normalized['source']}


def apply_row(db, row):
    from .engine import attribute
    computer = db.scalar(select(Computer).where(Computer.id == row.computer_id)
        .with_for_update().execution_options(populate_existing=True)) if row.computer_id else None
    if computer is None:
        row.status, row.error = 'skipped', 'Nessun calcolatore esistente associato: descrizione esclusa, nessuna scheda creata.'
        return
    incoming = row.normalized['description']
    previous = computer.description
    replace = history_sources.replaceable(computer.model_name, computer.manufacturer.name, previous)
    evidence = '\n'.join(filter(None, [
        'Testo e fonte forniti nel JSON dall’operatore; contenuto e corrispondenza alla fonte non verificati automaticamente.',
        row.normalized.get('evidence'),
    ]))
    attribute(db, row, computer, 'description', incoming, row.normalized['source'], evidence, accessed=False)
    if replace:
        computer.description = incoming
        # A recognized placeholder can be replaced, but this is not human
        # verification. attribute retained its exact previous value for review.
        claim = db.scalar(select(ImportClaim).where(ImportClaim.row_id == row.id, ImportClaim.field == 'description'))
        claim.status = 'pending'
    row.status = 'updated' if replace and previous != incoming else 'unchanged'
    row.error = None
