from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable

import pandas as pd


REQUIRED_COLUMNS = ["Open", "High", "Low", "Close", "Volume"]


def normalize_ohlcv(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame(columns=REQUIRED_COLUMNS)

    result = frame.copy()
    if isinstance(result.columns, pd.MultiIndex):
        result.columns = result.columns.get_level_values(-1)

    lookup = {str(c).strip().lower(): c for c in result.columns}
    selected: dict[str, pd.Series] = {}
    for wanted in REQUIRED_COLUMNS:
        source = lookup.get(wanted.lower())
        if source is None:
            return pd.DataFrame(columns=REQUIRED_COLUMNS)
        selected[wanted] = pd.to_numeric(result[source], errors="coerce")

    normalized = pd.DataFrame(selected, index=result.index)
    normalized = normalized.dropna(subset=["Open", "High", "Low", "Close"])
    normalized["Volume"] = normalized["Volume"].fillna(0)
    return normalized.sort_index()


class MarketDataProvider(ABC):
    name = "abstract"

    @abstractmethod
    def history_many(self, symbols: Iterable[str], period: str, batch_size: int = 40) -> dict[str, pd.DataFrame]:
        raise NotImplementedError


class YFinanceMarketDataProvider(MarketDataProvider):
    name = "yfinance-research"

    @staticmethod
    def to_provider_symbol(symbol: str) -> str:
        symbol = symbol.strip()
        if symbol.startswith("^") or symbol.endswith(".NS") or symbol.endswith(".BO"):
            return symbol
        return f"{symbol}.NS"

    def _download(self, provider_symbols: list[str], period: str):
        import yfinance as yf

        return yf.download(
            tickers=provider_symbols,
            period=period,
            interval="1d",
            auto_adjust=False,
            actions=False,
            group_by="ticker",
            threads=True,
            progress=False,
        )

    def history_many(self, symbols: Iterable[str], period: str, batch_size: int = 40) -> dict[str, pd.DataFrame]:
        originals = list(dict.fromkeys(s.strip() for s in symbols if s and s.strip()))
        output: dict[str, pd.DataFrame] = {}

        for start in range(0, len(originals), batch_size):
            batch = originals[start : start + batch_size]
            mapped = {symbol: self.to_provider_symbol(symbol) for symbol in batch}
            raw = self._download(list(mapped.values()), period)

            if len(batch) == 1:
                output[batch[0]] = normalize_ohlcv(raw)
                continue

            for original, provider_symbol in mapped.items():
                try:
                    if isinstance(raw.columns, pd.MultiIndex):
                        first_level = raw.columns.get_level_values(0)
                        if provider_symbol in first_level:
                            sub = raw[provider_symbol]
                        else:
                            second_level = raw.columns.get_level_values(1)
                            if provider_symbol in second_level:
                                sub = raw.xs(provider_symbol, axis=1, level=1)
                            else:
                                sub = pd.DataFrame()
                    else:
                        sub = pd.DataFrame()
                    output[original] = normalize_ohlcv(sub)
                except Exception:
                    output[original] = pd.DataFrame(columns=REQUIRED_COLUMNS)

        return output
