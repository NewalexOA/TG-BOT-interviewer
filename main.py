import sqlite3
import logging
from openai import OpenAI
from aiogram import Bot, Dispatcher, types, Router
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.fsm.storage.memory import MemoryStorage
from config import API_TOKEN, OPENAI_API_KEY

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Инициализация бота и диспетчера
bot = Bot(token=API_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
router = Router()
dp.include_router(router)

# Инициализация OpenAI
client = OpenAI(api_key=OPENAI_API_KEY, base_url="https://api.proxyapi.ru/openai/v1", timeout=30)
SYSTEM_PROMPT = ("Вы помощник, который помогает проверять правильность ответов. "
                 "Ваш ответ должен быть строго на русском языке, за исключением специальной лексики и терминов. "
                 "Ответ должен состоять из двух частей: "
                 "Первая часть - строго 'правильно' или 'неправильно', "
                 "Вторая часть - комментарий к ответу.")


# Функция для подключения к базе данных
def connect_db():
    return sqlite3.connect('users.db')


# Функция для подключения к базе данных вопросов
def connect_questions_db():
    return sqlite3.connect('questions.db')


# Функция для создания таблицы пользователей
def create_user_table():
    conn = connect_db()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                (id INTEGER PRIMARY KEY, telegram_id INTEGER, correct_answers INTEGER, total_answers INTEGER)''')
    conn.commit()
    conn.close()


# Функция для регистрации пользователя
def register_user(telegram_id):
    conn = connect_db()
    c = conn.cursor()
    c.execute('INSERT INTO users (telegram_id, correct_answers, total_answers) VALUES (?, ?, ?)', (telegram_id, 0, 0))
    conn.commit()
    conn.close()


# Функция для получения случайного вопроса из базы данных
def get_random_question():
    conn = connect_questions_db()
    c = conn.cursor()
    c.execute('SELECT id, question FROM questions ORDER BY RANDOM() LIMIT 1')
    question = c.fetchone()
    conn.close()
    return question


# Функция для проверки ответа с использованием OpenAI
def check_answer_with_openai(question, user_answer):
    try:
        completion = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Вопрос: {question}"},
                {"role": "user", "content": f"Ответ: {user_answer}. Это ответ правильный?"}
            ]
        )
        gpt_answer_content = completion.choices[0].message.content.strip()
        logging.info(f"OpenAI response: {gpt_answer_content}")

        # Разделяем ответ на две части
        parts = gpt_answer_content.split('\n', 1)
        correctness = parts[0].strip().lower()
        explanation = parts[1].strip() if len(parts) > 1 else ""

        return correctness, explanation
    except Exception as e:
        logging.error(f"Error checking answer with OpenAI: {e}")
        return "ошибка", "Ошибка при обращении к API"


# Хэндлер для команды /start
@router.message(Command("start"))
async def send_welcome(message: Message):
    telegram_id = message.from_user.id
    conn = connect_db()
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE telegram_id=?', (telegram_id,))
    user = c.fetchone()
    if user is None:
        register_user(telegram_id)
        await message.reply("Привет! Я бот-тренажер. Ты зарегистрирован.")
    else:
        await message.reply("Привет! Ты уже зарегистрирован.")


# Хэндлер для команды /question
@router.message(Command("question"))
async def send_question(message: Message):
    question = get_random_question()
    if question:
        question_id, question_text = question
        await message.reply(f"Вопрос: {question_text}")
        # Сохраним текст вопроса, чтобы потом проверить ответ
        bot_data[message.from_user.id] = question_text
    else:
        await message.reply("В базе данных нет вопросов.")


# Хэндлер для обработки текстовых сообщений (ответов)
@router.message()
async def handle_answer(message: Message):
    answer_text = message.text
    telegram_id = message.from_user.id

    question_text = bot_data.get(telegram_id)
    if not question_text:
        await message.reply("Пожалуйста, сначала запросите вопрос с помощью команды /question.")
        return

    correctness, explanation = check_answer_with_openai(question_text, answer_text)

    conn = connect_db()
    c = conn.cursor()
    if correctness == "правильно":
        c.execute(
            'UPDATE users SET correct_answers = correct_answers + 1, total_answers = total_answers + 1 WHERE telegram_id=?',
            (telegram_id,))
        await message.reply(f"Правильно! {explanation}")
    elif correctness == "неправильно":
        c.execute('UPDATE users SET total_answers = total_answers + 1 WHERE telegram_id=?', (telegram_id,))
        await message.reply(f"Неправильно. {explanation}")
    else:
        await message.reply(f"Ошибка при проверке ответа: {explanation}")

    conn.commit()
    conn.close()

    # Удаляем текст вопроса из bot_data после проверки ответа
    del bot_data[telegram_id]


if __name__ == '__main__':
    create_user_table()
    bot_data = {}  # Словарь для хранения текста вопросов по ID пользователей
    dp.run_polling(bot, skip_updates=True)
