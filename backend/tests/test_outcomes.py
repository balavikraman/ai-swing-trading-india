from datetime import date
import pandas as pd
from app.journal import JournalService
from app.models import PortfolioType
from app.outcomes import OutcomeTracker, SimulationConfig, list_simulations, simulate_signal, simulation_summary
from app.market_data import MarketDataProvider


def frame(rows):
    idx=pd.to_datetime([r[0] for r in rows]); return pd.DataFrame({k:[r[i] for r in rows] for i,k in enumerate(['Open','High','Low','Close'],start=1)},index=idx).assign(Volume=100000)

def base_signal(): return {'id':1,'signal_date':date(2026,8,31),'entry_zone_low':100.0,'entry_zone_high':102.0,'stop_loss':95.0,'target1':112.0,'target2':118.0,'quantity':2,'symbol':'TEST','classification':'PAPER'}

def test_target_after_next_session_entry():
    f=frame([('2026-08-31',100,103,99,102),('2026-09-01',101,106,99,104),('2026-09-02',104,113,103,112)]); r=simulate_signal(base_signal(),f,SimulationConfig())
    assert r['status']=='TARGET1'; assert r['entry_price']==101; assert r['exit_price']==112; assert r['target1_hit'] is True; assert r['stop_hit'] is False; assert r['profit_loss']==22; assert r['mfe_pct']==round((112/101-1)*100,4)

def test_same_bar_stop_and_target_assumes_stop():
    f=frame([('2026-08-31',100,103,99,102),('2026-09-01',101,114,94,103)]); r=simulate_signal(base_signal(),f,SimulationConfig())
    assert r['status']=='STOPPED'; assert r['exit_reason']=='STOP_SAME_BAR_AMBIGUITY'; assert r['ambiguous_bar'] is True; assert r['profit_loss']==-12

def test_gap_above_zone_is_not_chased_and_entry_expires():
    f=frame([('2026-08-31',100,103,99,102),('2026-09-01',108,110,105,109),('2026-09-02',109,111,106,110),('2026-09-03',110,112,107,111)]); r=simulate_signal(base_signal(),f,SimulationConfig(entry_valid_sessions=3)); assert r['status']=='ENTRY_EXPIRED'; assert r['entry_expired'] is True

def test_time_exit_at_max_holding_close():
    f=frame([('2026-08-31',100,103,99,102),('2026-09-01',101,104,99,102),('2026-09-02',103,105,100,104),('2026-09-03',104,107,101,106)]); r=simulate_signal(base_signal(),f,SimulationConfig(max_holding_sessions=3)); assert r['status']=='TIME_EXIT'; assert r['exit_price']==106; assert r['holding_sessions']==3; assert r['profit_loss']==10

class FakeProvider(MarketDataProvider):
    name='fake-market'
    def __init__(self,history): self.history=history
    def history_many(self,symbols,period,batch_size=40): return {s:self.history for s in symbols}

def test_tracker_persists_paper_result_and_summary():
    from app.models import EventDataStatus, ExperimentConfig, MarketRegime, TradeProposal
    from app.scanner import ScanResult
    j=JournalService('sqlite+pysqlite:///:memory:'); proposal=TradeProposal(symbol='TEST',name='Test Ltd',signal_date=date(2026,8,31),current_price=101,setup_type='breakout',entry_zone_low=100,entry_zone_high=102,stop_loss=95,target1=112,target2=118,quantity=1,capital_required=101,maximum_planned_loss=6,potential_reward=11,risk_reward_ratio=11/6,ai_score=90,score_components={},classification=PortfolioType.PAPER,technical_reason='',market_reason='',decision_reason='',event_data_status=EventDataStatus.AVAILABLE)
    j.save_scan(ScanResult([proposal],[],MarketRegime.BULLISH,date(2026,8,31)),'NIFTY_200','fake','fake',ExperimentConfig()); f=frame([('2026-08-31',100,103,99,102),('2026-09-01',101,106,99,104),('2026-09-02',104,113,103,112)])
    out=OutcomeTracker(j,FakeProvider(f)).refresh(); assert out['updated']==1 and out['terminal']==1
    sims=list_simulations(j,classification='PAPER'); assert sims[0]['simulation']['status']=='TARGET1'
    summary=simulation_summary(j); assert summary['paper']['closed']==1; assert summary['paper']['win_rate_pct']==100; assert summary['paper']['total_pnl']==11
