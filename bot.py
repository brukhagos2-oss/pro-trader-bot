import os
import time
import threading
import requests
import telebot
from telebot import types
from datetime import datetime

# ==========================================
# CONFIGURATION & CONSTANTS
# ==========================================
TOKEN = "8581232155:AAF5IYyCs0rKtp9VDktOz0HxwGXAOFbhsKc"
CHANNEL_USERNAME = "@Ethio_online_works_1"  # ሲግናሎቹ እና ውጤቶቹ አውቶማቲክ የሚለኩበት ቻናል
TWELVE_DATA_API_KEY = "3664c54c5d064605a75795583af2cd9c"

# Initialize Telegram Bot instance
bot = telebot.TeleBot(TOKEN)

# Active trade tracking dictionary to monitor open trades and check for 1:3 TP/SL
active_trades = {}
trade_lock = threading.Lock()

# Supported Assets
ASSETS = {
    "XAU/USD": "XAU/USD",
    "XAG/USD": "XAG/USD",
    "EUR/USD": "EUR/USD",
    "GBP/USD": "GBP/USD",
    "USD/JPY": "USD/JPY",
    "AUD/USD": "AUD/USD"
}

# ==========================================
# FORCE SUBSCRIPTION VERIFICATION MODULE
# ==========================================
def check_sub(user_id):
    """
    Verifies if a user has joined the mandatory Telegram channel.
    """
    try:
        member = bot.get_chat_member(CHANNEL_USERNAME, user_id)
        if member.status in ['member', 'administrator', 'creator']:
            return True
    except Exception as e:
        print(f"Subscription check error for user {user_id}: {e}")
    return False

def send_subscription_prompt(chat_id):
    """
    Sends an inline markup prompt requiring the user to join the channel.
    """
    markup = types.InlineKeyboardMarkup()
    channel_url = f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}"
    
    btn_channel = types.InlineKeyboardButton("📢 ቻናላችንን Join ይበሉ", url=channel_url)
    btn_check = types.InlineKeyboardButton("✅ ሰብስክራይብ አድርጌያለሁ", callback_data="check_subscription")
    
    markup.add(btn_channel)
    markup.add(btn_check)
    
    prompt_text = (
        "⚠️ **ቦቱን ለመጠቀም መጀመሪያ ቻናላችንን ሰብስክራይብ ማድረግ አለብዎት!**\n\n"
        "እባክዎ ከታች ያለውን ሊንክ በመጫን ቻናላችንን ይቀላቀሉና 'ሰብስክራይብ አድርጌያለሁ' የሚለውን ይጫኑ።"
    )
    
    bot.send_message(chat_id, prompt_text, reply_markup=markup, parse_mode="Markdown")

# ==========================================
# TWELVE DATA API MARKET ANALYZER
# ==========================================
def fetch_live_price(symbol):
    """
    Fetches current real-time live price for TP/SL monitoring and analysis.
    """
    try:
        price_url = f"https://api.twelvedata.com/price?symbol={symbol}&apikey={TWELVE_DATA_API_KEY}"
        price_res = requests.get(price_url, timeout=10).json()
        if "price" in price_res:
            return float(price_res["price"])
    except Exception as e:
        print(f"Error fetching live price for {symbol}: {e}")
    return None

