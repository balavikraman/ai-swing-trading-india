from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd

from .models import EventDataStatus, ExperimentConfig


@dataclass(frozen=True)
class CorporateEvent:
    symbol: str
    event_date: date
    event_type: str
    description: str = ""
    source: str = "unknown"


@dataclass(frozen=True)
class EventLookup:
    events: list[CorporateEvent]
    status: EventDataStatus
    source: str
    error: str | None = None


@dataclass(frozen=True)
class EventRiskCheck:
    blocked: bool
    reason: str | None
    status: EventDataStatus
    events: list[CorporateEvent]


class CorporateEventProvider(ABC):
    name = "abstract"

    @abstractmethod
    def lookup(self, symbol: str, start: date, end: date) -> EventLookup:
        raise NotImplementedError


class ManualCorporateEventProvider(CorporateEventProvider):
    name = "manual-csv"

    def __init__(self, path: str | Path | None = None):
        default_path = Path(__file__).resolve().parents[1] / "data" / "corporate_events.csv"
        self.path = Path(path or os.getenv("MANUAL_EVENTS_CSV", default_path))
        self._events = self._load()

    def _load(self) -> list[CorporateEvent]:
        if not self.path.exists(): return []
        frame = pd.read_csv(self.path)
        if frame.empty: return []
        columns = {str(c).strip().lower(): c for c in frame.columns}
        symbol_col = columns.get("symbol"); date_col = columns.get("event_date") or columns.get("date")
        type_col = columns.get("event_type") or columns.get("type"); desc_col = columns.get("description")
        if symbol_col is None or date_col is None: raise ValueError("corporate event CSV requires symbol and event_date columns")
        output = []
        for _, row in frame.iterrows():
            symbol = str(row[symbol_col]).strip().upper(); parsed = pd.to_datetime(row[date_col], errors="coerce")
            if not symbol or symbol == "NAN" or pd.isna(parsed): continue
            event_type = str(row[type_col]).strip() if type_col else "company_event"
            description = str(row[desc_col]).strip() if desc_col and not pd.isna(row[desc_col]) else ""
            output.append(CorporateEvent(symbol, parsed.date(), event_type, description, self.name))
        return output

    def lookup(self, symbol: str, start: date, end: date) -> EventLookup:
        wanted = symbol.strip().upper().removesuffix(".NS")
        events = [e for e in self._events if e.symbol == wanted and start <= e.event_date <= end]
        return EventLookup(events=events, status=EventDataStatus.MANUAL, source=self.name)


class YFinanceCorporateEventProvider(CorporateEventProvider):
    name = "yfinance-earnings-research"

    @staticmethod
    def _provider_symbol(symbol: str) -> str:
        symbol = symbol.strip(); return symbol if symbol.startswith("^") or symbol.endswith(".NS") else f"{symbol}.NS"

    def _calendar_dates(self, ticker) -> list[date]:
        dates = []; calendar = ticker.calendar
        if isinstance(calendar, dict):
            raw = calendar.get("Earnings Date") or calendar.get("EarningsDate")
            if raw is not None:
                for value in raw if isinstance(raw, (list, tuple)) else [raw]:
                    parsed = pd.to_datetime(value, errors="coerce")
                    if not pd.isna(parsed): dates.append(parsed.date())
        return dates

    def lookup(self, symbol: str, start: date, end: date) -> EventLookup:
        try:
            import yfinance as yf
            ticker = yf.Ticker(self._provider_symbol(symbol)); dates = []
            try:
                frame = ticker.get_earnings_dates(limit=8)
                if frame is not None and not frame.empty:
                    for value in frame.index:
                        parsed = pd.to_datetime(value, errors="coerce")
                        if not pd.isna(parsed): dates.append(parsed.date())
            except Exception:
                dates.extend(self._calendar_dates(ticker))
            events = [CorporateEvent(symbol.strip().upper().removesuffix(".NS"), d, "earnings", "Scheduled earnings/results date", self.name) for d in sorted(set(dates)) if start <= d <= end]
            return EventLookup(events=events, status=EventDataStatus.AVAILABLE, source=self.name)
        except Exception as exc:
            return EventLookup(events=[], status=EventDataStatus.UNAVAILABLE, source=self.name, error=str(exc))


class CompositeCorporateEventProvider(CorporateEventProvider):
    name = "manual+yfinance"
    def __init__(self, manual: CorporateEventProvider | None = None, automatic: CorporateEventProvider | None = None):
        self.manual = manual or ManualCorporateEventProvider(); self.automatic = automatic or YFinanceCorporateEventProvider()
    def lookup(self, symbol: str, start: date, end: date) -> EventLookup:
        manual = self.manual.lookup(symbol, start, end); automatic = self.automatic.lookup(symbol, start, end)
        combined = {(e.event_date, e.event_type, e.source): e for e in [*manual.events, *automatic.events]}; events = sorted(combined.values(), key=lambda e: e.event_date)
        if automatic.status == EventDataStatus.UNAVAILABLE:
            status = EventDataStatus.MANUAL if events else EventDataStatus.UNAVAILABLE
            return EventLookup(events, status, self.name, automatic.error)
        return EventLookup(events, EventDataStatus.AVAILABLE, self.name)


class NoCorporateEventProvider(CorporateEventProvider):
    name = "disabled"
    def lookup(self, symbol: str, start: date, end: date) -> EventLookup: return EventLookup([], EventDataStatus.NOT_CHECKED, self.name)


def build_event_provider_from_env() -> CorporateEventProvider:
    choice = os.getenv("EVENT_PROVIDER", "composite").strip().lower()
    if choice == "manual": return ManualCorporateEventProvider()
    if choice == "yfinance": return YFinanceCorporateEventProvider()
    if choice in {"none", "disabled", "off"}: return NoCorporateEventProvider()
    return CompositeCorporateEventProvider()


def _business_window(as_of: date, days_before: int, days_after: int) -> tuple[date, date]:
    base = pd.Timestamp(as_of)
    start = (base - pd.offsets.BDay(days_after)).date() if days_after else as_of
    end = (base + pd.offsets.BDay(days_before)).date() if days_before else as_of
    return start, end


def evaluate_event_risk(symbol: str, as_of: date, provider: CorporateEventProvider, cfg: ExperimentConfig) -> EventRiskCheck:
    start, end = _business_window(as_of, cfg.event_days_before, cfg.event_days_after); lookup = provider.lookup(symbol, start, end)
    if lookup.events:
        event = min(lookup.events, key=lambda e: abs((e.event_date - as_of).days))
        reason = f"{event.event_type} event on {event.event_date.isoformat()} within configured event exclusion window"
        if event.description: reason += f" ({event.description})"
        return EventRiskCheck(True, reason, lookup.status, lookup.events)
    if lookup.status == EventDataStatus.UNAVAILABLE and cfg.event_unknown_blocks_trade:
        reason = "corporate-event data unavailable; blocked by conservative event-data policy"
        if lookup.error: reason += f" ({lookup.error[:160]})"
        return EventRiskCheck(True, reason, lookup.status, [])
    return EventRiskCheck(False, None, lookup.status, [])
