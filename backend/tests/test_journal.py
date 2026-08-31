from datetime import date
from app.journal import JournalService
from app.models import EventDataStatus, ExperimentConfig, MarketRegime, PortfolioType, TradeProposal, OutcomeUpdate
from app.scanner import ScanResult

def proposal():
    return TradeProposal(symbol="TEST",name="Test Ltd",signal_date=date(2026,8,31),current_price=100,setup_type="breakout",entry_zone_low=99,entry_zone_high=100,stop_loss=95,target1=110,target2=115,quantity=2,capital_required=200,maximum_planned_loss=10,potential_reward=20,risk_reward_ratio=2,ai_score=88,score_components={"trend_strength":20},classification=PortfolioType.LIVE,technical_reason="clean",market_reason="bullish",decision_reason="eligible",event_risk=False,event_data_status=EventDataStatus.AVAILABLE)

def test_save_scan_is_idempotent_and_persists_signal():
    j=JournalService("sqlite+pysqlite:///:memory:"); result=ScanResult([proposal()],[],MarketRegime.BULLISH,date(2026,8,31)); cfg=ExperimentConfig(); run1,created1=j.save_scan(result,"NIFTY_200","fake-market","fake-events",cfg); run2,created2=j.save_scan(result,"NIFTY_200","fake-market","fake-events",cfg)
    assert created1 is True and created2 is False and run1==run2; rows=j.list_signals(); assert len(rows)==1; assert rows[0]["symbol"]=="TEST"; assert rows[0]["score_components"]["trend_strength"]==20

def test_outcome_update_computes_realized_metrics():
    j=JournalService("sqlite+pysqlite:///:memory:"); result=ScanResult([proposal()],[],MarketRegime.BULLISH,date(2026,8,31)); j.save_scan(result,"NIFTY_200","fake","fake",ExperimentConfig()); signal_id=j.list_signals()[0]["id"]
    row=j.update_outcome(signal_id,OutcomeUpdate(actual_entry=100,actual_entry_date=date(2026,9,1),actual_exit=110,actual_exit_date=date(2026,9,8),actual_quantity=2,decision_was_correct=True,expected_thesis_met=True))
    assert row["profit_loss"]==20; assert row["percentage_return"]==10; assert row["realized_r_multiple"]==2; assert row["holding_period_days"]==7
    summary=j.comparison_summary(); assert summary["reviewed_decisions"]==1; assert summary["decision_accuracy_pct"]==100
