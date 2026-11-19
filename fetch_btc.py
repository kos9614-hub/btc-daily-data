"""Fetch and validate confirmed Bithumb KRW-BTC daily candles (09:00 KST close)."""
import json
import math
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

URL = "https://api.bithumb.com/v1/candles/days?market=KRW-BTC&count=200"
KST = timezone(timedelta(hours=9))
OUTPUT = Path("btc_daily.json")
MAX_ATTEMPTS = 3
RETRY_SECONDS = 20


def expected_last_date(now):
    """Expected latest completed daily date at the 09:00 KST reporting cutoff."""
    today_at_nine = now.replace(hour=9, minute=0, second=0, microsecond=0)
    return (today_at_nine - timedelta(days=1 if now >= today_at_nine else 2)).date()


def fetch():
    request = urllib.request.Request(
        URL, headers={"User-Agent": "BTC-Daily-Data/1.1", "Accept": "application/json"}
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def parse_and_validate(candles, now):
    if not isinstance(candles, list) or len(candles) < 50:
        raise ValueError("API returned fewer than 50 daily candles")

    rows = []
    for candle in candles:
        start = datetime.fromisoformat(candle["candle_date_time_kst"])
        start = start.replace(tzinfo=KST) if start.tzinfo is None else start.astimezone(KST)
        # Bithumb labels daily candles with a 00:00 KST timestamp.
        # Use the 09:00 KST reporting cutoff to select completed dates;
        # do not interpret the API timestamp itself as a 09:00 start.
        if start.hour != 0 or start.minute != 0 or start.second != 0:
            raise ValueError(f"Unexpected API daily date timestamp: {start.isoformat()}")
        if start.date() > expected_last_date(now):
            continue  # Exclude dates beyond the reporting cutoff.

        row = {
            "date": start.date().isoformat(),
            "open": candle["opening_price"],
            "high": candle["high_price"],
            "low": candle["low_price"],
            "close": candle["trade_price"],
            "volume": candle["candle_acc_trade_volume"],
        }
        prices = [row[key] for key in ("open", "high", "low", "close")]
        values = prices + [row["volume"]]
        if not all(isinstance(value, (int, float)) and not isinstance(value, bool)
                   and math.isfinite(value) for value in values):
            raise ValueError("Non-finite or non-numeric OHLCV")
        if (min(prices) <= 0 or row["volume"] < 0 or
                row["low"] > min(row["open"], row["close"]) or
                row["high"] < max(row["open"], row["close"]) or
                row["high"] < row["low"]):
            raise ValueError("Invalid OHLCV range")
        rows.append(row)

    rows.sort(key=lambda row: row["date"])
    if len(rows) < 50:
        raise ValueError("Fewer than 50 confirmed daily candles")
    for previous, current in zip(rows, rows[1:]):
        delta = (datetime.fromisoformat(current["date"]) -
                 datetime.fromisoformat(previous["date"]))
        if delta != timedelta(days=1):
            raise ValueError("Missing or duplicate daily candle")

    expected = expected_last_date(now)
    actual = datetime.fromisoformat(rows[-1]["date"]).date()
    if actual != expected:
        raise ValueError(f"Latest confirmed daily candle missing: expected={expected}, actual={actual}")
    return rows


def main():
    for attempt in range(1, MAX_ATTEMPTS + 1):
        now = datetime.now(KST)
        try:
            rows = parse_and_validate(fetch(), now)
            result = {
                "market": "KRW-BTC",
                "source": URL,
                "fetched_at_kst": datetime.now(KST).isoformat(),
                "candle_close_time_kst": "09:00",
                "last_confirmed_date": rows[-1]["date"],
                "count": len(rows),
                "candles": rows,
            }
            temporary = OUTPUT.with_suffix(".json.tmp")
            temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            temporary.replace(OUTPUT)
            print(f"Saved {len(rows)} confirmed daily candles; "
                  f"latest={rows[-1]['date']}; attempt={attempt}")
            return
        except (urllib.error.URLError, TimeoutError, OSError, ValueError,
                KeyError, TypeError, json.JSONDecodeError) as exc:
            print(f"Daily candle attempt {attempt}/{MAX_ATTEMPTS} failed: {exc}", flush=True)
            if attempt == MAX_ATTEMPTS:
                raise RuntimeError("Daily candle refresh failed; existing JSON was preserved") from exc
            time.sleep(RETRY_SECONDS)


if __name__ == "__main__":
    main()