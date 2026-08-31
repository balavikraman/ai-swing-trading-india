from __future__ import annotations

from dataclasses import dataclass
from io import StringIO

import pandas as pd
import requests


NIFTY_200_CSV_URL = "https://www.niftyindices.com/IndexConstituent/ind_nifty200list.csv"


@dataclass(frozen=True)
class UniverseMember:
    symbol: str
    name: str


def parse_nifty_200_csv(text: str) -> list[UniverseMember]:
    frame = pd.read_csv(StringIO(text))
    normalized = {str(c).strip().lower(): c for c in frame.columns}
    symbol_col = normalized.get("symbol")
    company_col = normalized.get("company name") or normalized.get("company_name")
    if symbol_col is None:
        raise ValueError("Nifty 200 CSV is missing Symbol column")

    members: list[UniverseMember] = []
    seen: set[str] = set()
    for _, row in frame.iterrows():
        symbol = str(row[symbol_col]).strip().upper()
        if not symbol or symbol == "NAN" or symbol in seen:
            continue
        name = str(row[company_col]).strip() if company_col is not None else symbol
        members.append(UniverseMember(symbol=symbol, name=name))
        seen.add(symbol)
    return members


def load_nifty_200(timeout_seconds: int = 15) -> list[UniverseMember]:
    headers = {"User-Agent": "Mozilla/5.0 swing-research-app/0.2"}
    response = requests.get(NIFTY_200_CSV_URL, headers=headers, timeout=timeout_seconds)
    response.raise_for_status()
    return parse_nifty_200_csv(response.text)
