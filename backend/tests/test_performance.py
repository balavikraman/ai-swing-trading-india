from app.performance import performance_from_simulation_rows


def test_performance_metrics_include_drawdown_and_streak():
    rows = [
        {"simulation": {"status": "TARGET1", "profit_loss": 10, "percentage_return": 2, "realized_r_multiple": 2, "holding_sessions": 4, "exit_date": "2026-01-02"}},
        {"simulation": {"status": "STOPPED", "profit_loss": -5, "percentage_return": -1, "realized_r_multiple": -1, "holding_sessions": 2, "exit_date": "2026-01-03"}},
        {"simulation": {"status": "STOPPED", "profit_loss": -5, "percentage_return": -1, "realized_r_multiple": -1, "holding_sessions": 3, "exit_date": "2026-01-04"}},
        {"simulation": {"status": "TARGET1", "profit_loss": 15, "percentage_return": 3, "realized_r_multiple": 2, "holding_sessions": 5, "exit_date": "2026-01-05"}},
    ]
    result = performance_from_simulation_rows(rows)
    assert result["closed_trades"] == 4
    assert result["win_rate_pct"] == 50
    assert result["max_consecutive_losses"] == 2
    assert result["max_drawdown_rupees"] == -10
    assert result["profit_factor"] == 2.5