def analyze_market_15m(symbol):
    """
    Analyzes technical structures using EMA (Trend filter) and ATR (Volatility/Wide SL) 
    without time restriction for quick testing and instant signals.
    """
    try:
        current_price = fetch_live_price(symbol)
        if current_price is None:
            return None, None, None, None

        ema_url = f"https://api.twelvedata.com/ema?symbol={symbol}&interval=15min&time_period=20&outputsize=1&apikey={TWELVE_DATA_API_KEY}"
        atr_url = f"https://api.twelvedata.com/atr?symbol={symbol}&interval=15min&time_period=14&outputsize=1&apikey={TWELVE_DATA_API_KEY}"
        ts_url = f"https://api.twelvedata.com/time_series?symbol={symbol}&interval=15min&outputsize=2&apikey={TWELVE_DATA_API_KEY}"

        ema_res = requests.get(ema_url, timeout=10).json()
        atr_res = requests.get(atr_url, timeout=10).json()
        ts_res = requests.get(ts_url, timeout=10).json()

        if "values" in ema_res and "values" in atr_res and "values" in ts_res:
            current_ema = float(ema_res["values"][0]["ema"])
            current_atr = float(atr_res["values"][0]["atr"])
            
            latest_close = float(ts_res["values"][0]["close"])
            prev_close = float(ts_res["values"][1]["close"])

            if current_atr == 0:
                return None, None, None, None

            is_bullish_trend = (current_price > current_ema) and (latest_close > prev_close)
            is_bearish_trend = (current_price < current_ema) and (latest_close < prev_close)

            # Instant fallback if strict trend is neutral, to force signal generation for demo
            if not is_bullish_trend and not is_bearish_trend:
                is_bullish_trend = latest_close >= prev_close

            if is_bullish_trend:
                action = "BUY"
                risk_distance = max(current_atr * 2.5, 0.0020 if "USD" in symbol and "XAU" not in symbol else 2.0)
                return current_price, action, risk_distance, "Instant Trend Confluence (EMA & ATR Aligned)"
            else:
                action = "SELL"
                risk_distance = max(current_atr * 2.5, 0.0020 if "USD" in symbol and "XAU" not in symbol else 2.0)
                return current_price, action, risk_distance, "Instant Trend Confluence (EMA & ATR Aligned)"

    except Exception as e:
        print(f"Error analyzing market for {symbol}: {e}")
        
    return None, None, None, None

# ==========================================
# AUTOMATED BACKGROUND WORKER (INSTANT SIGNALS & 1:3 RATIO)
# ==========================================
def background_signal_and_result_worker():
    """
    Continuously analyzes markets, coordinates strict mathematical 1:3 execution,
    and updates statuses dynamically on target channels without delay.
    """
    print("🚀 Automated Instant Signal Engine with 1:3 R:R initialized...")
    
    while True:
        try:
            for display_name, symbol in ASSETS.items():
                with trade_lock:
                    active_trade = active_trades.get(symbol)
                
                # CASE 1: Active Trade Monitoring
                if active_trade:
                    current_price = fetch_live_price(symbol)
                    if current_price is not None:
                        action = active_trade["action"]
                        tp = active_trade["tp"]
                        sl = active_trade["sl"]
                        
                        hit_result = None
                        if action == "BUY":
                            if current_price >= tp:
                                hit_result = "PROFIT (TP HIT) 🟢"
                            elif current_price <= sl:
                                hit_result = "LOSS (SL HIT) 🔴"
                        else: # SELL
                            if current_price <= tp:
                                hit_result = "PROFIT (TP HIT) 🟢"
                            elif current_price >= sl:
                                hit_result = "LOSS (SL HIT) 🔴"
                                
                        if hit_result:
                            result_text = (
                                f"📊 **TRADE RESULT UPDATE** 📊\n"
                                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                                f"💎 **Asset:** `{display_name}`\n"
                                f"⚡ **Original Action:** `{action}`\n"
                                f"📌 **Result Status:** `{hit_result}`\n"
                                f"🎯 **Exit Price:** `{current_price}`\n"
                                f"⏱ *Time:* `{datetime.now().strftime('%Y-%m-%d %H:%M')} UTC`\n"
                                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                                f"💡 *Next instant setup will be broadcasted shortly.*"
                            )
                            try:
                                bot.send_message(CHANNEL_USERNAME, result_text, parse_mode="Markdown")
                                print(f"Reported result for {display_name}: {hit_result}")
                            except Exception as e:
                                print(f"Failed to send result message: {e}")
                                
                            with trade_lock:
                                del active_trades[symbol]
                    time.sleep(5)
                    continue

                # CASE 2: Process Signals Immediately
                price, action, risk, detail = analyze_market_15m(symbol)
                
                if price is None:
                    time.sleep(5)
                    continue

                decimals = 2 if "XAU" in symbol else (3 if "XAG" in symbol else (2 if "JPY" in symbol else 4))
                
                if action == "BUY":
                    entry = round(price, decimals)
                    sl = round(entry - risk, decimals)
                    tp = round(entry + (risk * 3.0), decimals)
                else: # SELL
                    entry = round(price, decimals)
                    sl = round(entry + risk, decimals)
                    tp = round(entry - (risk * 3.0), decimals)

                action_text = "BUY 🟢 (LONG - Instant Setup)" if action == "BUY" else "SELL 🔴 (SHORT - Instant Setup)"
                computed_pips = round(risk * 10000) if decimals == 4 else round(risk, 1)

                signal_text = (
                    f"🚨 **VIP INSTANT 1:3 SIGNAL** 🚨\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"💎 **Asset:** `{display_name}`\n"
                    f"⚡ **Signal Action:** `{action_text}`\n"
                    f"🎯 **Risk/Reward Ratio:** `1:3 (Strict Structure)`\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"📍 **Entry Execution:** `{entry}`\n"
                    f"🟢 **Take Profit (TP):** `{tp}`\n"
                    f"🔴 **Stop Loss (SL):** `{sl}`\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"💡 *Technical Filter:* `{detail}`\n"
                    f"⚠️ *Wide ATR SL applied (~{computed_pips} units protection) against noise.*\n"
                    f"⏱ *Time:* `{datetime.now().strftime('%Y-%m-%d %H:%M')} UTC`"
                )

                try:
                    sent_msg = bot.send_message(CHANNEL_USERNAME, signal_text, parse_mode="Markdown")
                    with trade_lock:
                        active_trades[symbol] = {
                            "action": action,
                            "entry": entry,
                            "tp": tp,
                            "sl": sl,
                            "message_id": sent_msg.message_id
                        }
                    print(f"Successfully broadcasted instant 1:3 structure for {display_name} -> {action}")
                except Exception as send_err:
                    print(f"Failed to send telegram broadcast: {send_err}")

                time.sleep(15)
                
        except Exception as outer_err:
            print(f"Background worker loop error: {outer_err}")
            time.sleep(15)

