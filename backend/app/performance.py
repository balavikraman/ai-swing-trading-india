from __future__ import annotations


def _max_consecutive_losses(pnls: list[float]) -> int:
    best = run = 0
    for pnl in pnls:
        if pnl < 0:
            run += 1
            best = max(best, run)
        else:
            run = 0
    return best


def _max_drawdown(pnls: list[float]) -> float:
    equity = peak = 0.0
    worst = 0.0
    for pnl in pnls:
        equity += pnl
        peak = max(peak, equity)
        worst = min(worst, equity - peak)
    return round(worst, 2)


def performance_from_simulation_rows(rows: list[dict]) -> dict:
    terminal = {"TARGET1", "STOPPED", "TIME_EXIT"}
    closed = []
    for row in rows:
        simulation = row.get("simulation", row)
        if simulation.get("status") in terminal and simulation.get("profit_loss") is not None:
            closed.append(simulation)
    closed.sort(key=lambda item: (item.get("exit_date") or "", item.get("signal_id") or 0))
    pnls = [float(item["profit_loss"]) for item in closed]
    wins = [pnl for pnl in pnls if pnl > 0]
    losses = [pnl for pnl in pnls if pnl < 0]
    returns = [float(item["percentage_return"]) for item in closed if item.get("percentage_return") is not None]
    r_values = [float(item["realized_r_multiple"]) for item in closed if item.get("realized_r_multiple") is not None]
    holds = [int(item["holding_sessions"]) for item in closed if item.get("holding_sessions") is not None]
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    return {
        "closed_trades": len(closed),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate_pct": round(len(wins) / len(closed) * 100, 2) if closed else None,
        "total_pnl": round(sum(pnls), 2),
        "average_winner": round(sum(wins) / len(wins), 2) if wins else None,
        "average_loser": round(sum(losses) / len(losses), 2) if losses else None,
        "profit_factor": round(gross_profit / gross_loss, 4) if gross_loss else None,
        "average_return_pct": round(sum(returns) / len(returns), 4) if returns else None,
        "average_r_multiple": round(sum(r_values) / len(r_values), 4) if r_values else None,
        "max_drawdown_rupees": _max_drawdown(pnls),
        "max_consecutive_losses": _max_consecutive_losses(pnls),
        "average_holding_sessions": round(sum(holds) / len(holds), 2) if holds else None,
    }
