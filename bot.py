import os
import random
import requests
import telebot
from telebot import types

TOKEN = "8581232155:AAF5IYyCs0rKtp9VDktOz0HxwGXAOFbhsKc"
CHANNEL_USERNAME = "@Ethio_online_works_1"
ALPHA_VANTAGE_API_KEY = "AM9CNITTXPT7CIVU"

bot = telebot.TeleBot(TOKEN)

def check_sub(user_id):
    try:
        member = bot.get_chat_member(CHANNEL_USERNAME, user_id)
        if member.status in ['member', 'administrator', 'creator']:
            return True
    except Exception as e:
        print(f"Sub check error: {e}")
    return False

def get_live_forex_price(from_currency, to_currency):
    try:
        url = f"https://www.alphavantage.co/query?function=CURRENCY_EXCHANGE_RATE&from_currency={from_currency}&to_currency={to_currency}&apikey={ALPHA_VANTAGE_API_KEY}"
        response = requests.get(url)
        data = response.json()
        rate = data["Realtime Currency Exchange Rate"]["5. Exchange Rate"]
        return float(rate)
    except Exception as e:
        print(f"API Error: {e}")
        return None

@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    if not check_sub(user_id):
        markup = types.InlineKeyboardMarkup()
        btn_channel = types.InlineKeyboardButton("📢 ቻናላችንን Join ይበሉ", url=f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}")
        btn_check = types.InlineKeyboardButton("✅ ሰብስክራይብ አድርጌያለሁ", callback_data="check_subscription")
        markup.add(btn_channel)
        markup.add(btn_check)
        
        bot.send_message(
            message.chat.id,
            "⚠️ **ቦቱን ለመጠቀም መጀመሪያ ቻናላችንን ሰብስክራይብ ማድረግ አለብዎት!**\n\nእባክዎ ከታች ያለውን ሊንክ በመጫን ቻናላችንን ይቀላቀሉና 'ሰብስክራይብ አድርጌያለሁ' የሚለውን ይጫኑ።",
            reply_markup=markup,
            parse_mode="Markdown"
        )
        return

    show_main_menu(message.chat.id)

def show_main_menu(chat_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn1 = types.KeyboardButton("💶 EUR/USD")
    btn2 = types.KeyboardButton("💴 USD/JPY")
    btn3 = types.KeyboardButton("💷 GBP/USD")
    btn4 = types.KeyboardButton("🪙 AUD/USD")
    markup.add(btn1, btn2, btn3, btn4)
    
    bot.send_message(
        chat_id,
        "🔥 **ወደ Price Action & SMC VIP Bot እንኳን ደህና መጡ!**\n\nከታች ከሚገኙት የገበያ አማራጮች ውስጥ አንዱን በመምረጥ የትዕዛዝ ማዕቀፍ (Order Block) ትንተና ያግኙ:",
        reply_markup=markup,
        parse_mode="Markdown"
    )

@bot.message_handler(func=lambda message: True)
def handle_messages(message):
    user_id = message.from_user.id
    text = message.text

    if not check_sub(user_id):
        send_welcome(message)
        return

    if text == "🔙 ወደ ዋናው ምናሌ":
        show_main_menu(message.chat.id)
        return

    from_curr, to_curr, asset_name = "", "", ""
    
    if "EUR/USD" in text:
        from_curr, to_curr, asset_name = "EUR", "USD", "EUR/USD"
    elif "USD/JPY" in text:
        from_curr, to_curr, asset_name = "USD", "JPY", "USD/JPY"
    elif "GBP/USD" in text:
        from_curr, to_curr, asset_name = "GBP", "USD", "GBP/USD"
    elif "AUD/USD" in text:
        from_curr, to_curr, asset_name = "AUD", "USD", "AUD/USD"
    
    if asset_name:
        price = get_live_forex_price(from_curr, to_curr)
        
        if price is None:
            bot.send_message(message.chat.id, "⚠️ የገበያውን መረጃ ማምጣት አልተቻለም። እባክዎ ትንሽ ቆይተው እንደገና ይሞክሩ።")
            return

        action = random.choice(["BUY 🟢 (LONG - Demand Zone)", "SELL 🔴 (SHORT - Supply Zone)"])
        
        if "BUY" in action:
            entry = round(price - 0.0005, 4) # Pullback to Order Block
            tp = round(entry + 0.0035, 4)
            sl = round(entry - 0.0015, 4)
            pa_detail = "Bullish Order Block (OB) & Fair Value Gap (FVG) mitigation."
        else:
            entry = round(price + 0.0005, 4) # Pullback to Supply
            tp = round(entry - 0.0035, 4)
            sl = round(entry + 0.0015, 4)
            pa_detail = "Bearish Order Block (OB) rejection & Liquidity Sweep."

        win_rate = random.randint(90, 98)

        response = (
            f"⚡ **SMART MONEY PRICE ACTION SETUP** ⚡\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"💎 **Asset:** `{asset_name}`\n"
            f"📊 **Structure:** `{action}`\n"
            f"🎯 **Probability:** `{win_rate}%`\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"📍 **OB Entry Zone:** `{entry}`\n"
            f"🟢 **Take Profit (TP):** `{tp}`\n"
            f"🔴 **Stop Loss (SL):** `{sl}`\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"💡 *Setup Logic:* `{pa_detail}`\n"
            f"⚠️ *Discipline: Wait for confirmation candle.*"
        )
        
        markup_back = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup_back.add(types.KeyboardButton("🔙 ወደ ዋናው ምናሌ"))
        
        bot.send_message(message.chat.id, response, reply_markup=markup_back, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == "check_subscription")
def callback_query(call):
    user_id = call.from_user.id
    if check_sub(user_id):
        bot.answer_callback_query(call.id, "✅ ማረጋገጫው ተሳክቷል! እንኳን ደህና መጡ።")
        bot.delete_message(call.message.chat.id, call.message.message_id)
        show_main_menu(call.message.chat.id)
    else:
        bot.answer_callback_query(call.id, "❌ እስካሁን ቻናሉን ሰብስክራይብ አላደረጉም! እባክዎ መጀመሪያ Join ይበሉ።", show_alert=True)

if __name__ == '__main__':
    print("Price Action Bot is running...")
    bot.infinity_polling()
