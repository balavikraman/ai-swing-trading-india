from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, JSON, String, Text, create_engine, func, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from sqlalchemy.pool import StaticPool

from .models import ExperimentConfig, OutcomeUpdate, PortfolioType
from .scanner import ScanResult


class Base(DeclarativeBase): pass


class ScanRunRecord(Base):
    __tablename__ = "scan_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    fingerprint: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    signal_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    universe: Mapped[str] = mapped_column(String(64)); market_regime: Mapped[str] = mapped_column(String(20))
    data_provider: Mapped[str] = mapped_column(String(100)); event_provider: Mapped[str] = mapped_column(String(100))
    capital: Mapped[float] = mapped_column(Float); max_rupee_risk: Mapped[float] = mapped_column(Float)
    candidate_count: Mapped[int] = mapped_column(Integer); skipped_count: Mapped[int] = mapped_column(Integer)
    skipped_json: Mapped[list] = mapped_column(JSON, default=list)


class SignalRecord(Base):
    __tablename__ = "signals"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("scan_runs.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    signal_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True); name: Mapped[str] = mapped_column(String(255))
    classification: Mapped[str] = mapped_column(String(20), index=True); ai_score: Mapped[float] = mapped_column(Float)
    score_components: Mapped[dict] = mapped_column(JSON, default=dict); current_price: Mapped[float] = mapped_column(Float)
    setup_type: Mapped[str] = mapped_column(String(120)); entry_zone_low: Mapped[float] = mapped_column(Float); entry_zone_high: Mapped[float] = mapped_column(Float)
    stop_loss: Mapped[float] = mapped_column(Float); target1: Mapped[float] = mapped_column(Float); target2: Mapped[float | None] = mapped_column(Float, nullable=True)
    quantity: Mapped[int] = mapped_column(Integer); capital_required: Mapped[float] = mapped_column(Float); maximum_planned_loss: Mapped[float] = mapped_column(Float)
    potential_reward: Mapped[float] = mapped_column(Float); risk_reward_ratio: Mapped[float] = mapped_column(Float)
    technical_reason: Mapped[str] = mapped_column(Text); market_reason: Mapped[str] = mapped_column(Text); decision_reason: Mapped[str] = mapped_column(Text)
    event_risk: Mapped[bool] = mapped_column(Boolean, default=False); event_reason: Mapped[str | None] = mapped_column(Text, nullable=True); event_data_status: Mapped[str] = mapped_column(String(30))
    actual_entry: Mapped[float | None] = mapped_column(Float, nullable=True); actual_entry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    actual_exit: Mapped[float | None] = mapped_column(Float, nullable=True); actual_exit_date: Mapped[date | None] = mapped_column(Date, nullable=True); actual_quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    profit_loss: Mapped[float | None] = mapped_column(Float, nullable=True); percentage_return: Mapped[float | None] = mapped_column(Float, nullable=True); realized_r_multiple: Mapped[float | None] = mapped_column(Float, nullable=True)
    maximum_adverse_excursion: Mapped[float | None] = mapped_column(Float, nullable=True); maximum_favorable_excursion: Mapped[float | None] = mapped_column(Float, nullable=True); holding_period_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stop_hit: Mapped[bool | None] = mapped_column(Boolean, nullable=True); target_hit: Mapped[bool | None] = mapped_column(Boolean, nullable=True); followed_system: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    rule_violation: Mapped[str | None] = mapped_column(Text, nullable=True); chart_reference: Mapped[str | None] = mapped_column(Text, nullable=True)
    expected_thesis_met: Mapped[bool | None] = mapped_column(Boolean, nullable=True); decision_was_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True); outcome_notes: Mapped[str | None] = mapped_column(Text, nullable=True)


DEFAULT_DATABASE_URL = "postgresql+psycopg://swing:swing@localhost:5432/swing_trading"


