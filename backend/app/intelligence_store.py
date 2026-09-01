from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, JSON, String, Text, select
from sqlalchemy.orm import Mapped, mapped_column

from .journal import Base, JournalService, SignalRecord


class SignalIntelligenceRecord(Base):
    __tablename__ = "signal_intelligence"
    signal_id: Mapped[int] = mapped_column(ForeignKey("signals.id", ondelete="CASCADE"), primary_key=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    provider: Mapped[str] = mapped_column(String(80))
    sentiment: Mapped[float] = mapped_column(Float, default=0)
    news_risk: Mapped[float] = mapped_column(Float, default=0)
    confidence: Mapped[float] = mapped_column(Float, default=0)
    critical_risk: Mapped[bool] = mapped_column(Boolean, default=False)
    overlay_adjustment: Mapped[float] = mapped_column(Float, default=0)
    research_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    summary: Mapped[str] = mapped_column(Text, default="")
    catalysts: Mapped[list] = mapped_column(JSON, default=list)
    risks: Mapped[list] = mapped_column(JSON, default=list)
    sources: Mapped[list] = mapped_column(JSON, default=list)
    as_of: Mapped[str | None] = mapped_column(String(80), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class MarketContextRecord(Base):
    __tablename__ = "market_context_snapshots"
    run_id: Mapped[str] = mapped_column(ForeignKey("scan_runs.id", ondelete="CASCADE"), primary_key=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    context: Mapped[dict] = mapped_column(JSON, default=dict)


def save_market_context(journal: JournalService, run_id: str, context: dict | None) -> None:
    if not context:
        return
    journal.init_schema()
    with journal.Session.begin() as session:
        record = session.get(MarketContextRecord, run_id)
        if record is None:
            session.add(MarketContextRecord(run_id=run_id, context=context))
        else:
            record.context = context
            record.updated_at = datetime.now(timezone.utc)


def save_intelligence(journal: JournalService, run_id: str, results: list[dict]) -> int:
    journal.init_schema()
    saved = 0
    with journal.Session.begin() as session:
        signals = session.scalars(select(SignalRecord).where(SignalRecord.run_id == run_id)).all()
        by_symbol = {signal.symbol: signal for signal in signals}
        for item in results:
            signal = by_symbol.get(item.get("symbol"))
            if signal is None:
                continue
            record = session.get(SignalIntelligenceRecord, signal.id)
            values = {key: item.get(key) for key in ["provider", "sentiment", "news_risk", "confidence", "critical_risk", "overlay_adjustment", "research_score", "summary", "catalysts", "risks", "sources", "as_of", "error"]}
            if record is None:
                session.add(SignalIntelligenceRecord(signal_id=signal.id, **values))
            else:
                for key, value in values.items():
                    setattr(record, key, value)
                record.updated_at = datetime.now(timezone.utc)
            saved += 1
    return saved


def list_intelligence(journal: JournalService, limit: int = 50) -> list[dict]:
    journal.init_schema()
    stmt = select(SignalRecord, SignalIntelligenceRecord).join(SignalIntelligenceRecord, SignalIntelligenceRecord.signal_id == SignalRecord.id).order_by(SignalIntelligenceRecord.updated_at.desc()).limit(max(1, min(limit, 500)))
    with journal.Session() as session:
        return [
            {
                "signal_id": signal.id,
                "symbol": signal.symbol,
                "name": signal.name,
                "classification": signal.classification,
                "base_score": signal.ai_score,
                **{column.name: getattr(intelligence, column.name) for column in SignalIntelligenceRecord.__table__.columns if column.name != "signal_id"},
            }
            for signal, intelligence in session.execute(stmt).all()
        ]


def latest_market_context(journal: JournalService) -> dict | None:
    journal.init_schema()
    stmt = select(MarketContextRecord).order_by(MarketContextRecord.updated_at.desc()).limit(1)
    with journal.Session() as session:
        record = session.scalar(stmt)
        return record.context if record else None
