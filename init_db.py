import sqlite3

def create_user_table():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY, telegram_id INTEGER, correct_answers INTEGER, total_answers INTEGER)''')
    conn.commit()
    conn.close()

def create_answered_questions_table():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS answered_questions
                 (id INTEGER PRIMARY KEY, telegram_id INTEGER, question_id INTEGER, correct BOOLEAN)''')
    conn.commit()
    conn.close()

if __name__ == '__main__':
    create_user_table()
    create_answered_questions_table()
    print("Таблицы успешно созданы")
