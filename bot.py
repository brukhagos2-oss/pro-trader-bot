import os
import threading
import subprocess
import tempfile
import shutil
import requests

from flask import Flask
from gtts import gTTS
import telebot


# ============================================================
# CONFIG
# ============================================================

TELEGRAM_TOKEN = "8581232155:AAF5IYyCs0rKtp9VDktOz0HxwGXAOFbhsKc"
PEXELS_API_KEY = "IGtE8cdRrEqJU4wAy1KEVzHxZwIgR8Lx74aMuqTD83PpB1QkWjWQZ7dP"

if not TELEGRAM_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN is missing.")

if not PEXELS_API_KEY:
    raise RuntimeError("PEXELS_API_KEY is missing.")

bot = telebot.TeleBot(TELEGRAM_TOKEN)

# ============================================================
# FLASK SERVER FOR RAILWAY
# ============================================================

app = Flask(__name__)


@app.route("/")
def home():
    return "🎬 Video Generator Bot is running!"


def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)


# ============================================================
# DOWNLOAD VIDEO FROM URL
# ============================================================

def download_video(url, output_path):

    response = requests.get(
        url,
        stream=True,
        timeout=60,
        headers={
            "User-Agent": "Mozilla/5.0"
        }
    )

    response.raise_for_status()

    with open(output_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=1024 * 1024):
            if chunk:
                f.write(chunk)

    return output_path


# ============================================================
# SEARCH PEXELS VIDEOS
# ============================================================

def search_pexels_videos(prompt, count=10):

    url = "https://api.pexels.com/v1/videos/search"

    headers = {
        "Authorization": PEXELS_API_KEY
    }

    params = {
        "query": prompt,
        "orientation": "portrait",
        "size": "medium",
        "per_page": count
    }

    response = requests.get(
        url,
        headers=headers,
        params=params,
        timeout=30
    )

    response.raise_for_status()

    data = response.json()

    return data.get("videos", [])


# ============================================================
# GET BEST VIDEO FILE
# ============================================================

def get_video_file(video):

    files = video.get("video_files", [])

    if not files:
        return None

    # Prefer vertical/HD video
    suitable = []

    for f in files:

        width = f.get("width", 0)
        height = f.get("height", 0)

        if width and height:
            suitable.append(f)

    if not suitable:
        return files[0].get("link")

    # Prefer approximately 720p or higher
    suitable.sort(
        key=lambda x: (
            x.get("width", 0) * x.get("height", 0)
        ),
        reverse=True
    )

    return suitable[0].get("link")


# ============================================================
# CREATE 60 SECOND VIDEO
# ============================================================

