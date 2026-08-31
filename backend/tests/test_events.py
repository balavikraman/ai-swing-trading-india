from datetime import date
from app.events import CorporateEvent, CorporateEventProvider, EventLookup, evaluate_event_risk
from app.models import EventDataStatus, ExperimentConfig

class FakeEvents(CorporateEventProvider):
    name="fake-events"
    def __init__(self,event_date=None,unavailable=False): self.event_date=event_date; self.unavailable=unavailable
    def lookup(self,symbol,start,end):
        if self.unavailable: return EventLookup([],EventDataStatus.UNAVAILABLE,self.name,"provider down")
        events=[]
        if self.event_date and start<=self.event_date<=end: events=[CorporateEvent(symbol,self.event_date,"earnings","quarterly results",self.name)]
        return EventLookup(events,EventDataStatus.AVAILABLE,self.name)

def test_event_inside_pre_window_blocks():
    check=evaluate_event_risk("TEST",date(2026,8,31),FakeEvents(date(2026,9,2)),ExperimentConfig(event_days_before=3,event_days_after=1)); assert check.blocked; assert "earnings" in check.reason

def test_event_outside_window_does_not_block():
    check=evaluate_event_risk("TEST",date(2026,8,31),FakeEvents(date(2026,9,10)),ExperimentConfig(event_days_before=2,event_days_after=1)); assert not check.blocked

def test_unknown_event_data_blocks_by_default():
    check=evaluate_event_risk("TEST",date(2026,8,31),FakeEvents(unavailable=True),ExperimentConfig()); assert check.blocked; assert check.status==EventDataStatus.UNAVAILABLE

def test_unknown_event_data_can_be_allowed_for_research():
    check=evaluate_event_risk("TEST",date(2026,8,31),FakeEvents(unavailable=True),ExperimentConfig(event_unknown_blocks_trade=False)); assert not check.blocked
