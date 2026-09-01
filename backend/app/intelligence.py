from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone

import requests


@dataclass(frozen=True)
class IntelligenceResult:
    provider: str
    configured: bool
    symbol: str
    sentiment: float = 0.0
    news_risk: float = 0.0
    confidence: float = 0.0
    critical_risk: bool = False
    summary: str = ""
    catalysts: tuple[str, ...] = ()
    risks: tuple[str, ...] = ()
    sources: tuple[str, ...] = ()
    overlay_adjustment: float = 0.0
    research_score: float | None = None
    as_of: str | None = None
    error: str | None = None


class OpenAIWebIntelligenceProvider:
    provider = "openai-web-search"
    endpoint = "https://api.openai.com/v1/responses"

    def __init__(self, api_key: str | None = None, model: str | None = None, timeout: float = 45):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model or os.getenv("OPENAI_RESEARCH_MODEL", "gpt-5")
        self.timeout = timeout

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    @staticmethod
    def _schema() -> dict:
        return {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "sentiment": {"type": "number", "minimum": -1, "maximum": 1},
                "news_risk": {"type": "number", "minimum": 0, "maximum": 1},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                "critical_risk": {"type": "boolean"},
                "summary": {"type": "string"},
                "catalysts": {"type": "array", "items": {"type": "string"}, "maxItems": 5},
                "risks": {"type": "array", "items": {"type": "string"}, "maxItems": 5},
                "sources": {"type": "array", "items": {"type": "string"}, "maxItems": 8},
            },
            "required": ["sentiment", "news_risk", "confidence", "critical_risk", "summary", "catalysts", "risks", "sources"],
        }

    @staticmethod
    def _extract_text(payload: dict) -> str:
        for item in payload.get("output", []):
            if item.get("type") == "message":
                for content in item.get("content", []):
                    if content.get("type") == "output_text" and content.get("text"):
                        return content["text"]
        return payload.get("output_text", "")

    def analyze(self, symbol: str, name: str, base_score: float, technical_reason: str, market_reason: str) -> IntelligenceResult:
        if not self.configured:
            return IntelligenceResult(self.provider, False, symbol, error="OPENAI_API_KEY not configured")
        now = datetime.now(timezone.utc).isoformat()
        prompt = f"""Research current public information for Indian NSE stock {symbol} ({name}) as of {now}. Use web search. Focus on information that can materially affect a 3-day to 4-week long-only swing trade: company announcements/results, regulatory/legal issues, management changes, order wins/losses, credit rating changes, sector news, macro sensitivity, unusual material news, and market-wide risk. Prefer primary sources such as NSE/company filings and high-quality financial journalism. Ignore social-media rumors.
Technical setup supplied by deterministic engine: {technical_reason}
Market context: {market_reason}
Return only the requested structured assessment. critical_risk should be true only for a high-confidence material risk that could invalidate a fresh long entry. Do not predict guaranteed direction."""
        body = {
            "model": self.model,
            "tools": [{"type": "web_search"}],
            "input": prompt,
            "text": {"format": {"type": "json_schema", "name": "stock_intelligence", "strict": True, "schema": self._schema()}},
        }
        try:
            response = requests.post(
                self.endpoint,
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json=body,
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = json.loads(self._extract_text(response.json()))
            sentiment = float(data["sentiment"])
            risk = float(data["news_risk"])
            confidence = float(data["confidence"])
            adjustment = max(-12.0, min(5.0, (sentiment * 5 - risk * 10) * confidence))
            research_score = max(0.0, min(100.0, base_score + adjustment))
            return IntelligenceResult(
                self.provider,
                True,
                symbol,
                sentiment,
                risk,
                confidence,
                bool(data["critical_risk"]),
                data["summary"],
                tuple(data["catalysts"]),
                tuple(data["risks"]),
                tuple(data["sources"]),
                round(adjustment, 2),
                round(research_score, 2),
                now,
            )
        except Exception as exc:
            return IntelligenceResult(self.provider, True, symbol, error=str(exc), as_of=now)


def enrich_candidates(candidates: list[dict], provider: OpenAIWebIntelligenceProvider, limit: int = 10) -> list[dict]:
    eligible = [
        candidate for candidate in candidates if str(candidate.get("classification", "")).split(".")[-1] in {"LIVE", "PAPER"}
    ][: max(0, limit)]
    output = []
    for candidate in eligible:
        result = provider.analyze(
            candidate["symbol"],
            candidate.get("name", candidate["symbol"]),
            float(candidate.get("ai_score", 0)),
            candidate.get("technical_reason", ""),
            candidate.get("market_reason", ""),
        )
        output.append({**result.__dict__, "catalysts": list(result.catalysts), "risks": list(result.risks), "sources": list(result.sources)})
    return output
