import subprocess
import telebot
import os
import wave
import json
import vosk
from vosk import Model, KaldiRecognizer

# Токен полученный у botfather
TOKEN = ''

# Путь к модели vosk
VOSK_MODEL_PATH = 'model/vosk'

# Папка с временными файлами
TEMP_DIR = 'temp'

# Максимальная длина сообщения в сек
MAX_DURATION = 30

# Проверка доступности ffmpeg
try:
    subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
except Exception as e:
    raise RuntimeError("FFmpeg не установлен или не доступен в PATH") from e

# Если папки нет - создаем
os.makedirs(TEMP_DIR, exist_ok=True)

# Инициализация бота
bot = telebot.TeleBot(TOKEN)

# Загрузка модели в vosk
try:
    model = vosk.Model(VOSK_MODEL_PATH)
    print(f'Модель {VOSK_MODEL_PATH} успешно загружена')
except Exception as e:
    print(f'Ошибка загрузки: {e}')
    model = None # Если модель не загрузилась, бот продолжит работу без распознования речи

# Конвертирует OGG в WAV 16кГц
def convert_ogg_to_wav(ogg_path: str) -> str:
    if not os.path.exists(ogg_path):
        raise FileNotFoundError(f"Файл {ogg_path} не найден")
    wav_path = os.path.splitext(ogg_path)[0] + ".wav"
    # Команда для ffmpeg
    cmd = [
        'ffmpeg',
        '-i', ogg_path,
        '-ar', '16000',
        '-ac', '1',
        '-y',
        '-hide_banner',
        '-loglevel', 'error',
        wav_path
    ]
    # Загрузка и конвертация
    try:
        subprocess.run(cmd, check=True)
        return wav_path
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Ошибка конвертации аудио: {e}") from e

# Преобразует аудио в текст с помощью Vosk
def transcribe_audio(audio_path: str) -> str:
    if not model:
        return "Ошибка: модель распознавания не загружена"
    # Открываем WAV файл
    try:
        with wave.open(audio_path, 'rb') as wf:
            if wf.getnchannels() != 1 or wf.getsampwidth() != 2:
                return "Неверный формат аудио: требуется mono, 16-bit PCM"

    # Инициализируем распознаватель
            rec = vosk.KaldiRecognizer(model, wf.getframerate())
            rec.SetWords(True)

    # Чтение и обработка аудиоданных
            results = []
            while True:
                data = wf.readframes(4000)
                if len(data) == 0 or not data:
                    break
                if rec.AcceptWaveform(data):
                    results.append(json.loads(rec.Result()).get("text", ""))
    # Финализация распознавания
            final_result = json.loads(rec.FinalResult())
            results.append(final_result.get("text", ""))

            return " ".join(filter(None, results))#([text for text in results if text])
    except Exception as e:
        return f"Ошибка распознавания: {str(e)}"

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    # Обработка команд /start и /help
    bot.reply_to(
        message,
        "Привет! Я бот для преобразования голосовых сообщений в текст.\n\n"
        "Отправь мне голосовое сообщение, и я переведу его в текст!"
    )

@bot.message_handler(content_types=['voice'])
def handle_voice(message):
    # Обработка голосовых сообщений
    try:
        # Проверка длительности
        if message.voice.duration > MAX_DURATION:
            bot.reply_to(
                message,
                f"Сообщение слишком длинное (максимум {MAX_DURATION} секунд)"
            )
            return
        # Скачивание голосового сообщения
        file_info = bot.get_file(message.voice.file_id)
        ogg_path = os.path.join(TEMP_DIR, f"voice_{message.id}.ogg")

        with open(ogg_path, 'wb') as f:
            f.write(bot.download_file(file_info.file_path))

        # Конвертация и распознавание
        wav_path = convert_ogg_to_wav(ogg_path)
        bot.send_chat_action(message.chat.id, 'typing')
        text = transcribe_audio(wav_path)

        # Отправка результата
        reply = f"Распознанный текст:\n\n{text}" if text else "Не удалось распознать текст"
        bot.reply_to(message, reply)

    except Exception as e:
        error_msg = f"Ошибка при обработке: {str(e)}"
        print(error_msg)
        bot.reply_to(message, "Произошла ошибка при обработке сообщения")
    finally:
        # Очистка временных файлов
        for path in [ogg_path, wav_path]:
            try:
                if path and os.path.exists(path):
                    os.remove(path)
            except:
                pass

if __name__ == "__main__":
    print("Бот запущен...")
    bot.infinity_polling()

