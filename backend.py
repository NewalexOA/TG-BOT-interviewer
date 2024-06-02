import sqlite3
import logging
import random
from openai import OpenAI
from config import SYSTEM_PROMPT, OPENAI_API_KEY

# Инициализация OpenAI
client = OpenAI(api_key=OPENAI_API_KEY, base_url="https://api.proxyapi.ru/openai/v1", timeout=30)


def connect_db():
    return sqlite3.connect('users.db')


def connect_questions_db():
    return sqlite3.connect('questions.db')


def create_user_table():
    conn = connect_db()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY, telegram_id INTEGER UNIQUE, correct_answers INTEGER, total_answers INTEGER)''')
    conn.commit()
    conn.close()


def create_answered_questions_table():
    conn = connect_db()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS answered_questions
                 (id INTEGER PRIMARY KEY, telegram_id INTEGER, question_id INTEGER, correct BOOLEAN)''')
    conn.commit()
    conn.close()


def register_user(telegram_id):
    conn = connect_db()
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE telegram_id = ?', (telegram_id,))
    user = c.fetchone()
    if user:
        logging.info(f"Пользователь с telegram_id {telegram_id} уже зарегистрирован.")
    else:
        c.execute('INSERT INTO users (telegram_id, correct_answers, total_answers) VALUES (?, ?, ?)',
                  (telegram_id, 0, 0))
        conn.commit()
    conn.close()


def check_questions_table():
    conn = connect_questions_db()
    c = conn.cursor()
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='questions'")
    table_exists = c.fetchone()
    conn.close()
    return table_exists is not None


def get_random_question(telegram_id):
    with connect_db() as users_conn:
        users_cursor = users_conn.cursor()

        # Получение списка ID вопросов, на которые был дан неправильный ответ
        users_cursor.execute('''SELECT question_id 
                                FROM answered_questions
                                WHERE telegram_id = ? AND correct = 0''', (telegram_id,))
        wrong_answers = [row[0] for row in users_cursor.fetchall()]

        # Получение списка ID вопросов, на которые был дан правильный ответ
        users_cursor.execute('''SELECT question_id 
                                FROM answered_questions
                                WHERE telegram_id = ? AND correct = 1''', (telegram_id,))
        correct_answers = [row[0] for row in users_cursor.fetchall()]

    with connect_questions_db() as questions_conn:
        questions_cursor = questions_conn.cursor()

        # Проверяем наличие таблицы questions
        if not check_questions_table():
            logging.error("Таблица 'questions' не существует в базе данных.")
            raise sqlite3.OperationalError("no such table: questions")

        logging.info(f"Получаем случайный вопрос для пользователя с telegram_id: {telegram_id}")

        # Вероятность выбора вопроса, на который был дан неправильный ответ
        retry_probability = 0.3

        if wrong_answers and random.random() < retry_probability:
            logging.info("Попытка выбрать вопрос с неправильным ответом")
            # Выбор вопроса, на который был дан неправильный ответ
            questions_cursor.execute(f'''SELECT id, question, category 
                                        FROM questions
                                        WHERE id IN ({",".join("?" * len(wrong_answers))})
                                        ORDER BY RANDOM() LIMIT 1''', wrong_answers)
            question = questions_cursor.fetchone()
            if question:
                logging.info(f"Выбран вопрос с неправильным ответом: {question}")
                return question

        logging.info("Попытка выбрать новый вопрос")
        # Если не выбрали вопрос с неправильным ответом или если таких вопросов нет
        if correct_answers:
            questions_cursor.execute(f'''SELECT * FROM questions
                                        WHERE id NOT IN ({",".join("?" * len(correct_answers))})
                                        ORDER BY RANDOM() LIMIT 1''', correct_answers)
        else:
            questions_cursor.execute('''SELECT * FROM questions
                                        ORDER BY RANDOM() LIMIT 1''')
        question = questions_cursor.fetchone()
        if question:
            logging.info(f"Выбран новый вопрос: {question}")
        else:
            logging.info("Не удалось выбрать новый вопрос")
        return question


def update_user_stats(telegram_id, question_id, correct):
    with connect_db() as conn:
        c = conn.cursor()
        c.execute('SELECT correct_answers, total_answers FROM users WHERE telegram_id = ?', (telegram_id,))
        user = c.fetchone()
        if user:
            correct_answers, total_answers = user
            if correct:
                correct_answers += 1
            total_answers += 1
            c.execute('UPDATE users SET correct_answers = ?, total_answers = ? WHERE telegram_id = ?',
                      (correct_answers, total_answers, telegram_id))
            c.execute('INSERT INTO answered_questions (telegram_id, question_id, correct) VALUES (?, ?, ?)',
                      (telegram_id, question_id, correct))
            conn.commit()


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
        parts = gpt_answer_content.split('.', 1)
        correctness = parts[0].strip()
        explanation = parts[1].strip() if len(parts) > 1 else ""

        return correctness, explanation
    except Exception as e:
        logging.error(f"Error checking answer with OpenAI: {e}")
        return "Ошибка", "Ошибка при обращении к API"
