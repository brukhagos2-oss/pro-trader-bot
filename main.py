import os
import threading
from flask import Flask
from gtts import gTTS
import telebot
from PIL import Image, ImageDraw, ImageFont

# ============================================================
# CONFIG
# ============================================================
TELEGRAM_TOKEN = "8581232155:AAF5IYyCs0rKtp9VDktOz0HxwGXAOFbhsKc"

if not TELEGRAM_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN environment variable is missing.")

bot = telebot.TeleBot(TELEGRAM_TOKEN)

# Flask ሰርቨር ለ Railway ፖርት
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# ============================================================
# SIMPLE & STABLE MEDIA GENERATOR (No MoviePy Crash)
# ============================================================
def generate_media_card(text, output_filename="output.mp4"):
    try:
        # 1. ጽሁፉን ወደ ድምፅ መቀየር (Voiceover)
        audio_path = "voiceover.mp3"
        tts = gTTS(text=text, lang='en', slow=False)
        tts.save(audio_path)

        # 2. ለቪዲዮው የሚሆን ምስል በ PIL መፍጠር
        img = Image.new('RGB', (720, 1280), color=(15, 15, 25))
        d = ImageDraw.Draw(img)
        
        # 텍ስቱን በምስሉ ላይ መጻፍ (ቀለል ያለ ጽሁፍ ማሳያ)
        d.text((50, 600), f"Prompt:\n{text}", fill=(255, 255, 255))
        
        image_path = "slide.png"
        img.save(image_path)

        # 3. ምስሉን እና ድምፁን በአንድ ላይ ለማያያዝ ffmpeg በቀጥታ መጠቀም (ያለ MoviePy ከባድ ስራ)
        # ይህ ከባድ የራይለዌይ ስህተቶችን ያስወግዳል
        import subprocess
        
        # 5 ሰኮንድ የሚረዝም ቪዲዮ ከምስሉ እና ከድምፁ ጋር መስራት
        cmd = [
            "ffmpeg", "-loop", "1", "-i", image_path, "-i", audio_path,
            "-c:v", "libx264", "-tune", "stillimage", "-c:a", "aac",
            "-b:a", "192k", "-shortest", "-pix_fmt", "yuv420p", output_filename, "-y"
        ]
        
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        # የጸዱ ፋይሎችን መሰረዝ
        if os.path.exists(image_path):
            os.remove(image_path)
        if os.path.exists(audio_path):
            os.remove(audio_path)

        return output_filename
    except Exception as e:
        print(f"Error generating media: {e}")
        return None

# ============================================================
# TELEGRAM HANDLERS
# ============================================================
@bot.message_handler(commands=['start'])
def start_command(message):
    bot.send_message(
        message.chat.id,
        "🎬 *Media Generator Bot*\n\nጽሁፍ ላክልኝ፣ ምስል እና ድምፅ ያለው ቪዲዮ አሰናድቼ እልክልሃለሁ!"
    )

@bot.message_handler(func=lambda message: True)
def handle_prompt(message):
    chat_id = message.chat.id
    user_prompt = message.text

    msg = bot.send_message(chat_id, "⏳ *ቪዲዮዎ እየተሰራ ነው...*")

    def process():
        output_file = generate_media_card(user_prompt)
        if output_file and os.path.exists(output_file):
            try:
                with open(output_file, 'rb') as f:
                    bot.send_video(chat_id, f, caption=f"🎥 {user_prompt}")
                bot.delete_message(chat_id, msg.message_id)
            except Exception as e:
                bot.send_message(chat_id, f"❌ መላክ አልተቻለም: {e}")
            try:
                os.remove(output_file)
            except:
                pass
        else:
            bot.edit_message_text("❌ ቪዲዮ መስራት አልተቻለም።", chat_id, msg.message_id)

    threading.Thread(target=process).start()

# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    threading.Thread(target=run_flask).start()
    bot.infinity_polling(skip_pending=True)
