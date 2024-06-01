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
                 (id INTEGER PRIMARY KEY, telegram_id INTEGER, correct_answers INTEGER, total_answers INTEGER)''')
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
    c.execute('INSERT INTO users (telegram_id, correct_answers, total_answers) VALUES (?, ?, ?)', (telegram_id, 0, 0))
    conn.commit()
    conn.close()


def get_random_question(telegram_id):
    conn = connect_questions_db()
    c = conn.cursor()

    # Вероятность выбора вопроса, на который был дан неправильный ответ
    retry_probability = 0.3

    if random.random() < retry_probability:
        # Выбор вопроса, на который был дан неправильный ответ
        c.execute('''SELECT q.id, q.question, q.category FROM questions q
                     JOIN answered_questions aq ON q.id = aq.question_id
                     WHERE aq.telegram_id = ? AND aq.correct = 0
                     ORDER BY RANDOM() LIMIT 1''', (telegram_id,))
        question = c.fetchone()
        if question:
            conn.close()
            return question

    # Если не выбрали вопрос с неправильным ответом или если таких вопросов нет
    c.execute('''SELECT * FROM questions
                 WHERE id NOT IN (SELECT question_id FROM answered_questions WHERE telegram_id = ? AND correct = 1)
                 ORDER BY RANDOM() LIMIT 1''', (telegram_id,))
    question = c.fetchone()
    conn.close()
    return question


def update_user_stats(telegram_id, question_id, correct):
    conn = connect_db()
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
    conn.close()


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