def generate_video(prompt):

    work_dir = tempfile.mkdtemp(prefix="video_bot_")

    try:

        print("Searching Pexels:", prompt)

        videos = search_pexels_videos(prompt, count=10)

        if not videos:
            print("No Pexels videos found.")
            return None

        downloaded = []

        # ----------------------------------------------------
        # DOWNLOAD CLIPS
        # ----------------------------------------------------

        for index, video in enumerate(videos):

            video_url = get_video_file(video)

            if not video_url:
                continue

            clip_path = os.path.join(
                work_dir,
                f"clip_{index}.mp4"
            )

            try:

                print("Downloading clip:", index)

                download_video(
                    video_url,
                    clip_path
                )

                downloaded.append(clip_path)

            except Exception as e:

                print(
                    f"Could not download clip {index}: {e}"
                )

            if len(downloaded) >= 8:
                break

        if not downloaded:
            return None

        # ----------------------------------------------------
        # CREATE CONCAT FILE
        # ----------------------------------------------------

        concat_file = os.path.join(
            work_dir,
            "concat.txt"
        )

        with open(concat_file, "w") as f:

            for clip in downloaded:

                safe_path = clip.replace(
                    "'",
                    "'\\''"
                )

                f.write(
                    f"file '{safe_path}'\n"
                )

        # ----------------------------------------------------
        # COMBINE CLIPS
        # ----------------------------------------------------

        combined = os.path.join(
            work_dir,
            "combined.mp4"
        )

        concat_cmd = [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            concat_file,
            "-c",
            "copy",
            combined
        ]

        result = subprocess.run(
            concat_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        if result.returncode != 0:

            print(
                "FFmpeg concat error:",
                result.stderr.decode(
                    errors="ignore"
                )
            )

            return None

        # ----------------------------------------------------
        # CREATE VOICEOVER
        # ----------------------------------------------------

        audio_path = os.path.join(
            work_dir,
            "voice.mp3"
        )

        try:

            tts = gTTS(
                text=prompt,
                lang="en",
                slow=False
            )

            tts.save(audio_path)

        except Exception as e:

            print("TTS error:", e)

            return None

        # ----------------------------------------------------
        # FINAL 720x1280 VIDEO
        # ----------------------------------------------------

        output_path = os.path.join(
            work_dir,
            "final_video.mp4"
        )

        ffmpeg_cmd = [
            "ffmpeg",
            "-y",

            "-i",
            combined,

            "-i",
            audio_path,

            # 720x1280 vertical video
            "-vf",
            (
                "scale=720:1280:"
                "force_original_aspect_ratio=increase,"
                "crop=720:1280"
            ),

            # Exactly about 60 seconds
            "-t",
            "60",

            # Video
            "-c:v",
            "libx264",

            "-preset",
            "veryfast",

            "-b:v",
            "1800k",

            "-maxrate",
            "2200k",

            "-bufsize",
            "4400k",

            "-pix_fmt",
            "yuv420p",

            # Audio
            "-c:a",
            "aac",

            "-b:a",
            "128k",

            "-shortest",

            output_path
        ]

        result = subprocess.run(
            ffmpeg_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        if result.returncode != 0:

            print(
                "FFmpeg final error:",
                result.stderr.decode(
                    errors="ignore"
                )
            )

            return None

        if not os.path.exists(output_path):
            return None

        print(
            "Video created:",
            output_path
        )

        # Copy outside temporary directory
        final_file = os.path.join(
            tempfile.gettempdir(),
            f"telegram_video_{os.getpid()}_{threading.get_ident()}.mp4"
        )

        shutil.copy2(
            output_path,
            final_file
        )

        return final_file

    except Exception as e:

        print(
            "Video generation error:",
            e
        )

        return None

    finally:

        shutil.rmtree(
            work_dir,
            ignore_errors=True
        )


# ============================================================
# START COMMAND
# ============================================================

@bot.message_handler(commands=["start"])
def start_command(message):

    bot.send_message(
        message.chat.id,

        """
🎬 *Pexels Video Generator Bot*

Send me a prompt.

Example:

`A beautiful lion walking through the African savanna`

I will:
🎥 Find matching videos
✂️ Combine the clips
🎙️ Add voiceover
📱 Create a vertical 720p video
⏱️ Make it approximately 60 seconds
📤 Send it back to you

👇 Send your prompt now.
        """,

        parse_mode="Markdown"
    )


# ============================================================
# PROMPT HANDLER
# ============================================================

@bot.message_handler(
    func=lambda message:
    message.text is not None
)
def handle_prompt(message):

    chat_id = message.chat.id

    prompt = message.text.strip()

    if not prompt:
        bot.send_message(
            chat_id,
            "❌ Please send a video prompt."
        )
        return

    status = bot.send_message(
        chat_id,

        "⏳ *Searching Pexels and creating your video...*\n\n"
        "This may take a few minutes.",

        parse_mode="Markdown"
    )

    def process():

        output_file = None

        try:

            output_file = generate_video(
                prompt
            )

            if not output_file:

                bot.edit_message_text(
                    "❌ I couldn't create the video.\n\n"
                    "Try another prompt.",

                    chat_id,
                    status.message_id
                )

                return

            bot.edit_message_text(
                "📤 *Video ready! Uploading to Telegram...*",

                chat_id,
                status.message_id,

                parse_mode="Markdown"
            )

            with open(
                output_file,
                "rb"
            ) as video:

                bot.send_video(
                    chat_id,

                    video,

                    caption=(
                        "🎬 *Your Video*\n\n"
                        f"📝 {prompt}\n\n"
                        "🎥 Videos provided by "
                        "Pexels\n"
                        "https://www.pexels.com"
                    ),

                    parse_mode="Markdown",

                    supports_streaming=True
                )

            bot.delete_message(
                chat_id,
                status.message_id
            )

        except Exception as e:

            print(
                "Bot error:",
                e
            )

            try:

                bot.edit_message_text(
                    f"❌ Error:\n`{str(e)[:1000]}`",

                    chat_id,
                    status.message_id,

                    parse_mode="Markdown"
                )

            except:
                pass

        finally:

            if output_file and os.path.exists(
                output_file
            ):

                try:
                    os.remove(output_file)
                except:
                    pass

    threading.Thread(
        target=process,
        daemon=True
    ).start()


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    threading.Thread(
        target=run_flask,
        daemon=True
    ).start()

    print(
        "🎬 Telegram Pexels Video Bot started!"
    )

    bot.infinity_polling(
        skip_pending=True
  )