class JournalService:
    def __init__(self, database_url: str | None = None):
        self.database_url = database_url or os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL); kwargs = {"pool_pre_ping": True}
        if self.database_url.startswith("sqlite") and ":memory:" in self.database_url: kwargs.update({"connect_args": {"check_same_thread": False}, "poolclass": StaticPool})
        self.engine = create_engine(self.database_url, **kwargs); self.Session = sessionmaker(self.engine, expire_on_commit=False)
    def init_schema(self) -> None: Base.metadata.create_all(self.engine)
    def ping(self) -> bool:
        with self.engine.connect() as conn: conn.execute(select(1))
        return True
    @staticmethod
    def _fingerprint(result: ScanResult, universe: str, data_provider: str, event_provider: str, cfg: ExperimentConfig) -> str:
        payload={"signal_date":result.signal_date.isoformat() if result.signal_date else None,"universe":universe,"data_provider":data_provider,"event_provider":event_provider,"config":cfg.model_dump(mode="json"),"proposals":[p.model_dump(mode="json") for p in result.proposals]}
        return hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
    def save_scan(self, result: ScanResult, universe: str, data_provider: str, event_provider: str, cfg: ExperimentConfig) -> tuple[str, bool]:
        self.init_schema(); fingerprint=self._fingerprint(result,universe,data_provider,event_provider,cfg)
        with self.Session.begin() as session:
            existing=session.scalar(select(ScanRunRecord).where(ScanRunRecord.fingerprint==fingerprint))
            if existing: return existing.id,False
            run_id=str(uuid.uuid4()); session.add(ScanRunRecord(id=run_id,fingerprint=fingerprint,signal_date=result.signal_date,universe=universe,market_regime=result.market_regime.value,data_provider=data_provider,event_provider=event_provider,capital=cfg.capital,max_rupee_risk=cfg.max_rupee_risk,candidate_count=len(result.proposals),skipped_count=len(result.skipped),skipped_json=result.skipped))
            for p in result.proposals:
                session.add(SignalRecord(run_id=run_id,signal_date=p.signal_date or result.signal_date,symbol=p.symbol,name=p.name,classification=p.classification.value,ai_score=p.ai_score,score_components=p.score_components,current_price=p.current_price,setup_type=p.setup_type,entry_zone_low=p.entry_zone_low,entry_zone_high=p.entry_zone_high,stop_loss=p.stop_loss,target1=p.target1,target2=p.target2,quantity=p.quantity,capital_required=p.capital_required,maximum_planned_loss=p.maximum_planned_loss,potential_reward=p.potential_reward,risk_reward_ratio=p.risk_reward_ratio,technical_reason=p.technical_reason,market_reason=p.market_reason,decision_reason=p.decision_reason,event_risk=p.event_risk,event_reason=p.event_reason,event_data_status=p.event_data_status.value))
        return run_id,True
    @staticmethod
    def _signal_dict(s: SignalRecord) -> dict: return {c.name:getattr(s,c.name) for c in SignalRecord.__table__.columns}
    def list_signals(self, limit: int=100, symbol: str | None=None, classification: str | None=None) -> list[dict]:
        self.init_schema(); stmt=select(SignalRecord).order_by(SignalRecord.created_at.desc(),SignalRecord.id.desc()).limit(max(1,min(limit,1000)))
        if symbol: stmt=stmt.where(SignalRecord.symbol==symbol.strip().upper())
        if classification: stmt=stmt.where(SignalRecord.classification==classification.strip().upper())
        with self.Session() as session: return [self._signal_dict(s) for s in session.scalars(stmt).all()]
    def list_runs(self, limit: int=30) -> list[dict]:
        self.init_schema(); stmt=select(ScanRunRecord).order_by(ScanRunRecord.created_at.desc()).limit(max(1,min(limit,365)))
        with self.Session() as session: return [{c.name:getattr(r,c.name) for c in ScanRunRecord.__table__.columns} for r in session.scalars(stmt).all()]
    def update_outcome(self, signal_id: int, update: OutcomeUpdate) -> dict | None:
        self.init_schema(); values=update.model_dump(exclude_unset=True)
        with self.Session.begin() as session:
            signal=session.get(SignalRecord,signal_id)
            if signal is None: return None
            for key,value in values.items(): setattr(signal,key,value)
            if signal.actual_entry is not None and signal.actual_exit is not None:
                qty=signal.actual_quantity if signal.actual_quantity is not None else signal.quantity; signal.profit_loss=round((signal.actual_exit-signal.actual_entry)*qty,2); signal.percentage_return=round((signal.actual_exit/signal.actual_entry-1)*100,4)
                per_share_risk=signal.actual_entry-signal.stop_loss
                if per_share_risk>0: signal.realized_r_multiple=round((signal.actual_exit-signal.actual_entry)/per_share_risk,4)
            start_date=signal.actual_entry_date or signal.signal_date
            if start_date and signal.actual_exit_date: signal.holding_period_days=max(0,(signal.actual_exit_date-start_date).days)
            session.flush(); return self._signal_dict(signal)
    def comparison_summary(self) -> dict:
        self.init_schema()
        with self.Session() as session:
            total=session.scalar(select(func.count()).select_from(SignalRecord)) or 0; reviewed=session.scalar(select(func.count()).select_from(SignalRecord).where(SignalRecord.decision_was_correct.is_not(None))) or 0; correct=session.scalar(select(func.count()).select_from(SignalRecord).where(SignalRecord.decision_was_correct.is_(True))) or 0
            realized=session.scalar(select(func.coalesce(func.sum(SignalRecord.profit_loss),0.0)).where(SignalRecord.profit_loss.is_not(None))) or 0.0; live_pnl=session.scalar(select(func.coalesce(func.sum(SignalRecord.profit_loss),0.0)).where(SignalRecord.classification==PortfolioType.LIVE.value)) or 0.0; paper_pnl=session.scalar(select(func.coalesce(func.sum(SignalRecord.profit_loss),0.0)).where(SignalRecord.classification==PortfolioType.PAPER.value)) or 0.0
            return {"total_recommendations":int(total),"reviewed_decisions":int(reviewed),"decision_accuracy_pct":round(correct/reviewed*100,2) if reviewed else None,"realized_pnl":round(float(realized),2),"live_realized_pnl":round(float(live_pnl),2),"paper_realized_pnl":round(float(paper_pnl),2),"note":"Decision accuracy is only computed for outcomes explicitly reviewed/labeled; it is not a profit prediction metric."}
