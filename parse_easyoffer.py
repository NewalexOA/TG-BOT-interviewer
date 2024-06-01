import requests
from bs4 import BeautifulSoup
import sqlite3

def get_html(url):
    response = requests.get(url)
    return response.text

def read_table(html):
    soup = BeautifulSoup(html, 'html.parser')
    questions = []
    question_rows = soup.find_all('tr')
    for row in question_rows:
        try:
            question_text_element = row.find('a')
            question_text = question_text_element.text.strip()
            category_element = row.find_all('td')[2]
            category_text = category_element.text.strip()
            # Пример правильного ответа, необходимо обновить в зависимости от структуры HTML
            correct_answer_element = row.find('td', class_='correct-answer')
            correct_answer = correct_answer_element.text.strip() if correct_answer_element else "N/A"
            questions.append((question_text, category_text, correct_answer))
            print(f"Question: {question_text}, Category: {category_text}, Answer: {correct_answer}")
        except Exception as e:
            print(f"Ошибка при парсинге строки: {e}")

    return questions

def parsing_easyoffer():
    url = "https://easyoffer.ru/rating/python_developer?page="
    parsed_data = []

    for page in range(1, 12):
        url_page = url + str(page).strip()
        print(f"Loading page: {url_page}")
        html = get_html(url_page)
        cur_page = read_table(html)
        parsed_data.extend(cur_page)

    create_database(parsed_data)

def create_database(questions):
    conn = sqlite3.connect('questions.db')
    c = conn.cursor()
    c.execute('DROP TABLE IF EXISTS questions')  # Удаление существующей таблицы
    c.execute('''CREATE TABLE questions
                 (id INTEGER PRIMARY KEY, question TEXT, category TEXT, correct_answer TEXT)''')
    c.executemany('INSERT INTO questions (question, category, correct_answer) VALUES (?, ?, ?)', questions)
    conn.commit()
    conn.close()

if __name__ == "__main__":
    parsing_easyoffer()
