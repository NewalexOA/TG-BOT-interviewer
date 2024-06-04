import logging
import asyncio
import os
import ffmpeg
from aiogram import Bot, Dispatcher, Router, types
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.fsm.storage.memory import MemoryStorage
from backend import register_user, get_random_question, update_user_stats, check_answer_with_openai, calculate_user_stats
from config import API_TOKEN, ANSWER_TIMEOUT, WHISPER_API_TOKEN
from openai import OpenAI


# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Инициализация бота, диспетчера и маршрутизатора
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()
dp.include_router(router)


# Глобальный словарь для хранения данных о вопросах пользователя
bot_data = {}

# Функция для создания основного меню
def main_menu():
    markup = types.InlineKeyboardMarkup(inline_keyboard=[])
    question_button = types.InlineKeyboardButton(text="Получить вопрос", callback_data="get_question")
    stats_button = types.InlineKeyboardButton(text="Статистика", callback_data="check_stats")
    markup.inline_keyboard.append([question_button, stats_button])
    return markup

@router.message(Command("menu"))
async def show_menu(message: types.Message):
    await message.answer("Выберите действие:", reply_markup=main_menu())

@router.callback_query(lambda c: c.data == "get_question")
async def handle_get_question(callback_query: types.CallbackQuery):
    await cmd_question(callback_query.message)

@router.callback_query(lambda c: c.data == "check_stats")
async def handle_check_stats(callback_query: types.CallbackQuery):
    telegram_id = callback_query.from_user.id
    total_answers, correct_percentage = calculate_user_stats(telegram_id)
    response_message = f"Ваша статистика:\nВсего ответов: {total_answers}\nПроцент правильных ответов: {correct_percentage:.2f}%"
    await bot.send_message(telegram_id, response_message)
    await callback_query.answer()

async def stop_receiving_answers(user_id):
    if user_id in bot_data:
        del bot_data[user_id]
        await bot.send_message(user_id, "Время на ответ истекло. Введите /question, чтобы получить новый вопрос.")

@router.message(Command("start"))
async def cmd_start(message: Message):
    logging.info(f"Регистрация пользователя с telegram_id: {message.from_user.id}")
    register_user(message.from_user.id)
    welcome_message = "Привет! Я помогу тебе подготовиться к собеседованию по Python. Вы успешно зарегистрированы! Готов начать?"
    await message.answer(welcome_message, reply_markup=main_menu())

@router.message(Command("question"))
async def cmd_question(message: Message):
    logging.info(f"Получение вопроса для пользователя с telegram_id: {message.from_user.id}")
    question = get_random_question(message.from_user.id)
    if question:
        question_id, question_text, category = question
        bot_data[message.from_user.id] = (question_id, question_text)
        await message.answer(f"Вопрос: {question_text}\nКатегория: {category}")
        # Убедимся, что задача таймера корректно установлена
        asyncio.create_task(timer_task(message.from_user.id), name=f"timer_{message.from_user.id}")

async def timer_task(user_id):
    logging.info(f"Таймер запущен для пользователя {user_id}")
    await asyncio.sleep(ANSWER_TIMEOUT)
    logging.info(f"Таймер истек для пользователя {user_id}")
    await stop_receiving_answers(user_id)


@router.message(lambda message: message.voice is not None)
async def handle_voice(message: Message):
    logging.info(f"Получено голосовое сообщение от пользователя {message.from_user.id}")
    file_info = await bot.get_file(message.voice.file_id)
    file_path = file_info.file_path
    voice_file = f"voice_{message.from_user.id}.ogg"
    await bot.download_file(file_path, voice_file)

    # Преобразование аудио в формат, поддерживаемый API
    wav_file = f"voice_{message.from_user.id}.wav"
    ffmpeg.input(voice_file).output(wav_file).run(overwrite_output=True)

    client = OpenAI(api_key = WHISPER_API_TOKEN)

    # Отправка файла на сервер OpenAI для транскрипции
    try:
        with open(wav_file, 'rb') as audio_file:
            response = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file
            )

        if response:
            user_answer = response['text']
            await handle_answer(message, user_answer)
        else:
            logging.error(f"Ошибка транскрипции: {response}")
            await message.answer("Произошла ошибка при распознавании аудио. Пожалуйста, попробуйте еще раз.")
    except Exception as e:
        logging.error(f"Произошла ошибка при обработке аудио: {e}")
        await message.answer("Произошла ошибка при распознавании аудио. Пожалуйста, попробуйте еще раз.")
    finally:
        os.remove(voice_file)
        os.remove(wav_file)

@router.message(Command("stats"))
async def cmd_stats(message: Message):
    telegram_id = message.from_user.id
    total_answers, correct_percentage = calculate_user_stats(telegram_id)
    response_message = f"Ваша статистика:\nВсего ответов: {total_answers}\nПроцент правильных ответов: {correct_percentage:.2f}%"
    await message.answer(response_message)

@router.message(lambda message: message.text is not None)
async def handle_text_message(message: Message):
    await handle_answer(message, message.text)

async def handle_answer(message: Message, user_answer: str):
    user_id = message.from_user.id
    if user_id in bot_data:
        question_id, question_text = bot_data[user_id]
        correctness, explanation = check_answer_with_openai(question_text, user_answer)
        await message.answer(f"{correctness}\n{explanation}")
        update_user_stats(user_id, question_id, correctness.lower() == "правильно")
        del bot_data[user_id]

if __name__ == '__main__':
    dp.run_polling(bot)  # Укажите объект bot при вызове метода run_polling
