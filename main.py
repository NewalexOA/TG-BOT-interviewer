import logging
from aiogram import Bot, Dispatcher, types, Router
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.fsm.storage.memory import MemoryStorage
from config import API_TOKEN
from backend import (register_user, get_random_question, update_user_stats, check_answer_with_openai)

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Инициализация бота и диспетчера
bot = Bot(token=API_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
router = Router()
dp.include_router(router)

@router.message(Command("start"))
async def cmd_start(message: Message):
    logging.info(f"Регистрация пользователя с telegram_id: {message.from_user.id}")
    register_user(message.from_user.id)
    await message.answer("Привет! Я помогу тебе подготовиться к собеседованию по Python. Вы успешно зарегистрированы! Готов начать?")

@router.message(Command("question"))
async def cmd_question(message: Message):
    logging.info(f"Получение вопроса для пользователя с telegram_id: {message.from_user.id}")
    question = get_random_question(message.from_user.id)
    if question:
        question_id, question_text, category = question
        bot_data[message.from_user.id] = (question_id, question_text)
        logging.info(f"Отправка вопроса пользователю: {question_text}")
        await message.answer(f"Вопрос: {question_text}\nКатегория: {category}")
    else:
        logging.info("Вопросы закончились для пользователя")
        await message.answer("Вопросы закончились, попробуйте позже.")

@router.message()
async def handle_answer(message: Message):
    telegram_id = message.from_user.id
    user_answer = message.text
    logging.info(f"Получен ответ от пользователя {telegram_id}: {user_answer}")
    if telegram_id in bot_data:
        question_id, question_text = bot_data[telegram_id]
        correctness, explanation = check_answer_with_openai(question_text, user_answer)
        logging.info(f"Проверка ответа: {correctness}, объяснение: {explanation}")
        await message.answer(f"{correctness}\n{explanation}")
        update_user_stats(telegram_id, question_id, correctness.lower() == "правильно")
        del bot_data[telegram_id]
    else:
        logging.info("Не найден вопрос для данного ответа")
        await message.answer("Используйте команду /question, чтобы получить вопрос.")

if __name__ == '__main__':
    bot_data = {}  # Словарь для хранения текста вопросов по ID пользователей
    dp.run_polling(bot, skip_updates=True)
