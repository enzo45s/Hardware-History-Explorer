"""Additive ETL audit tables; catalog entities and source link tables stay intact."""
from datetime import datetime, timezone
from sqlalchemy import ForeignKey, String, Text, JSON, UniqueConstraint, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .models import Base


def now():
    return datetime.now(timezone.utc)


class ImportJob(Base):
    __tablename__ = 'import_jobs'
    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String(40))
    filename: Mapped[str] = mapped_column(String(250))
    format: Mapped[str] = mapped_column(String(20))
    checksum: Mapped[str] = mapped_column(String(64))
    raw_payload: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default='ready')
    error: Mapped[str | None] = mapped_column(Text)
    retry_of: Mapped[int | None] = mapped_column(ForeignKey('import_jobs.id'))
    request_options: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    rows = relationship('ImportRow', cascade='all,delete-orphan', order_by='ImportRow.position')


class ImportRow(Base):
    __tablename__ = 'import_rows'
    __table_args__ = (UniqueConstraint('job_id', 'position'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey('import_jobs.id', ondelete='CASCADE'), index=True)
    position: Mapped[int]
    raw: Mapped[dict] = mapped_column(JSON)
    normalized: Mapped[dict | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default='ready')
    error: Mapped[str | None] = mapped_column(Text)
    computer_id: Mapped[int | None] = mapped_column(ForeignKey('computers.id', ondelete='SET NULL'), index=True)
    candidates: Mapped[list] = mapped_column(JSON, default=list)
    claims = relationship('ImportClaim', cascade='all,delete-orphan', order_by='ImportClaim.id')


class ExternalIdentity(Base):
    __tablename__ = 'import_identities'
    __table_args__ = (UniqueConstraint('provider', 'external_id'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String(40))
    external_id: Mapped[str] = mapped_column(String(200))
    computer_id: Mapped[int] = mapped_column(ForeignKey('computers.id', ondelete='CASCADE'), index=True)


class ImportClaim(Base):
    __tablename__ = 'import_claims'
    id: Mapped[int] = mapped_column(primary_key=True)
    row_id: Mapped[int] = mapped_column(ForeignKey('import_rows.id', ondelete='CASCADE'), index=True)
    computer_id: Mapped[int | None] = mapped_column(ForeignKey('computers.id', ondelete='SET NULL'), index=True)
    source_id: Mapped[int] = mapped_column(ForeignKey('sources.id'), index=True)
    entity: Mapped[str] = mapped_column(String(30))
    target_id: Mapped[int]
    field: Mapped[str] = mapped_column(String(80))
    value: Mapped[dict] = mapped_column(JSON)
    previous: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default='pending')
    estimated: Mapped[bool] = mapped_column(default=False)
    evidence: Mapped[str | None] = mapped_column(Text)
    review_note: Mapped[str | None] = mapped_column(Text)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source = relationship('Source')