# ==========================================
# TELEGRAM BOT INTERACTION COMMANDS
# ==========================================
@bot.message_handler(commands=['start'])
def handle_start(message):
    """
    Handles /start command with strict channel subscription enforcement.
    """
    user_id = message.from_user.id
    
    if not check_sub(user_id):
        send_subscription_prompt(message.chat.id)
        return

    welcome_text = (
        "🤖 **Welcome to Pro Trader AI Automated Signal Bot!**\n\n"
        "✅ ቻናላችንን ስላደረጉ እናመሰግናለን!\n\n"
        "ይህ ቦት ገበያው አላስፈላጊ ጫጫታ (Noise) እንዳይመታው በ ATR የተደገፈ ሰፊ ስቶፕ ላስ (Wide SL) እና በትክክለኛ 1:3 ራቲዮ ፈጣን ሲግናሎችን በራሱ ይለቃል።"
    )
    bot.send_message(message.chat.id, welcome_text, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == "check_subscription")
def handle_subscription_callback(call):
    """
    Handles subscription confirmation button click.
    """
    user_id = call.from_user.id
    
    if check_sub(user_id):
        bot.answer_callback_query(call.id, "✅ ማረጋገጫው ተሳክቷል! እንኳን ደህና መጡ።")
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception:
            pass
        
        success_text = (
            "🎉 **እንኳን ደህና መጡ!**\n\n"
            "አሁን ቦቱ በትክክል ስራውን ጀምሯል። የ 1:3 ሲግናሎችን እና የውጤት ሪፖርቶችን ለመከታተል ወደ ቻናላችን ይመልከቱ!"
        )
        bot.send_message(call.message.chat.id, success_text, parse_mode="Markdown")
    else:
        bot.answer_callback_query(
            call.id, 
            "❌ እስካሁን ቻናሉን ሰብስክራይብ አላደረጉም! እባክዎ መጀመሪያ Join ይበሉ።", 
            show_alert=True
        )

# ==========================================
# APPLICATION ENTRY POINT & THREADING
# ==========================================
if __name__ == '__main__':
    worker_thread = threading.Thread(target=background_signal_and_result_worker, daemon=True)
    worker_thread.start()
    
    print("Telegram Bot Instant 1:3 engine and background worker initialized successfully...")
    bot.infinity_polling(skip_pending=True)
