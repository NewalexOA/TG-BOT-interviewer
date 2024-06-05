import logging
import asyncio
import os
import ffmpeg
from aiogram import Bot, Dispatcher, Router, types
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.storage.memory import MemoryStorage
from backend import register_user, get_random_question, update_user_stats, check_answer_with_openai, \
    calculate_user_stats
from config import API_TOKEN, ANSWER_TIMEOUT, OPENAI_API_KEY
from openai import OpenAI
import json
import re

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


# Функция для экранирования специальных символов в MarkdownV2
def escape_markdown_v2(text: str) -> str:
    return re.sub(r'([_*\[\]()~`>#+\-=|{}.!\\])', r'\\\1', text)


# Функция для создания основного меню
def main_menu():
    markup = types.InlineKeyboardMarkup(inline_keyboard=[])
    question_button = types.InlineKeyboardButton(text="Получить вопрос", callback_data="get_question")
    stats_button = types.InlineKeyboardButton(text="Статистика", callback_data="check_stats")
    markup.inline_keyboard.append([question_button, stats_button])
    return markup


@router.message(Command("menu"))
async def show_menu(message: types.Message):
    logging.info(f"Показ меню для пользователя с telegram_id: {message.from_user.id}")
    await message.answer("Выберите действие:", reply_markup=main_menu(), parse_mode='MarkdownV2')


@router.callback_query(lambda c: c.data == "get_question")
async def handle_get_question(callback_query: CallbackQuery):
    telegram_id = callback_query.from_user.id
    logging.info(f"Получение вопроса для пользователя с telegram_id (callback_query): {telegram_id}")
    await cmd_question(callback_query.message, telegram_id)


@router.callback_query(lambda c: c.data == "check_stats")
async def handle_check_stats(callback_query: CallbackQuery):
    telegram_id = callback_query.from_user.id
    logging.info(f"Проверка статистики для пользователя с telegram_id: {telegram_id}")
    total_answers, correct_percentage = calculate_user_stats(telegram_id)
    response_message = f"Ваша статистика:\nВсего ответов: {total_answers}\nПроцент правильных ответов: {correct_percentage:.2f}%"
    response_message = escape_markdown_v2(response_message)
    await bot.send_message(telegram_id, response_message, parse_mode='MarkdownV2')
    await callback_query.answer()


async def stop_receiving_answers(user_id):
    if user_id in bot_data:
        del bot_data[user_id]
        logging.info(f"Остановка получения ответов для пользователя с telegram_id: {user_id}")
        await bot.send_message(user_id, "Время на ответ истекло. Введите /question, чтобы получить новый вопрос.",
                               parse_mode='MarkdownV2')


@router.message(Command("start"))
async def cmd_start(message: Message):
    user_id = message.from_user.id
    logging.info(f"Регистрация пользователя с telegram_id: {user_id}")
    register_user(user_id)
    welcome_message = "Привет! Я помогу тебе подготовиться к собеседованию по Python. Вы успешно зарегистрированы! Готов начать?"
    welcome_message = escape_markdown_v2(welcome_message)
    await message.answer(welcome_message, reply_markup=main_menu(), parse_mode='MarkdownV2')


@router.message(Command("question"))
async def cmd_question(message: Message, user_id: int = None):
    if user_id is None:
        user_id = message.from_user.id
    logging.info(f"Начало выполнения cmd_question для пользователя с telegram_id: {user_id}")
    question = get_random_question(user_id)
    if question:
        question_id, question_text, category = question
        bot_data[user_id] = (question_id, question_text)
        response_message = f"Вопрос: {escape_markdown_v2(question_text)}\nКатегория: {escape_markdown_v2(category)}"
        await message.answer(response_message, parse_mode='MarkdownV2')
        if not message.from_user.is_bot:
            logging.info(f"Установка таймера для пользователя с telegram_id: {user_id}")
            asyncio.create_task(timer_task(user_id), name=f"timer_{user_id}")
    else:
        logging.error(f"Не удалось получить вопрос для пользователя с telegram_id: {user_id}")


