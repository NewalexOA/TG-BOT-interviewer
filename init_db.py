import sqlite3
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)

def create_user_table():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY, telegram_id INTEGER UNIQUE, correct_answers INTEGER, total_answers INTEGER)''')
    conn.commit()
    conn.close()

def create_answered_questions_table():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS answered_questions
                 (id INTEGER PRIMARY KEY, telegram_id INTEGER, question_id INTEGER, correct BOOLEAN)''')
    conn.commit()
    conn.close()

def create_questions_table():
    conn = sqlite3.connect('questions.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS questions
                 (id INTEGER PRIMARY KEY, question TEXT, category TEXT)''')
    conn.commit()
    conn.close()

def insert_sample_questions():
    conn = sqlite3.connect('questions.db')
    c = conn.cursor()
    questions = [
        ("What is a closure in Python?", "Programming"),
        ("Explain the difference between lists and tuples in Python.", "Programming"),
        ("What is the purpose of the `self` keyword in Python?", "Programming")
    ]
    c.executemany('INSERT INTO questions (question, category) VALUES (?, ?)', questions)
    conn.commit()
    conn.close()

def check_table_exists(database, table_name):
    conn = sqlite3.connect(database)
    c = conn.cursor()
    c.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'")
    table_exists = c.fetchone()
    conn.close()
    return table_exists is not None

if __name__ == '__main__':
    create_user_table()
    create_answered_questions_table()
    create_questions_table()
    insert_sample_questions()

    if check_table_exists('users.db', 'users'):
        print("Таблица 'users' успешно создана.")
    else:
        print("Ошибка создания таблицы 'users'.")

    if check_table_exists('users.db', 'answered_questions'):
        print("Таблица 'answered_questions' успешно создана.")
    else:
        print("Ошибка создания таблицы 'answered_questions'.")

    if check_table_exists('questions.db', 'questions'):
        print("Таблица 'questions' успешно создана.")
    else:
        print("Ошибка создания таблицы 'questions'.")
