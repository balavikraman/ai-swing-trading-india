from __future__ import annotations

from datetime import datetime, timezone

from .broker import ZerodhaReadOnlyClient

BENCHMARK_ALIASES = {
    "NIFTY50": ["NSE:NIFTY 50"],
    "NIFTY200": ["NSE:NIFTY 200", "NSE:CNX200INDE"],
}


def benchmark_snapshot(client: ZerodhaReadOnlyClient | None = None) -> dict:
    client = client or ZerodhaReadOnlyClient()
    now = datetime.now(timezone.utc).isoformat()
    if not client.configured:
        return {
            "configured": False,
            "provider": client.provider,
            "as_of": now,
            "benchmarks": {},
            "reason": "Zerodha credentials required for both Nifty 50 and Nifty 200 live benchmark snapshots",
        }
    try:
        requested = [item for aliases in BENCHMARK_ALIASES.values() for item in aliases]
        data = client.ohlc(requested)
        output = {}
        for key, aliases in BENCHMARK_ALIASES.items():
            instrument = next((alias for alias in aliases if alias in data), aliases[0])
            row = data.get(instrument) or {}
            last = row.get("last_price")
            previous = (row.get("ohlc") or {}).get("close")
            output[key] = {
                "instrument": instrument,
                "last_price": last,
                "previous_close": previous,
                "day_change_pct": round((last / previous - 1) * 100, 4) if last and previous else None,
                "available": bool(row),
            }
        return {"configured": True, "provider": client.provider, "as_of": now, "benchmarks": output}
    except Exception as exc:
        return {"configured": True, "provider": client.provider, "as_of": now, "benchmarks": {}, "error": str(exc)}
