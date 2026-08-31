from datetime import date
from enum import Enum
from pydantic import BaseModel, Field


class PortfolioType(str, Enum):
    LIVE = "LIVE"
    PAPER = "PAPER"
    NO_TRADE = "NO_TRADE"


class MarketRegime(str, Enum):
    BULLISH = "BULLISH"
    NEUTRAL = "NEUTRAL"
    BEARISH = "BEARISH"


class EventDataStatus(str, Enum):
    NOT_CHECKED = "NOT_CHECKED"
    AVAILABLE = "AVAILABLE"
    MANUAL = "MANUAL"
    UNAVAILABLE = "UNAVAILABLE"


class CandidateInput(BaseModel):
    symbol: str
    name: str
    current_price: float = Field(gt=0)
    ema20: float = Field(gt=0)
    dma50: float = Field(gt=0)
    dma200: float = Field(gt=0)
    resistance: float = Field(gt=0)
    avg_volume_20d: float = Field(gt=0)
    breakout_volume: float = Field(gt=0)
    consolidation_days: int = Field(ge=1)
    relative_strength_score: float = Field(ge=0, le=1)
    volatility_quality: float = Field(ge=0, le=1)
    stop_loss: float = Field(gt=0)
    target1: float = Field(gt=0)
    target2: float | None = Field(default=None, gt=0)
    signal_date: date | None = None
    major_event_nearby: bool = False
    event_reason: str | None = None
    event_data_status: EventDataStatus = EventDataStatus.NOT_CHECKED
    liquid: bool = True
    gap_pct_above_breakout: float = Field(default=0, ge=0)
    market_regime: MarketRegime = MarketRegime.NEUTRAL


class ExperimentConfig(BaseModel):
    capital: float = Field(default=1000, gt=0)
    max_rupee_risk: float = Field(default=10, gt=0)
    min_rr: float = Field(default=2.0, gt=0)
    min_score_for_trade: float = Field(default=80, ge=0, le=100)
    max_gap_pct: float = Field(default=2.0, ge=0)
    max_live_positions: int = Field(default=1, ge=1)
    event_days_before: int = Field(default=3, ge=0, le=30)
    event_days_after: int = Field(default=1, ge=0, le=30)
    event_unknown_blocks_trade: bool = True


class TradeProposal(BaseModel):
    symbol: str
    name: str
    signal_date: date | None = None
    current_price: float
    setup_type: str
    entry_zone_low: float
    entry_zone_high: float
    stop_loss: float
    target1: float
    target2: float | None
    quantity: int
    capital_required: float
    maximum_planned_loss: float
    potential_reward: float
    risk_reward_ratio: float
    ai_score: float
    score_components: dict[str, float] = Field(default_factory=dict)
    classification: PortfolioType
    technical_reason: str
    market_reason: str
    decision_reason: str
    event_risk: bool = False
    event_reason: str | None = None
    event_data_status: EventDataStatus = EventDataStatus.NOT_CHECKED


class OutcomeUpdate(BaseModel):
    actual_entry: float | None = Field(default=None, gt=0)
    actual_entry_date: date | None = None
    actual_quantity: int | None = Field(default=None, gt=0)
    actual_exit: float | None = Field(default=None, gt=0)
    actual_exit_date: date | None = None
    maximum_adverse_excursion: float | None = None
    maximum_favorable_excursion: float | None = None
    stop_hit: bool | None = None
    target_hit: bool | None = None
    followed_system: bool | None = None
    rule_violation: str | None = None
    chart_reference: str | None = None
    expected_thesis_met: bool | None = None
    decision_was_correct: bool | None = None
    outcome_notes: str | None = None
