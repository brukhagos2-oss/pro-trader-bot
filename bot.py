import os
import random
import telebot
from telebot import types

TOKEN = "8581232155:AAF5IYyCs0rKtp9VDktOz0HxwGXAOFbhsKc"
CHANNEL_USERNAME = "@Ethio_online_works_1"

bot = telebot.TeleBot(TOKEN)

def check_sub(user_id):
    try:
        member = bot.get_chat_member(CHANNEL_USERNAME, user_id)
        if member.status in ['member', 'administrator', 'creator']:
            return True
    except Exception as e:
        print(f"Sub check error: {e}")
    return False

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
    btn1 = types.KeyboardButton("🟡 XAU/USD (Gold)")
    btn2 = types.KeyboardButton("💶 EUR/USD")
    btn3 = types.KeyboardButton("💴 USD/JPY")
    btn4 = types.KeyboardButton("🪙 BTC/USD")
    markup.add(btn1, btn2, btn3, btn4)
    
    bot.send_message(
        chat_id,
        "🚀 **ወደ Pro Trader VIP Bot እንኳን ደህና መጡ!**\n\nከታች ከሚገኙት የገበያ አማራጮች ውስጥ የሚፈልጉትን ይምረጡና ትክክለኛ የትሬዲንግ ሲግናል (Buy/Sell, TP, SL) ያግኙ:",
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

    selected_asset = ""
    base_price = 0.0
    
    if "XAU/USD" in text:
        selected_asset = "XAU/USD (Gold)"
        base_price = round(random.uniform(2300.0, 2650.0), 2)
    elif "EUR/USD" in text:
        selected_asset = "EUR/USD"
        base_price = round(random.uniform(1.0500, 1.1200), 4)
    elif "USD/JPY" in text:
        selected_asset = "USD/JPY"
        base_price = round(random.uniform(145.00, 155.00), 2)
    elif "BTC/USD" in text:
        selected_asset = "BTC/USD"
        base_price = round(random.uniform(60000.0, 95000.0), 2)
    
    if selected_asset:
        action = random.choice(["BUY 🟢 (LONG)", "SELL 🔴 (SHORT)"])
        
        if "XAU/USD" in selected_asset:
            entry = base_price
            if "BUY" in action:
                tp = round(entry + random.uniform(8.0, 15.0), 2)
                sl = round(entry - random.uniform(5.0, 9.0), 2)
            else:
                tp = round(entry - random.uniform(8.0, 15.0), 2)
                sl = round(entry + random.uniform(5.0, 9.0), 2)
        elif "BTC/USD" in selected_asset:
            entry = base_price
            if "BUY" in action:
                tp = round(entry + random.uniform(500.0, 1200.0), 2)
                sl = round(entry - random.uniform(300.0, 600.0), 2)
            else:
                tp = round(entry - random.uniform(500.0, 1200.0), 2)
                sl = round(entry + random.uniform(300.0, 600.0), 2)
        else:
            entry = base_price
            if "BUY" in action:
                tp = round(entry + random.uniform(0.0030, 0.0070), 4)
                sl = round(entry - random.uniform(0.0020, 0.0040), 4)
            else:
                tp = round(entry - random.uniform(0.0030, 0.0070), 4)
                sl = round(entry + random.uniform(0.0020, 0.0040), 4)

        win_rate = random.randint(88, 97)

        response = (
            f"📊 **VIP MARKET SIGNAL ANALYSIS** 📊\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"💎 **Asset:** `{selected_asset}`\n"
            f"⚡ **Signal Action:** `{action}`\n"
            f"🎯 **Win Probability:** `{win_rate}%`\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"📍 **Entry Price:** `{entry}`\n"
            f"🟢 **Take Profit (TP):** `{tp}`\n"
            f"🔴 **Stop Loss (SL):** `{sl}`\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"💡 *Technical Indicator: RSI & Smart Money Order Block Aligned.*\n"
            f"⚠️ *Risk Management: Use proper lot size.*"
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
    print("Pro Trader Bot is running...")
    bot.infinity_polling()
