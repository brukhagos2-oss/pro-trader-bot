import os
import time
import threading
import requests
import telebot

from telebot import types
from datetime import datetime, timezone


# ============================================================
# CONFIG
# ============================================================

# NEVER put your real keys directly in this file.
# Set them as environment variables.

TELEGRAM_TOKEN = os.getenv("8581232155:AAF5IYyCs0rKtp9VDktOz0HxwGXAOFbhsKc")
GOLD_API_KEY = os.getenv("goldapi-0e62024fc9c1fc4b2509182ce59fff57-io")

CHANNEL_USERNAME = os.getenv(
    "CHANNEL_USERNAME",
    "@Ethio_online_works_1"
)

# GoldAPI.io
GOLD_API_URL = "https://www.goldapi.io/api/price/XAU/USD"

# ============================================================
# STRATEGY
# ============================================================

SYMBOL = "XAU/USD"

TIMEFRAME_SECONDS = 300       # 5 minutes
PRICE_POLL_SECONDS = 10       # poll every 10 seconds

EMA_FAST = 9
EMA_SLOW = 21

RSI_PERIOD = 14
ATR_PERIOD = 14

# Risk / Reward
RR = 3.0

# ATR stop multiplier
ATR_MULTIPLIER = 1.0

# Gold price risk limits
MIN_SL_DISTANCE = 2.0
MAX_SL_DISTANCE = 12.0

# RSI filters
BUY_RSI_MIN = 52
BUY_RSI_MAX = 68

SELL_RSI_MIN = 32
SELL_RSI_MAX = 48

# Don't send another signal while one is active
ONE_TRADE_AT_A_TIME = True

# Minimum candles before signals
MIN_CANDLES = 60

# Cooldown after TP/SL
TRADE_COOLDOWN = 60


# ============================================================
# VALIDATION
# ============================================================

if not TELEGRAM_TOKEN:
    raise RuntimeError(
        "TELEGRAM_BOT_TOKEN environment variable is missing."
    )

if not GOLD_API_KEY:
    raise RuntimeError(
        "GOLD_API_KEY environment variable is missing."
    )


# ============================================================
# TELEGRAM
# ============================================================

bot = telebot.TeleBot(TELEGRAM_TOKEN)


# ============================================================
# GLOBAL STATE
# ============================================================

candles = []

current_candle = None

active_trade = None

last_trade_time = 0

state_lock = threading.Lock()


# ============================================================
# GOLDAPI
# ============================================================

def get_gold_price():

    headers = {
        "x-access-token": GOLD_API_KEY,
        "Content-Type": "application/json"
    }

    try:

        response = requests.get(
            GOLD_API_URL,
            headers=headers,
            timeout=10
        )

        response.raise_for_status()

        data = response.json()

        price = data.get("price")

        bid = data.get("bid")
        ask = data.get("ask")

        timestamp = data.get("timestamp")

        if price is None:
            print("GoldAPI response has no price.")
            return None

        return {
            "price": float(price),
            "bid": float(bid) if bid is not None else None,
            "ask": float(ask) if ask is not None else None,
            "timestamp": int(timestamp)
            if timestamp else int(time.time())
        }

    except Exception as e:

        print(
            f"GoldAPI request error: {e}"
        )

        return None


# ============================================================
# 5-MINUTE CANDLE BUILDER
# ============================================================

def candle_start(timestamp):

    return (
        timestamp // TIMEFRAME_SECONDS
    ) * TIMEFRAME_SECONDS


def update_5m_candle(price_data):

    global current_candle

    price = price_data["price"]

    timestamp = price_data["timestamp"]

    start = candle_start(timestamp)

    with state_lock:

        # First candle
        if current_candle is None:

            current_candle = {
                "timestamp": start,
                "open": price,
                "high": price,
                "low": price,
                "close": price
            }

            return None

        # Same 5-minute candle
        if start == current_candle["timestamp"]:

            current_candle["high"] = max(
                current_candle["high"],
                price
            )

            current_candle["low"] = min(
                current_candle["low"],
                price
            )

            current_candle["close"] = price

            return None

        # New candle started
        completed = current_candle.copy()

        candles.append(completed)

        # Keep memory under control
        if len(candles) > 500:
            del candles[:-500]

        current_candle = {
            "timestamp": start,
            "open": price,
            "high": price,
            "low": price,
            "close": price
        }

        return completed


