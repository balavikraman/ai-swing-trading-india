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
    major_event_nearby: bool = False
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


class TradeProposal(BaseModel):
    symbol: str
    name: str
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
    classification: PortfolioType
    technical_reason: str
    market_reason: str
    decision_reason: str
