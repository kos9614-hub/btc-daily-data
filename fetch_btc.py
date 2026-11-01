
import json
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

URL = "https://api.bithumb.com/v1/candles/days?market=KRW-BTC&count=200"
KST = timezone(timedelta(hours=9))

def main():
    now = datetime.now(KST)
    request = urllib.request.Request(
        URL,
        headers={"User-Agent": "BTC-Daily-Data/1.0"}
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        candles = json.load(response)

    if not isinstance(candles, list) or len(candles) < 50:
        raise ValueError("Not enough daily candles")

    # Bithumb daily candles close at 09:00 KST.
    # Exclude the candle currently in progress.
    today = now.date()

    rows = []
    for c in candles:
        day = c["candle_date_time_kst"][:10]
        if day >= today.isoformat() and now.hour < 9:
            continue
        if day > today.isoformat():
            continue
        if day == today.isoformat() and now.hour >= 9:
            continue

        rows.append({
            "date": day,
            "open": c["opening_price"],
            "high": c["high_price"],
            "low": c["low_price"],
            "close": c["trade_price"],
            "volume": c["candle_acc_trade_volume"]
        })

    rows.sort(key=lambda x: x["date"])

    dates = [datetime.fromisoformat(r["date"]).date() for r in rows]
    for a, b in zip(dates, dates[1:]):
        if (b - a).days != 1:
            raise ValueError("Missing daily candle")

    if len(rows) < 50:
        raise ValueError("Not enough confirmed candles")

    result = {
        "market": "KRW-BTC",
        "source": URL,
        "fetched_at_kst": now.isoformat(),
        "candle_close_time_kst": "09:00",
        "last_confirmed_date": rows[-1]["date"],
        "count": len(rows),
        "candles": rows
    }

    Path("btc_daily.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    print("Saved", len(rows), "confirmed daily candles")

if __name__ == "__main__":
    main()