# ============================================================
# EMA
# ============================================================

def ema(values, period):

    if len(values) < period:
        return None

    multiplier = 2 / (period + 1)

    value = sum(
        values[:period]
    ) / period

    for price in values[period:]:

        value = (
            (price - value) *
            multiplier
        ) + value

    return value


# ============================================================
# RSI
# ============================================================

def rsi(values, period=14):

    if len(values) <= period:
        return None

    gains = []
    losses = []

    for i in range(1, len(values)):

        change = (
            values[i] -
            values[i - 1]
        )

        gains.append(
            max(change, 0)
        )

        losses.append(
            max(-change, 0)
        )

    avg_gain = (
        sum(gains[:period]) /
        period
    )

    avg_loss = (
        sum(losses[:period]) /
        period
    )

    if avg_loss == 0:
        return 100.0

    rs_value = avg_gain / avg_loss

    result = 100 - (
        100 / (1 + rs_value)
    )

    for i in range(
        period,
        len(gains)
    ):

        avg_gain = (
            (
                avg_gain *
                (period - 1)
            ) +
            gains[i]
        ) / period

        avg_loss = (
            (
                avg_loss *
                (period - 1)
            ) +
            losses[i]
        ) / period

        if avg_loss == 0:
            result = 100.0
        else:

            rs_value = (
                avg_gain /
                avg_loss
            )

            result = 100 - (
                100 /
                (1 + rs_value)
            )

    return result


# ============================================================
# ATR
# ============================================================

def atr(candle_data, period=14):

    if len(candle_data) <= period:
        return None

    true_ranges = []

    for i in range(
        1,
        len(candle_data)
    ):

        current = candle_data[i]

        previous = candle_data[i - 1]

        high = current["high"]
        low = current["low"]

        previous_close = (
            previous["close"]
        )

        true_range = max(
            high - low,
            abs(
                high -
                previous_close
            ),
            abs(
                low -
                previous_close
            )
        )

        true_ranges.append(
            true_range
        )

    if len(true_ranges) < period:
        return None

    value = (
        sum(
            true_ranges[:period]
        ) / period
    )

    for tr in true_ranges[period:]:

        value = (
            (
                value *
                (period - 1)
            ) +
            tr
        ) / period

    return value


# ============================================================
# CANDLE QUALITY
# ============================================================

def bullish_candle(candle):

    body = abs(
        candle["close"] -
        candle["open"]
    )

    candle_range = (
        candle["high"] -
        candle["low"]
    )

    if candle_range <= 0:
        return False

    body_ratio = (
        body / candle_range
    )

    return (
        candle["close"] >
        candle["open"]
        and
        body_ratio >= 0.50
    )


def bearish_candle(candle):

    body = abs(
        candle["close"] -
        candle["open"]
    )

    candle_range = (
        candle["high"] -
        candle["low"]
    )

    if candle_range <= 0:
        return False

    body_ratio = (
        body / candle_range
    )

    return (
        candle["close"] <
        candle["open"]
        and
        body_ratio >= 0.50
    )


# ============================================================
# SIGNAL ENGINE
# ============================================================

