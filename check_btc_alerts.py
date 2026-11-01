
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

KST = timezone(timedelta(hours=9))
INPUT_FILE = Path("btc_4h.json")
OUTPUT_FILE = Path("btc_alerts.json")

DROP_THRESHOLD = -5.0
RISE_THRESHOLD = 5.0
RSI_THRESHOLD = 30.0


def calculate_rsi(closes, period=14):
    if len(closes) < period + 2:
        raise ValueError("Not enough candles for RSI")

    changes = [
        closes[i] - closes[i - 1]
        for i in range(1, len(closes))
    ]

    gains = [max(change, 0) for change in changes]
    losses = [max(-change, 0) for change in changes]

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    values = []

    def rsi_value(gain, loss):
        if gain == 0 and loss == 0:
            return 50.0
        if loss == 0:
            return 100.0
        if gain == 0:
            return 0.0
        rs = gain / loss
        return 100 - 100 / (1 + rs)

    values.append(rsi_value(avg_gain, avg_loss))

    for i in range(period, len(changes)):
        avg_gain = (
            avg_gain * (period - 1) + gains[i]
        ) / period
        avg_loss = (
            avg_loss * (period - 1) + losses[i]
        ) / period
        values.append(rsi_value(avg_gain, avg_loss))

    return values


def main():
    data = json.loads(INPUT_FILE.read_text(encoding="utf-8"))

    if data.get("market") != "KRW-BTC":
        raise ValueError("Unexpected market")

    if data.get("timeframe") != "240m":
        raise ValueError("Unexpected timeframe")

    candles = data.get("candles", [])

    if len(candles) < 50:
        raise ValueError("Not enough 4-hour candles")

    times = [
        datetime.fromisoformat(c["date_time_kst"])
        for c in candles
    ]

    if any(
        b - a != timedelta(hours=4)
        for a, b in zip(times, times[1:])
    ):
        raise ValueError("4-hour candle continuity error")

    now = datetime.now(KST)
    latest_end = times[-1] + timedelta(hours=4)

    if latest_end > now:
        raise ValueError("Latest candle is unfinished")

    if now - latest_end > timedelta(hours=5):
        raise ValueError("4-hour candle data is stale")

    for candle in candles:
        o = float(candle["open"])
        h = float(candle["high"])
        l = float(candle["low"])
        c = float(candle["close"])
        v = float(candle["volume"])

        if not (
            l > 0 and
            l <= min(o, c) <= max(o, c) <= h and
            v >= 0
        ):
            raise ValueError("Invalid OHLCV data")

    closes = [float(c["close"]) for c in candles]
    rsi_values = calculate_rsi(closes)

    previous_rsi = rsi_values[-2]
    current_rsi = rsi_values[-1]

    latest = candles[-1]
    open_price = float(latest["open"])
    close_price = float(latest["close"])

    change_pct = (
        (close_price / open_price) - 1
    ) * 100

    signals = []

    if change_pct <= DROP_THRESHOLD:
        signals.append("SHARP_DROP")

    if change_pct >= RISE_THRESHOLD:
        signals.append("SHARP_RISE")

    if (
        previous_rsi < RSI_THRESHOLD
        and current_rsi >= RSI_THRESHOLD
    ):
        signals.append("RSI_RECOVERY")

    result = {
        "market": "KRW-BTC",
        "timeframe": "240m",
        "checked_at_kst": now.isoformat(),
        "last_candle_start_kst": times[-1].isoformat(),
        "last_candle_end_kst": latest_end.isoformat(),
        "open": latest["open"],
        "close": latest["close"],
        "change_pct": round(change_pct, 3),
        "previous_rsi14": round(previous_rsi, 2),
        "current_rsi14": round(current_rsi, 2),
        "signals": signals,
        "alert": len(signals) > 0,
        "note": (
            "Preliminary signals only. "
            "Daily candle confirms buy decisions."
        )
    }

    OUTPUT_FILE.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    print("Alert check completed")
    print("Signals:", signals)


if __name__ == "__main__":
    main()
