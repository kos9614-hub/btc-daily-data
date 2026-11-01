
import json
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

URL = "https://api.bithumb.com/v1/candles/minutes/240?market=KRW-BTC&count=200"
KST = timezone(timedelta(hours=9))


def main():
    now = datetime.now(KST)

    request = urllib.request.Request(
        URL,
        headers={"User-Agent": "BTC-4H-Data/1.0"}
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        candles = json.load(response)

    if not isinstance(candles, list) or len(candles) < 50:
        raise ValueError("Not enough 4-hour candles")

    rows = []

    for c in candles:
        start = datetime.fromisoformat(
            c["candle_date_time_kst"]
        ).replace(tzinfo=KST)

        # Exclude unfinished 4-hour candles.
        if start + timedelta(hours=4) > now:
            continue

        rows.append({
            "date_time_kst": start.isoformat(),
            "open": c["opening_price"],
            "high": c["high_price"],
            "low": c["low_price"],
            "close": c["trade_price"],
            "volume": c["candle_acc_trade_volume"]
        })

    rows.sort(key=lambda x: x["date_time_kst"])

    if len(rows) < 50:
        raise ValueError("Not enough confirmed 4-hour candles")

    result = {
        "market": "KRW-BTC",
        "timeframe": "240m",
        "source": URL,
        "fetched_at_kst": now.isoformat(),
        "last_confirmed_candle": rows[-1]["date_time_kst"],
        "count": len(rows),
        "candles": rows
    }

    Path("btc_4h.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    print("Saved", len(rows), "confirmed 4-hour candles")


if __name__ == "__main__":
    main()