def generate_signal():

    with state_lock:

        data = list(candles)

    if len(data) < MIN_CANDLES:

        print(
            f"Waiting for candles: "
            f"{len(data)}/{MIN_CANDLES}"
        )

        return None

    closes = [
        c["close"]
        for c in data
    ]

    last = data[-1]

    price = last["close"]

    fast_ema = ema(
        closes,
        EMA_FAST
    )

    slow_ema = ema(
        closes,
        EMA_SLOW
    )

    current_rsi = rsi(
        closes,
        RSI_PERIOD
    )

    current_atr = atr(
        data,
        ATR_PERIOD
    )

    if (
        fast_ema is None or
        slow_ema is None or
        current_rsi is None or
        current_atr is None
    ):

        return None

    # --------------------------------------------------------
    # Previous EMA values
    # --------------------------------------------------------

    previous_closes = closes[:-1]

    previous_fast = ema(
        previous_closes,
        EMA_FAST
    )

    previous_slow = ema(
        previous_closes,
        EMA_SLOW
    )

    if (
        previous_fast is None or
        previous_slow is None
    ):

        return None

    # --------------------------------------------------------
    # Trend
    # --------------------------------------------------------

    bullish_trend = (
        fast_ema > slow_ema
        and
        price > fast_ema
    )

    bearish_trend = (
        fast_ema < slow_ema
        and
        price < fast_ema
    )

    # --------------------------------------------------------
    # EMA momentum
    # --------------------------------------------------------

    bullish_momentum = (
        fast_ema > previous_fast
        and
        slow_ema >= previous_slow
    )

    bearish_momentum = (
        fast_ema < previous_fast
        and
        slow_ema <= previous_slow
    )

    # --------------------------------------------------------
    # Candle confirmation
    # --------------------------------------------------------

    bull_candle = bullish_candle(
        last
    )

    bear_candle = bearish_candle(
        last
    )

    # --------------------------------------------------------
    # BUY
    # --------------------------------------------------------

    buy = (
        bullish_trend
        and
        bullish_momentum
        and
        BUY_RSI_MIN <= current_rsi <= BUY_RSI_MAX
        and
        bull_candle
    )

    # --------------------------------------------------------
    # SELL
    # --------------------------------------------------------

    sell = (
        bearish_trend
        and
        bearish_momentum
        and
        SELL_RSI_MIN <= current_rsi <= SELL_RSI_MAX
        and
        bear_candle
    )

    if not buy and not sell:

        return None

    # --------------------------------------------------------
    # Dynamic stop distance
    # --------------------------------------------------------

    risk = (
        current_atr *
        ATR_MULTIPLIER
    )

    risk = max(
        risk,
        MIN_SL_DISTANCE
    )

    if risk > MAX_SL_DISTANCE:

        print(
            "Volatility too high - "
            "signal rejected."
        )

        return None

    # --------------------------------------------------------
    # BUY
    # --------------------------------------------------------

    if buy:

        action = "BUY"

        entry = price

        stop_loss = (
            entry - risk
        )

        take_profit = (
            entry +
            (risk * RR)
        )

    # --------------------------------------------------------
    # SELL
    # --------------------------------------------------------

    else:

        action = "SELL"

        entry = price

        stop_loss = (
            entry + risk
        )

        take_profit = (
            entry -
            (risk * RR)
        )

    return {
        "action": action,
        "entry": round(entry, 2),
        "sl": round(stop_loss, 2),
        "tp": round(take_profit, 2),
        "risk": round(risk, 2),
        "atr": round(current_atr, 2),
        "rsi": round(current_rsi, 2),
        "ema_fast": round(fast_ema, 2),
        "ema_slow": round(slow_ema, 2),
        "candle_time": last["timestamp"]
    }


# ============================================================
# TELEGRAM SIGNAL
# ============================================================

def signal_message(signal):

    if signal["action"] == "BUY":

        action = "BUY 🟢"

    else:

        action = "SELL 🔴"

    candle_time = datetime.fromtimestamp(
        signal["candle_time"],
        tz=timezone.utc
    )

    return (
        "🚨 *XAU/USD 5M SCALPER* 🚨\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"💎 *Asset:* `{SYMBOL}`\n"
        f"⚡ *Signal:* `{action}`\n"
        f"📍 *Entry:* `{signal['entry']:.2f}`\n"
        f"🎯 *TP:* `{signal['tp']:.2f}`\n"
        f"🛑 *SL:* `{signal['sl']:.2f}`\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "📊 *Risk/Reward:* `1:3`\n"
        f"📈 *EMA {EMA_FAST}:* "
        f"`{signal['ema_fast']:.2f}`\n"
        f"📉 *EMA {EMA_SLOW}:* "
        f"`{signal['ema_slow']:.2f}`\n"
        f"📊 *RSI:* `{signal['rsi']:.2f}`\n"
        f"〽️ *ATR:* `{signal['atr']:.2f}`\n"
        f"🛡 *Risk:* `{signal['risk']:.2f}`\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"🕐 *Candle:* "
        f"`{candle_time.strftime('%Y-%m-%d %H:%M')} UTC`\n\n"
        "⚠️ *XAU/USD only • 5-minute scalping*"
    )


