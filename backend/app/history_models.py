"""Additive, durable historical-description research and original evidence."""
from datetime import datetime, timezone
from sqlalchemy import DateTime, ForeignKey, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from .models import Base


def now():
    return datetime.now(timezone.utc)


class HistoryJob(Base):
    __tablename__ = 'history_research_jobs'
    id: Mapped[int] = mapped_column(primary_key=True)
    active_key: Mapped[str | None] = mapped_column(String(20), unique=True)
    status: Mapped[str] = mapped_column(String(20), default='ready')
    error: Mapped[str | None] = mapped_column(Text)
    next_request_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_token: Mapped[str | None] = mapped_column(String(36))
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class HistoryItem(Base):
    __tablename__ = 'history_research_items'
    __table_args__ = (UniqueConstraint('job_id', 'position'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey('history_research_jobs.id', ondelete='CASCADE'), index=True)
    position: Mapped[int]
    computer_id: Mapped[int | None] = mapped_column(ForeignKey('computers.id', ondelete='SET NULL'), index=True)
    model_name: Mapped[str] = mapped_column(String(180))
    manufacturer: Mapped[str] = mapped_column(String(160))
    previous: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default='pending')
    error: Mapped[str | None] = mapped_column(Text)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    raw_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    import_job_id: Mapped[int | None] = mapped_column(ForeignKey('import_jobs.id'))
