import os
import threading
import subprocess
import tempfile
import shutil
import textwrap
from flask import Flask
from gtts import gTTS
import telebot
from PIL import Image, ImageDraw, ImageFont
import google.generativeai as genai

# ============================================================
# CONFIG
# ============================================================

TELEGRAM_TOKEN = "8581232155:AAF5IYyCs0rKtp9VDktOz0HxwGXAOFbhsKc"
GEMINI_API_KEY = "AIzaSyCl6QdibqFotCPaUEAFgLNaFSNi4fSx6b8"

if not TELEGRAM_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN is missing.")

if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY is missing.")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-pro")

bot = telebot.TeleBot(TELEGRAM_TOKEN)

# ============================================================
# FLASK SERVER
# ============================================================

app = Flask(__name__)

@app.route("/")
def home():
    return "🎬 Gemini Video Bot is running!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# ============================================================
# VIDEO GENERATION ENGINE
# ============================================================

def generate_video(user_prompt):
    work_dir = tempfile.mkdtemp(prefix="video_")

    try:
        print("Processing prompt:", user_prompt)
        script_text = user_prompt

        # ጂሚኒን በመጠቀም ጽሁፉን ማስተካከል መሞከር (ካጠረ/ከተሳሳተ ዩዘር የላከውን እንጠቀማለን)
        try:
            response = model.generate_content(f"Summarize or enhance this for a short video script (max 35 words): {user_prompt}")
            if response and response.text:
                script_text = response.text.strip()
        except Exception as e:
            print("Gemini API warning, using original prompt:", e)

        # የድምፅ ፋይል (gTTS)
        audio_path = os.path.join(work_dir, "voice.mp3")
        tts = gTTS(text=script_text, lang="en", slow=False)
        tts.save(audio_path)

        # የድምፁን ርዝመት ማግኘት
        probe_cmd = [
            "ffprobe", "-v", "error", "-show_entries",
            "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", audio_path
        ]
        res = subprocess.run(probe_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            duration = float(res.stdout.strip())
        except:
            duration = 10.0
        
        if duration < 5:
            duration = 5.0

        # 720p ቨርቲካል (720x1280) ምስል መፍጠር
        width, height = 720, 1280
        img = Image.new('RGB', (width, height), color=(20, 20, 35))
        draw = ImageDraw.Draw(img)

        wrapped_text = textwrap.fill(script_text, width=26)

        try:
            font = ImageFont.truetype("DejaVuSans-Bold.ttf", 48)
        except:
            font = ImageFont.load_default()

        draw.multiline_text((60, 450), wrapped_text, fill=(255, 255, 255), font=font, spacing=20, align="center")
        
        image_path = os.path.join(work_dir, "slide.png")
        img.save(image_path)

        # FFmpeg በመጠቀም ምስል እና ድምፅ ማቀናጀት
        output_path = os.path.join(work_dir, "final_video.mp4")
        ffmpeg_cmd = [
            "ffmpeg",
            "-y",
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
            output_path
        ]

        result = subprocess.run(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        if result.returncode != 0:
            print("FFmpeg error:", result.stderr.decode(errors="ignore"))
            return None

        if not os.path.exists(output_path):
            return None

        final_file = os.path.join(
            tempfile.gettempdir(),
            f"video_{os.getpid()}_{threading.get_ident()}.mp4"
        )
        shutil.copy2(output_path, final_file)
        return final_file

    except Exception as e:
        print("Generation error:", e)
        return None

    finally:
        shutil.rmtree(work_dir, ignore_errors=True)

# ============================================================
# TELEGRAM BOT
# ============================================================

@bot.message_handler(commands=["start"])
def start_command(message):
    bot.send_message(
        message.chat.id,
        (
            "🎬 *Gemini AI Video Bot*\n\n"
            "ሰላም! ፖምፕት ላክልኝ፤ 720p ቪዲዮ ከድምፅ ጋር ሰርቼ እልክልሃለሁ!\n\n"
            "👇 ፖምፕት አሁን ላክ:"
        ),
        parse_mode="Markdown"
    )

@bot.message_handler(func=lambda message: message.text is not None)
def handle_prompt(message):
    chat_id = message.chat.id
    prompt = message.text.strip()

    if not prompt:
        return

    status = bot.send_message(
        chat_id,
        "⏳ *ቪዲዮው በጥራት እየተዘጋጀ ነው...*",
        parse_mode="Markdown"
    )

    def process():
        output_file = None
        try:
            output_file = generate_video(prompt)

            if not output_file:
                bot.edit_message_text(
                    "❌ ቪዲዮውን ማዘጋጀት አልተቻለም። እባክዎ እንደገና ይሞክሩ።",
                    chat_id,
                    status.message_id
                )
                return

            bot.edit_message_text(
                "📤 *ቪዲዮው ዝግጁ ነው! እየተላከ ነው...*",
                chat_id,
                status.message_id,
                parse_mode="Markdown"
            )

            with open(output_file, "rb") as video:
                bot.send_video(
                    chat_id,
                    video,
                    caption=f"🎬 *Generated Video*\n\n📝 {prompt}",
                    parse_mode="Markdown",
                    supports_streaming=True
                )

            bot.delete_message(chat_id, status.message_id)

        except Exception as e:
            print("Bot error:", e)
            try:
                bot.edit_message_text(f"❌ ስህተት: `{str(e)[:300]}`", chat_id, status.message_id, parse_mode="Markdown")
            except:
                pass
        finally:
            if output_file and os.path.exists(output_file):
                try:
                    os.remove(output_file)
                except:
                    pass

    threading.Thread(target=process, daemon=True).start()

# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    print("🎬 Telegram Bot started successfully!")
    bot.infinity_polling(skip_pending=True)