# ============================================================
# RESULT MESSAGE
# ============================================================

def result_message(
    trade,
    result,
    exit_price
):

    if result == "TP":

        status = "TAKE PROFIT HIT 🟢"

    else:

        status = "STOP LOSS HIT 🔴"

    return (
        "📊 *XAU/USD TRADE RESULT*\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"💎 *Asset:* `{SYMBOL}`\n"
        f"⚡ *Action:* `{trade['action']}`\n"
        f"📍 *Entry:* `{trade['entry']:.2f}`\n"
        f"💰 *Exit:* `{exit_price:.2f}`\n"
        f"📊 *Result:* `{status}`\n"
        f"🎯 *TP:* `{trade['tp']:.2f}`\n"
        f"🛑 *SL:* `{trade['sl']:.2f}`\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "📈 *Risk/Reward:* `1:3`\n"
        f"🕐 `{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC`"
    )


# ============================================================
# TRADE MONITOR
# ============================================================

def trade_monitor():

    global active_trade
    global last_trade_time

    while True:

        try:

            with state_lock:

                trade = active_trade

            if trade is None:

                time.sleep(
                    PRICE_POLL_SECONDS
                )

                continue

            data = get_gold_price()

            if data is None:

                time.sleep(
                    PRICE_POLL_SECONDS
                )

                continue

            price = data["price"]

            result = None

            # ------------------------------------------------
            # BUY
            # ------------------------------------------------

            if trade["action"] == "BUY":

                if price >= trade["tp"]:

                    result = "TP"

                elif price <= trade["sl"]:

                    result = "SL"

            # ------------------------------------------------
            # SELL
            # ------------------------------------------------

            elif trade["action"] == "SELL":

                if price <= trade["tp"]:

                    result = "TP"

                elif price >= trade["sl"]:

                    result = "SL"

            if result:

                message = result_message(
                    trade,
                    result,
                    price
                )

                try:

                    bot.send_message(
                        CHANNEL_USERNAME,
                        message,
                        parse_mode="Markdown"
                    )

                except Exception as e:

                    print(
                        f"Telegram result error: {e}"
                    )

                with state_lock:

                    active_trade = None

                    last_trade_time = (
                        time.time()
                    )

                print(
                    f"Trade finished: {result}"
                )

            time.sleep(
                PRICE_POLL_SECONDS
            )

        except Exception as e:

            print(
                f"Trade monitor error: {e}"
            )

            time.sleep(10)


# ============================================================
# MARKET DATA ENGINE
# ============================================================

def market_engine():

    global active_trade
    global last_trade_time

    print(
        "======================================"
    )

    print(
        " XAU/USD 5-MINUTE SCALPER"
    )

    print(
        " GoldAPI.io"
    )

    print(
        " Risk/Reward = 1:3"
    )

    print(
        "======================================"
    )

    last_signal_candle = None

    while True:

        try:

            price_data = get_gold_price()

            if price_data is None:

                time.sleep(
                    PRICE_POLL_SECONDS
                )

                continue

            completed = update_5m_candle(
                price_data
            )

            # Only evaluate a new signal
            # when a 5-minute candle closes.

            if completed is None:

                time.sleep(
                    PRICE_POLL_SECONDS
                )

                continue

            print(
                "5-minute candle closed:"
            )

            print(
                f"Open={completed['open']:.2f} "
                f"High={completed['high']:.2f} "
                f"Low={completed['low']:.2f} "
                f"Close={completed['close']:.2f}"
            )

            candle_id = (
                completed["timestamp"]
            )

            if (
                last_signal_candle ==
                candle_id
            ):

                continue

            last_signal_candle = candle_id

            # Don't create another position
            # while one exists.

            with state_lock:

                trade_exists = (
                    active_trade is not None
                )

            if (
                ONE_TRADE_AT_A_TIME
                and
                trade_exists
            ):

                print(
                    "Existing trade active."
                )

                continue

            # Cooldown

            if (
                time.time() -
                last_trade_time
                <
                TRADE_COOLDOWN
            ):

                print(
                    "Cooldown active."
                )

                continue

            signal = generate_signal()

            if signal is None:

                print(
                    "No valid XAU/USD setup."
                )

                continue

            text = signal_message(
                signal
            )

            try:

                sent = bot.send_message(
                    CHANNEL_USERNAME,
                    text,
                    parse_mode="Markdown"
                )

                trade = {
                    **signal,
                    "message_id":
                        sent.message_id,
                    "created_at":
                        time.time()
                }

                with state_lock:

                    active_trade = trade

                print(
                    "================================"
                )

                print(
                    "NEW SIGNAL"
                )

                print(
                    f"Action: {signal['action']}"
                )

                print(
                    f"Entry: {signal['entry']}"
                )

                print(
                    f"SL: {signal['sl']}"
                )

                print(
                    f"TP: {signal['tp']}"
                )

                print(
                    "================================"
                )

            except Exception as e:

                print(
                    f"Telegram signal error: {e}"
                )

        except Exception as e:

            print(
                f"Market engine error: {e}"
            )

        time.sleep(
            PRICE_POLL_SECONDS
        )


