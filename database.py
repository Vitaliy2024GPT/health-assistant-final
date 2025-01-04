import sqlite3
from flask import g
import os
from datetime import date, timedelta

# Указываем директорию для базы данных
DATABASE_DIR = os.getenv("DATABASE_DIR", "/tmp")
os.makedirs(DATABASE_DIR, exist_ok=True)
DATABASE = os.path.join(DATABASE_DIR, "database.db")

def get_db():
    """
    Возвращает соединение с базой данных для текущего контекста запроса.
    """
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

def close_connection(exception):
    """
    Закрывает соединение с базой данных при завершении запроса.
    """
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    """
    Инициализирует базу данных и создаёт необходимые таблицы.
    """
    db = get_db()
    cursor = db.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            chat_id INTEGER UNIQUE NOT NULL,
            google_token TEXT DEFAULT NULL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS nutrition (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            food_name TEXT NOT NULL,
            calories INTEGER NOT NULL,
            date TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    db.commit()

def add_user(name, chat_id):
    """
    Добавляет нового пользователя по имени и chat_id.
    Возвращает id нового пользователя или существующего.
    """
    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute("INSERT INTO users (name, chat_id) VALUES (?, ?)", (name, chat_id))
        db.commit()
    except sqlite3.IntegrityError:
        pass  # Игнорируем ошибку, если пользователь уже существует
    cursor.execute("SELECT id FROM users WHERE chat_id = ?", (chat_id,))
    user = cursor.fetchone()
    return user["id"] if user else None

def get_user_by_chat_id(chat_id):
    """
    Получает пользователя по chat_id или возвращает None, если не найден.
    """
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM users WHERE chat_id = ?", (chat_id,))
    return cursor.fetchone()

def save_google_token(chat_id, token):
    """
    Сохраняет или обновляет Google Fit токен для пользователя.
    """
    db = get_db()
    cursor = db.cursor()
    cursor.execute("UPDATE users SET google_token = ? WHERE chat_id = ?", (token, chat_id))
    db.commit()

def get_google_token(chat_id):
    """
    Возвращает Google Fit токен пользователя по chat_id.
    """
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT google_token FROM users WHERE chat_id = ?", (chat_id,))
    row = cursor.fetchone()
    return row["google_token"] if row else None

def add_meal(user_id, food_name, calories, date_str):
    """
    Добавляет запись о приёме пищи для указанного user_id.
    """
    db = get_db()
    cursor = db.cursor()
    cursor.execute("INSERT INTO nutrition (user_id, food_name, calories, date) VALUES (?, ?, ?, ?)",
                   (user_id, food_name, calories, date_str))
    db.commit()
    return cursor.lastrowid

def get_user_meals(user_id):
    """
    Возвращает список приёмов пищи для user_id.
    """
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM nutrition WHERE user_id = ?", (user_id,))
    rows = cursor.fetchall()
    return [dict(row) for row in rows]

def get_meals_last_7_days(user_id):
    """
    Возвращает список приёмов пищи за последние 7 дней для данного пользователя.
    """
    db = get_db()
    cursor = db.cursor()
    today = date.today()
    seven_days_ago = today - timedelta(days=7)
    cursor.execute("""
        SELECT * FROM nutrition
        WHERE user_id = ?
        AND date >= ? AND date <= ?
    """, (user_id, seven_days_ago.isoformat(), today.isoformat()))
    rows = cursor.fetchall()
    return [dict(row) for row in rows]

def get_calories_last_7_days(user_id):
    """
    Возвращает суммарные калории за последние 7 дней.
    """
    db = get_db()
    cursor = db.cursor()
    today = date.today()
    seven_days_ago = today - timedelta(days=7)

    cursor.execute("""
        SELECT SUM(calories) as total_calories
        FROM nutrition
        WHERE user_id = ?
        AND date >= ? AND date <= ?
    """, (user_id, seven_days_ago.isoformat(), today.isoformat()))
    row = cursor.fetchone()
    return row["total_calories"] if row and row["total_calories"] is not None else 0

# Добавление тестового пользователя
def add_test_user():
    db = sqlite3.connect(DATABASE)
    cursor = db.cursor()
    cursor.execute("INSERT INTO users (chat_id, name, email) VALUES (192695390, 'Test User', 'test@example.com')")
    db.commit()
    db.close()

add_test_user()
