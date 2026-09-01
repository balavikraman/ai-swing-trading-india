from __future__ import annotations

import os

import requests


class TelegramNotifier:
    def __init__(self, token: str | None = None, chat_id: str | None = None, timeout: float = 10):
        self.token = token or os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID")
        self.timeout = timeout

    @property
    def configured(self) -> bool:
        return bool(self.token and self.chat_id)

    def send(self, text: str) -> dict:
        if not self.configured:
            return {"sent": False, "reason": "Telegram credentials not configured"}
        response = requests.post(
            f"https://api.telegram.org/bot{self.token}/sendMessage",
            json={"chat_id": self.chat_id, "text": text[:4096], "disable_web_page_preview": True},
            timeout=self.timeout,
        )
        response.raise_for_status()
        data = response.json()
        return {"sent": bool(data.get("ok")), "message_id": (data.get("result") or {}).get("message_id")}


def format_scan_alert(scan: dict, top_n: int = 5) -> str:
    candidates = [
        candidate
        for candidate in scan.get("candidates", [])
        if str(candidate.get("classification")) in {"LIVE", "PAPER", "PortfolioType.LIVE", "PortfolioType.PAPER"}
    ][:top_n]
    lines = [f"AI Swing Lab | {scan.get('signal_date')}", f"Nifty regime: {scan.get('market_regime')}"]
    context = scan.get("market_context") or {}
    if context.get("breadth_score") is not None:
        lines.append(f"Breadth quality: {context['breadth_score']:.0%}")
    if not candidates:
        lines.append("No actionable high-quality setup in the current shortlist.")
    for candidate in candidates:
        lines.append(
            f"{candidate.get('symbol')} | {candidate.get('classification')} | score {candidate.get('ai_score')} | "
            f"entry {candidate.get('entry_zone_low')}-{candidate.get('entry_zone_high')} | "
            f"SL {candidate.get('stop_loss')} | T1 {candidate.get('target1')}"
        )
    lines.append("Research only. Human approval required; no auto-trading.")
    return "\n".join(lines)
