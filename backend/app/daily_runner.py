from __future__ import annotations

import json
import sys

from dotenv import load_dotenv

from .pipeline import run_daily_pipeline

load_dotenv()


def main() -> int:
    try:
        result = run_daily_pipeline(send_telegram=True, enrich_news=True)
        print(json.dumps(result, indent=2, default=str))
        return 0
    except Exception as exc:
        print(f"Daily pipeline failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
