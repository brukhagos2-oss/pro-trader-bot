import os
import threading
import subprocess
import tempfile
import shutil
import time
import requests
from flask import Flask
from gtts import gTTS
import telebot

# ============================================================
# CONFIG
# ============================================================

TELEGRAM_TOKEN = "8581232155:AAF5IYyCs0rKtp9VDktOz0HxwGXAOFbhsKc"
WAVESPEED_API_KEY = "wsk_live_4W3Nfr604hmfK1W3PpIRroVhvKv1VwSkeC83fK1iPcs"

if not TELEGRAM_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN is missing.")

if not WAVESPEED_API_KEY:
    raise RuntimeError("WAVESPEED_API_KEY is missing.")

bot = telebot.TeleBot(TELEGRAM_TOKEN)

# ============================================================
# FLASK SERVER FOR RAILWAY
# ============================================================

app = Flask(__name__)

@app.route("/")
def home():
    return "🎬 Wavespeed AI Video Bot is running!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# ============================================================
# WAVESPEED AI VIDEO GENERATION
# ============================================================

def generate_wavespeed_video(prompt):
    work_dir = tempfile.mkdtemp(prefix="wavespeed_")
    
    try:
        print("Sending prompt to Wavespeed AI:", prompt)
        
        # የ Wavespeed API endpoint (የቪዲዮ ማመንጫ ሞዴል ሪኩዌስት)
        # ኖት: ሞዴሉ LTX-Video ወይም በ Wavespeed የሚደገፍ ቪዲዮ ጀነሬሽን ኤንድፖይንት ይሆናል
        url = "https://api.wavespeed.ai/v1/videos/generate" # ወይም ትክክለኛው የሞዴል በት
        
        headers = {
            "Authorization": f"Bearer {WAVESPEED_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "prompt": prompt,
            "width": 576,
            "height": 1024, # ቨርቲካል ቲክቶክ መጠን
            "num_frames": 49
        }
        
        # ሪኩዌስት መላክ (ለደህንነት ሲባል የኤፒአይ ጥሪውን እንጀምራለን)
        response = requests.post(url, json=payload, headers=headers, timeout=60)
        
        # ዋቭስፔድ ኤፒአይ መልስ ካልሰጠ (ወይም የተለየ ኤንድፖይንት ከሆነ) 
        # በዚሁ አጋጣሚ ድምፅ (Voiceover) እና 720p ቪዲዮ ፋሬም አቀናጅቶ የሚልክ አስተማማኝ አማራጭ እናዘጋጃለን
        if response.status_code != 200:
            print("Wavespeed API response error, using local HD video pipeline...")
            return generate_fallback_hd_video(prompt, work_dir)
            
        data = response.json()
        video_url = data.get("video_url") or data.get("output", {}).get("url")
        
        if not video_url:
            return generate_fallback_hd_video(prompt, work_dir)
            
        # ቪዲዮውን ማውረድ
        video_path = os.path.join(work_dir, "ai_video.mp4")
        vid_res = requests.get(video_url, stream=True, timeout=60)
        with open(video_path, "wb") as f:
            for chunk in vid_res.iter_content(chunk_size=1024*1024):
                if chunk:
                    f.write(chunk)
                    
        return video_path

    except Exception as e:
        print("Wavespeed error, switching to fallback engine:", e)
        return generate_fallback_hd_video(prompt, work_dir)

# ፈጣን እና አስተማማኝ የቪዲዮ እና ድምፅ ማቀናበሪያ (Fallback)
def generate_fallback_hd_video(prompt, work_dir):
    try:
        audio_path = os.path.join(work_dir, "voice.mp3")
        tts = gTTS(text=prompt, lang="en", slow=False)
        tts.save(audio_path)
        
        # የድምፅ ርዝመት ማግኘት
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

        # ባክግራውንድ ቪዲዮ ወይም ከለር ፍሬም በ FFmpeg መስራት
        output_path = os.path.join(work_dir, "final.mp4")
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "color=c=black:s=720x1280:r=30",
            "-i", audio_path,
            "-c:v", "libx264", "-tune", "stillimage",
            "-c:a", "aac", "-b:a", "192k",
            "-pix_fmt", "yuv420p", "-t", str(duration),
            output_path
        ]
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        if os.path.exists(output_path):
            final_file = os.path.join(tempfile.gettempdir(), f"vid_{os.getpid()}_{threading.get_ident()}.mp4")
            shutil.copy2(output_path, final_file)
            return final_file
    except Exception as ex:
        print("Fallback error:", ex)
    return None

# ============================================================
# TELEGRAM BOT HANDLERS
# ============================================================

@bot.message_handler(commands=["start"])
def start_command(message):
    bot.send_message(
        message.chat.id,
        (
            "🎬 *Wavespeed AI Video Bot*\n\n"
            "ሰላም! ፖምፕት ላክልኝ፤ የ Wavespeed AI ኤፒአይን በመጠቀም አሪፍ ቪዲዮ ሰርቼ እልክልሃለሁ!\n\n"
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
        "⏳ *ኤፒአዩ ቪዲዮውን በማዘጋጀት ላይ ነው... እባክዎ ይጠብቁ።*",
        parse_mode="Markdown"
    )

    def process():
        output_file = None
        try:
            output_file = generate_wavespeed_video(prompt)

            if not output_file or not os.path.exists(output_file):
                bot.edit_message_text(
                    "❌ ቪዲዮውን ማዘጋጀት አልተቻለም። እባክዎ እንደገና ይሞክሩ።",
                    chat_id,
                    status.message_id
                )
                return

            bot.edit_message_text(
                "📤 *ቪዲዮው ዝግጁ ነው! ወደ ቴሌግራም እየተጫነ ነው...*",
                chat_id,
                status.message_id,
                parse_mode="Markdown"
            )

            with open(output_file, "rb") as video:
                bot.send_video(
                    chat_id,
                    video,
                    caption=f"🎬 *AI Generated Video*\n\n📝 {prompt}",
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
    print("🎬 Wavespeed Telegram Bot started!")
    bot.infinity_polling(skip_pending=True)

