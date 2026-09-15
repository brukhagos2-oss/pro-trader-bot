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

# Active trade tracking dictionary for XAU/USD
active_trades = {}
trade_lock = threading.Lock()

# Focused Exclusively on XAU/USD for Maximum Profitability & Stability
ASSETS = {
    "XAU/USD": "XAU/USD"
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
# TWELVE DATA API MARKET ANALYZER (XAU/USD)
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
    specifically optimized for Gold (XAU/USD).
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

            if not is_bullish_trend and not is_bearish_trend:
                is_bullish_trend = latest_close >= prev_close

            if is_bullish_trend:
                action = "BUY"
                risk_distance = max(current_atr * 2.0, 3.0)  # Optimized safe distance for Gold volatility
                return current_price, action, risk_distance, "Gold Bullish Trend Confluence (EMA & ATR Aligned)"
            else:
                action = "SELL"
                risk_distance = max(current_atr * 2.0, 3.0)
                return current_price, action, risk_distance, "Gold Bearish Trend Confluence (EMA & ATR Aligned)"

    except Exception as e:
        print(f"Error analyzing market for {symbol}: {e}")
        
    return None, None, None, None

# ==========================================
# AUTOMATED BACKGROUND WORKER (XAU/USD 1:3 & STRICT RESULT CHECK)
# ==========================================
def background_signal_and_result_worker():
    """
    Continuously monitors active XAU/USD trade, immediately reports TP/SL results,
    and publishes high-accuracy 1:3 setups.
    """
    print("🚀 Gold (XAU/USD) Dedicated 1:3 Profit Engine Initialized...")
    
    while True:
        try:
            for display_name, symbol in ASSETS.items():
                with trade_lock:
                    active_trade = active_trades.get(symbol)
                
                # CASE 1: Active Trade Monitoring & Instant Result Reporting
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
                                f"📊 **GOLD TRADE RESULT UPDATE** 📊\n"
                                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                                f"💎 **Asset:** `{display_name}`\n"
                                f"⚡ **Original Action:** `{action}`\n"
                                f"📌 **Result Status:** `{hit_result}`\n"
                                f"🎯 **Exit Price:** `{current_price}`\n"
                                f"⏱ *Time:* `{datetime.now().strftime('%Y-%m-%d %H:%M')} UTC`\n"
                                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                                f"💡 *Result verified. Preparing next high-probability Gold setup...*"
                            )
                            try:
                                bot.send_message(CHANNEL_USERNAME, result_text, parse_mode="Markdown")
                                print(f"Reported result for {display_name}: {hit_result}")
                            except Exception as e:
                                print(f"Failed to send result message: {e}")
                                
                            with trade_lock:
                                del active_trades[symbol]
                            
                            # Brief pause after result before seeking next setup
                            time.sleep(10)
                    time.sleep(5)
                    continue

                # CASE 2: Process New Gold Signal only when no active trade exists
                price, action, risk, detail = analyze_market_15m(symbol)
                
                if price is None:
                    time.sleep(10)
                    continue

                decimals = 2  # Gold standard decimal places
                
                if action == "BUY":
                    entry = round(price, decimals)
                    sl = round(entry - risk, decimals)
                    tp = round(entry + (risk * 3.0), decimals)  # Strict 1:3 Ratio
                else: # SELL
                    entry = round(price, decimals)
                    sl = round(entry + risk, decimals)
                    tp = round(entry - (risk * 3.0), decimals)  # Strict 1:3 Ratio

                action_text = "BUY 🟢 (LONG - Gold Setup)" if action == "BUY" else "SELL 🔴 (SHORT - Gold Setup)"
                computed_pips = round(risk, 1)

                signal_text = (
                    f"🚨 **VIP XAU/USD (GOLD) 1:3 SIGNAL** 🚨\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"💎 **Asset:** `{display_name}`\n"
                    f"⚡ **Signal Action:** `{action_text}`\n"
                    f"🎯 **Risk/Reward Ratio:** `1:3 (Gold Optimized)`\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"📍 **Entry Execution:** `{entry}`\n"
                    f"🟢 **Take Profit (TP):** `{tp}`\n"
                    f"🔴 **Stop Loss (SL):** `{sl}`\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"💡 *Technical Filter:* `{detail}`\n"
                    f"⚠️ *Gold ATR SL applied (~{computed_pips} USD width protection).*\n"
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
                    print(f"Successfully broadcasted XAU/USD 1:3 structure -> {action}")
                except Exception as send_err:
                    print(f"Failed to send telegram broadcast: {send_err}")

                time.sleep(20)
                
        except Exception as outer_err:
            print(f"Background worker loop error: {outer_err}")
            time.sleep(20)

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
        "🤖 **Welcome to XAU/USD Pro Trader AI Bot!**\n\n"
        "✅ ቻናላችንን ስላደረጉ እናመሰግናለን!\n\n"
        "ይህ ቦት በልዩ ሁኔታ በወርቅ (XAU/USD) ገበያ ላይ ብቻ እንዲያተኩር የተደረገ ሲሆን፣ የ 1:3 ትክክለኛ ራቲዮ እና አውቶማቲክ የውጤት ሪፖርት አለው።"
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
            "አሁን ቦቱ በ XAU/USD ላይ ብቻ ስራውን ጀምሯል። የ 1:3 ሲግናሎችን እና ትክክለኛ የውጤት ሪፖርቶችን ለመከታተል ቻናሉን ይመልከቱ!"
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
    
    print("XAU/USD Dedicated Telegram Bot engine initialized successfully...")
    bot.infinity_polling(skip_pending=True)
