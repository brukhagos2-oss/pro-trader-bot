import os
import threading
import textwrap
import subprocess
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

# Flask ሰርቨር ለ Railway ፖርት እንዳይዘጋ
app = Flask(__name__)

@app.route("/")
def home():
    return "Video Generator Bot is running!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# ============================================================
# REAL 720p VIDEO GENERATION ENGINE (FFmpeg + Pillow)
# ============================================================
def generate_hd_video(prompt_text, output_filename="generated_video.mp4"):
    try:
        print(f"Starting video generation for: {prompt_text}")
        
        # 1. የድምፅ ፋይል ማዘጋጀት (gTTS)
        audio_path = "voiceover.mp3"
        tts = gTTS(text=prompt_text, lang='en', slow=False)
        tts.save(audio_path)
        
        # የድምፁን ርዝመት (Duration) በ ffprobe ማግኘት
        probe_cmd = [
            "ffprobe", "-v", "error", "-show_entries",
            "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", audio_path
        ]
        result = subprocess.run(probe_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            duration = float(result.stdout.strip())
        except:
            duration = 10.0 # ነባሪ ሰኮንድ
            
        # ቢያንስ ለ 5 ሰኮንድ እንዲሆን ማድረግ
        if duration < 5:
            duration = 5.0

        # 2. 720p ጥራት ያለው ዳራ ምስል ማዘጋጀት (1280x720 Landscape ወይም 720x1280 Portrait)
        # ለቲክቶክ/ሪልስ የሚሆን 720p Vertical (720x1280) እንጠቀማለን
        width, height = 720, 1280
        img = Image.new('RGB', (width, height), color=(10, 10, 20))
        draw = ImageDraw.Draw(img)
        
        # ጽሁፉን ውብ በሆነ መልኩ በ መስመሮች መክፈል (Wrapping)
        wrapped_text = textwrap.fill(prompt_text, width=30)
        
        # ጽሁፉን መሃል ላይ ማሳየት (Default font እንጠቀማለን ሰርቨር ላይ ስህተት እንዳይፈጥር)
        try:
            font = ImageFont.truetype("DejaVuSans-Bold.ttf", 45)
        except:
            font = ImageFont.load_default()

        # የጽሁፉን መጠን በማስላት መሃል ላይ ማስቀመጥ
        # draw.textbox ወይም በቀላል መንገድ
        draw.multiline_text((60, 500), wrapped_text, fill=(255, 255, 255), font=font, spacing=15, align="center")
        
        image_path = "slide_bg.png"
        img.save(image_path)

        # 3. FFmpeg በመጠቀም ምስሉን እና ድምፁን በማቀናጀት ትክክለኛ 720p ቪዲዮ መስራት
        # -shortest በመጠቀም ድምጹ እስኪያልቅ ድረስ ቪዲዮው እንዲረዝም ይደረጋል
        cmd = [
            "ffmpeg", 
            "-loop", "1", 
            "-i", image_path, 
            "-i", audio_path,
            "-c:v", "libx264", 
            "-tune", "stillimage", 
            "-c:a", "aac",
            "-b:a", "192k", 
            "-pix_fmt", "yuv420p",
            "-r", "30",
            "-t", str(duration),
            output_filename, 
            "-y"
        ]
        
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        # ጊዜያዊ ፋይሎችን ማጥፋት
        if os.path.exists(image_path):
            os.remove(image_path)
        if os.path.exists(audio_path):
            os.remove(audio_path)

        if os.path.exists(output_filename):
            return output_filename
        return None

    except Exception as e:
        print(f"Video generation error: {e}")
        return None

# ============================================================
# TELEGRAM HANDLERS
# ============================================================
@bot.message_handler(commands=['start'])
def start_command(message):
    bot.send_message(
        message.chat.id,
        (
            "🎬 *AI 720p Video Generator Bot*\n\n"
            "የፈለከውን ጽሁፍ (Prompt) ላክልኝ፤ እኔ ደግሞ 720p ጥራት ያለው እውነተኛ ቪዲዮ ከድምፅ ጋር አሰናድቼ እልክልሃለሁ!\n\n"
            "👇 እስቲ አሁን ጽሁፍ ላክለት:"
        ),
        parse_mode="Markdown"
    )

@bot.message_handler(func=lambda message: True)
def handle_prompt(message):
    chat_id = message.chat.id
    user_prompt = message.text

    msg = bot.send_message(
        chat_id,
        "⏳ *720p ቪዲዮዎ በጥራት እየተዘጋጀ ነው... እባክዎ ትንሽ ይጠብቁ።*",
        parse_mode="Markdown"
    )

    def process_video():
        output_file = generate_hd_video(user_prompt)
        
        if output_file and os.path.exists(output_file):
            try:
                with open(output_file, 'rb') as video_file:
                    bot.send_video(
                        chat_id,
                        video_file,
                        caption=f"🎥 *Generated Video*\n📝 {user_prompt}",
                        parse_mode="Markdown"
                    )
                bot.delete_message(chat_id, msg.message_id)
            except Exception as e:
                bot.send_message(chat_id, f"❌ ቪዲዮውን መላክ አልተቻለም: {e}")
            
            try:
                os.remove(output_file)
            except:
                pass
        else:
            bot.edit_message_text(
                "❌ ቪዲዮውን ማቀናጀት አልተቻለም። እባክዎ እንደገና ይሞክሩ።",
                chat_id,
                msg.message_id
            )

    threading.Thread(target=process_video).start()

# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    # Flask ሰርቨርን ማስጀመር (Railway ፖርት እንዲያይ)
    threading.Thread(target=run_flask).start()

    print("Telegram video bot started successfully...")
    bot.infinity_polling(skip_pending=True)