# ============================================================
# SUBSCRIPTION CHECK
# ============================================================

def check_subscription(user_id):

    try:

        member = bot.get_chat_member(
            CHANNEL_USERNAME,
            user_id
        )

        return member.status in [
            "member",
            "administrator",
            "creator"
        ]

    except Exception as e:

        print(
            f"Subscription check error: {e}"
        )

        return False


def subscription_prompt(chat_id):

    markup = types.InlineKeyboardMarkup()

    channel_url = (
        "https://t.me/" +
        CHANNEL_USERNAME.replace("@", "")
    )

    join_button = (
        types.InlineKeyboardButton(
            "📢 Join Channel",
            url=channel_url
        )
    )

    check_button = (
        types.InlineKeyboardButton(
            "✅ I Joined",
            callback_data=
                "check_subscription"
        )
    )

    markup.add(join_button)

    markup.add(check_button)

    bot.send_message(
        chat_id,
        (
            "⚠️ *Channel subscription required.*\n\n"
            "Join the channel first, then "
            "press *I Joined*."
        ),
        reply_markup=markup,
        parse_mode="Markdown"
    )


# ============================================================
# /START
# ============================================================

@bot.message_handler(
    commands=["start"]
)
def start_command(message):

    if not check_subscription(
        message.from_user.id
    ):

        subscription_prompt(
            message.chat.id
        )

        return

    bot.send_message(
        message.chat.id,
        (
            "🤖 *XAU/USD 5M Scalper*\n\n"
            "🥇 Asset: XAU/USD only\n"
            "⏱ Timeframe: 5 minutes\n"
            "📊 EMA + RSI + ATR\n"
            "🎯 Risk/Reward: 1:3\n\n"
            "Signals are published automatically."
        ),
        parse_mode="Markdown"
    )


# ============================================================
# SUBSCRIPTION CALLBACK
# ============================================================

@bot.callback_query_handler(
    func=lambda call:
        call.data ==
        "check_subscription"
)
def subscription_callback(call):

    if check_subscription(
        call.from_user.id
    ):

        bot.answer_callback_query(
            call.id,
            "✅ Subscription verified!"
        )

        try:

            bot.delete_message(
                call.message.chat.id,
                call.message.message_id
            )

        except Exception:
            pass

        bot.send_message(
            call.message.chat.id,
            (
                "🎉 *Verified successfully!*\n\n"
                "XAU/USD 5-minute scalping "
                "signals are available."
            ),
            parse_mode="Markdown"
        )

    else:

        bot.answer_callback_query(
            call.id,
            "❌ Please join the channel first.",
            show_alert=True
        )


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    # Signal/candle engine
    engine_thread = threading.Thread(
        target=market_engine,
        daemon=True
    )

    engine_thread.start()

    # TP/SL monitor
    monitor_thread = threading.Thread(
        target=trade_monitor,
        daemon=True
    )

    monitor_thread.start()

    print(
        "Telegram polling started..."
    )

    bot.infinity_polling(
        skip_pending=True
    )