async def timer_task(user_id):
    logging.info(f"Таймер запущен для пользователя {user_id}")
    await asyncio.sleep(ANSWER_TIMEOUT)
    logging.info(f"Таймер истек для пользователя {user_id}")
    await stop_receiving_answers(user_id)


@router.message(lambda message: message.voice is not None)
async def handle_voice(message: Message):
    user_id = message.from_user.id
    logging.info(f"Получено голосовое сообщение от пользователя {user_id}")
    file_info = await bot.get_file(message.voice.file_id)
    file_path = file_info.file_path
    voice_file = f"voice_{user_id}.ogg"
    await bot.download_file(file_path, voice_file)

    # Преобразование аудио в формат, поддерживаемый API
    wav_file = f"voice_{user_id}.wav"
    ffmpeg.input(voice_file).output(wav_file).run(overwrite_output=True)

    client = OpenAI(api_key=OPENAI_API_KEY, base_url="https://api.proxyapi.ru/openai/v1", timeout=ANSWER_TIMEOUT)

    # Отправка файла на сервер OpenAI для транскрипции
    try:
        with open(wav_file, 'rb') as audio_file:
            response = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file
            )

        if response:
            response_data = response.json()
            logging.info(f"Response data: {response_data}")  # Печать полного ответа для отладки

            # Убедимся, что response_data является словарем, а не строкой
            if isinstance(response_data, str):
                response_data = json.loads(response_data)

            user_answer = response_data['text']
            await handle_answer(message, user_answer)
        else:
            logging.error(f"Ошибка транскрипции: {response}")
            await message.answer("Произошла ошибка при распознавании аудио. Пожалуйста, попробуйте еще раз.",
                                 parse_mode='MarkdownV2')
    except Exception as e:
        logging.error(f"Произошла ошибка при обработке аудио: {e}")
        await message.answer("Произошла ошибка при распознавании аудио. Пожалуйста, попробуйте еще раз.",
                             parse_mode='MarkdownV2')
    finally:
        os.remove(voice_file)
        os.remove(wav_file)


@router.message(Command("stats"))
async def cmd_stats(message: Message):
    user_id = message.from_user.id
    logging.info(f"Проверка статистики для пользователя с telegram_id: {user_id}")
    total_answers, correct_percentage = calculate_user_stats(user_id)
    response_message = f"Ваша статистика:\nВсего ответов: {total_answers}\nПроцент правильных ответов: {correct_percentage:.2f}%"
    response_message = escape_markdown_v2(response_message)
    await message.answer(response_message, parse_mode='MarkdownV2')


@router.message(lambda message: message.text is not None)
async def handle_text_message(message: Message):
    await handle_answer(message, message.text)


async def handle_answer(message: types.Message, user_answer: str):
    user_id = message.from_user.id
    logging.info(f"Обработка ответа для пользователя с telegram_id: {user_id}")
    if user_id in bot_data:
        question_id, question_text = bot_data[user_id]
        logging.info(f"Вопрос ID: {question_id}, Текст вопроса: {question_text}, Ответ пользователя: {user_answer}")

        correctness, explanation = check_answer_with_openai(question_text, user_answer)
        logging.info(f"Проверка ответа с OpenAI: корректность - {correctness}, объяснение - {explanation}")

        # Экранируем специальные символы и форматируем ответ без использования блоков кода
        formatted_explanation = f"*{escape_markdown_v2(correctness)}*\n\n{escape_markdown_v2(explanation)}"
        await message.answer(formatted_explanation, parse_mode='MarkdownV2')

        if correctness.lower() == "правильно":
            correct = 1
        else:
            correct = 1
        update_user_stats(user_id, question_id, correct)
        del bot_data[user_id]
        logging.info(f"Данные о вопросе удалены для пользователя с telegram_id: {user_id}")
    else:
        logging.warning(f"Нет данных о вопросе для пользователя с telegram_id: {user_id}")


if __name__ == '__main__':
    logging.info(f"ID бота: {bot.id}")
    dp.run_polling(bot)  # Укажите объект bot при вызове метода run_pollинг

# TODO Добавить функцию обнуления статистики