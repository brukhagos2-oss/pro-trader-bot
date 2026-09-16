import os
import time
import threading
from gtts import gTTS
from moviepy.editor import TextClip, AudioFileClip, ColorClip, CompositeVideoClip
import telebot
from telebot import types

# ============================================================
# CONFIG (Telegram Bot Token)
# ============================================================
TELEGRAM_TOKEN = "8581232155:AAF5IYyCs0rKtp9VDktOz0HxwGXAOFbhsKc"

if not TELEGRAM_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN environment variable is missing.")

bot = telebot.TeleBot(TELEGRAM_TOKEN)

# ============================================================
# VIDEO GENERATION ENGINE (MoviePy + gTTS)
# ============================================================
def generate_ai_style_video(prompt_text, output_filename="output_video.mp4"):
    try:
        print(f"Generating video for prompt: {prompt_text}")
        
        # 1. ጽሁፉን ወደ ድምፅ መቀየር (Voiceover)
        tts = gTTS(text=prompt_text, lang='en', slow=False)
        audio_path = "voiceover.mp3"
        tts.save(audio_path)
        
        # የድምፁን ርዝመት (Duration) ማወቅ
        audio_clip = AudioFileClip(audio_path)
        duration = audio_clip.duration
        
        # ቢበዛ እስከ 5 ደቂቃ (300 ሰኮንድ) ብቻ እንዲሆን መወሰን
        if duration > 300:
            duration = 300
            audio_clip = audio_clip.subclip(0, 300)

        # 2. የቪዲዮውን ከለር ወይም ዳራ መፍጠር (ለምሳሌ ጥቁር ዳራ 720p)
        bg_clip = ColorClip(size=(720, 1280), color=(15, 15, 25), duration=duration)

        # 3. ቴክስቱን በቪዲዮው ላይ ማሳየት (Text Overlay)
        # ማስታወሻ: TextClip ዩኒኮድ/አማርኛ በትክክል እንዲያነብ فونቱ (Font) ሊያስፈልግ ስለሚችል በእንግሊዝኛ ማድረግ ይመረጣል
        txt_clip = TextClip(
            prompt_text, 
            fontsize=40, 
            color='white', 
            size=(680, 1200), 
            method='caption'
        )
        txt_clip = txt_clip.set_duration(duration).set_position('center')

        # 4. ቪዲዮውን እና ድምፁን ማቀናጀት
        video = CompositeVideoClip([bg_clip, txt_clip])
        video = video.set_audio(audio_clip)

        # 5. ቪዲዮውን በፋይል መልክ ማስቀመጥ (Rendering)
        # ራም (RAM) ላለማጨናነቅ ዝቅተኛ ፕረሴት (Preset) እንጠቀማለን
        video.write_videofile(
            output_filename, 
            fps=24, 
            codec='libx264', 
            audio_codec='aac', 
            preset='ultrafast',
            logger=None
        )

        # ሪሶርሶችን መዝጋት
        audio_clip.close()
        video.close()
        
        if os.path.exists(audio_path):
            os.remove(audio_path)
            
        return output_filename

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
            "🎬 *AI Video Generator Bot*\n\n"
            "ጽሁፍ (Prompt) ላክልኝ፣ እኔ ደግሞ ያንን ጽሁፍ መሰረት በማድረግ ድምፅ ያለው ቪዲዮ አሰናድቼ እልክልሃለሁ!\n\n"
            "⚠️ *ማስታወሻ:* ቪዲዮው እስኪሰራ ከጥቂት ሰኮንዶች እስከ ደቂቃዎች ሊወስድ ይችላል።"
        ),
        parse_mode="Markdown"
    )

@bot.message_handler(func=lambda message: True)
def handle_prompt(message):
    chat_id = message.chat.id
    user_prompt = message.text

    msg = bot.send_message(
        chat_id,
        "⏳ *ቪዲዮዎ እየተሰራ ነው... እባክዎ ትንሽ ይጠብቁ።*",
        parse_mode="Markdown"
    )

    # ሰርቨሩ እንዳይጨናነቅ በ Background Thread ማሰራት
    def process_video():
        output_file = generate_ai_style_video(user_prompt)
        
        if output_file and os.path.exists(output_file):
            try:
                with open(output_file, 'rb') as video_file:
                    bot.send_video(
                        chat_id,
                        video_file,
                        caption=f"🎥 *Generated for:* {user_prompt}",
                        parse_mode="Markdown"
                    )
                bot.delete_message(chat_id, msg.message_id)
            except Exception as e:
                bot.send_message(chat_id, f"❌ ቪዲዮውን ለመላክ አልተቻለም: {e}")
            
            # ከተላከ በኋላ ፋይሉን ከሰርቨር ማጥፋት
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
    print("Video Generator Bot started polling...")
    bot.infinity_polling(skip_pending=True)
