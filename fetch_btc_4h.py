"""Fetch and validate confirmed Bithumb KRW-BTC 4-hour candles."""
import json
import math
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

URL = "https://api.bithumb.com/v1/candles/minutes/240?market=KRW-BTC&count=200"
KST = timezone(timedelta(hours=9))
OUTPUT = Path("btc_4h.json")
MAX_ATTEMPTS = 3
RETRY_SECONDS = 20


def expected_last_start(now):
    boundary = now.replace(hour=(now.hour // 4) * 4, minute=0, second=0, microsecond=0)
    return boundary - timedelta(hours=4)


def fetch():
    request = urllib.request.Request(URL, headers={"User-Agent": "BTC-4H-Data/1.1", "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def parse_and_validate(candles, now):
    if not isinstance(candles, list) or len(candles) < 50:
        raise ValueError("API returned fewer than 50 candles")
    rows = []
    for candle in candles:
        start = datetime.fromisoformat(candle["candle_date_time_kst"])
        start = start.replace(tzinfo=KST) if start.tzinfo is None else start.astimezone(KST)
        if start + timedelta(hours=4) > now:
            continue
        row = {
            "date_time_kst": start.isoformat(),
            "open": candle["opening_price"], "high": candle["high_price"],
            "low": candle["low_price"], "close": candle["trade_price"],
            "volume": candle["candle_acc_trade_volume"],
        }
        values = [row[key] for key in ("open", "high", "low", "close", "volume")]
        if not all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in values):
            raise ValueError("Non-finite or non-numeric OHLCV")
        if (min(values[:4]) <= 0 or row["volume"] < 0 or
                row["low"] > min(row["open"], row["close"]) or
                row["high"] < max(row["open"], row["close"]) or row["high"] < row["low"]):
            raise ValueError("Invalid OHLCV range")
        if start.minute != 0 or start.second != 0 or start.hour % 4 != 0:
            raise ValueError("Unexpected 4-hour candle boundary")
        rows.append(row)
    rows.sort(key=lambda row: row["date_time_kst"])
    if len(rows) < 50:
        raise ValueError("Fewer than 50 confirmed candles")
    for previous, current in zip(rows, rows[1:]):
        interval = (datetime.fromisoformat(current["date_time_kst"]) -
                    datetime.fromisoformat(previous["date_time_kst"]))
        if interval != timedelta(hours=4):
            raise ValueError("Missing or duplicate 4-hour candle")
    actual = datetime.fromisoformat(rows[-1]["date_time_kst"])
    expected = expected_last_start(now)
    if actual != expected:
        raise ValueError(f"Latest confirmed candle missing: expected={expected.isoformat()}, actual={actual.isoformat()}")
    return rows


def main():
    for attempt in range(1, MAX_ATTEMPTS + 1):
        now = datetime.now(KST)
        try:
            rows = parse_and_validate(fetch(), now)
            result = {
                "market": "KRW-BTC", "timeframe": "240m", "source": URL,
                "fetched_at_kst": datetime.now(KST).isoformat(),
                "last_confirmed_candle": rows[-1]["date_time_kst"],
                "count": len(rows), "candles": rows,
            }
            temporary = OUTPUT.with_suffix(".json.tmp")
            temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            temporary.replace(OUTPUT)
            print(f"Saved {len(rows)} confirmed 4-hour candles; latest={rows[-1]['date_time_kst']}; attempt={attempt}")
            return
        except (urllib.error.URLError, TimeoutError, OSError, ValueError, KeyError, TypeError) as exc:
            print(f"4-hour candle attempt {attempt}/{MAX_ATTEMPTS} failed: {exc}", flush=True)
            if attempt == MAX_ATTEMPTS:
                raise RuntimeError("4-hour candle refresh failed; existing JSON was preserved") from exc
            time.sleep(RETRY_SECONDS)

if __name__ == "__main__":
    main()