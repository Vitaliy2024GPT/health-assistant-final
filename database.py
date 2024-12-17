import sqlite3
from flask import g
import os
from datetime import date, timedelta

# Указываем директорию для базы данных
DATABASE_DIR = os.getenv("DATABASE_DIR", "/tmp")
os.makedirs(DATABASE_DIR, exist_ok=True)
DATABASE = os.path.join(DATABASE_DIR, "database.db")

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    """
    Создаём таблицы:
    users: (id, name, chat_id)
    nutrition: (id, user_id, food_name, calories, date)
    """
    db = get_db()
    cursor = db.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            chat_id INTEGER UNIQUE NOT NULL
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
    Возвращает id нового пользователя.
    """
    db = get_db()
    cursor = db.cursor()
    cursor.execute("INSERT INTO users (name, chat_id) VALUES (?, ?)", (name, chat_id))
    db.commit()
    return cursor.lastrowid

def get_user_by_chat_id(chat_id):
    """
    Получает пользователя по chat_id или возвращает None, если не найден.
    """
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM users WHERE chat_id = ?", (chat_id,))
    return cursor.fetchone()

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

def get_calories_last_7_days(user_id):
    """
    Возвращает суммарные калории за последние 7 дней.
    """
    db = get_db()
    cursor = db.cursor()

    today = date.today()
    seven_days_ago = today - timedelta(days=7)

    today_str = today.isoformat()
    seven_days_ago_str = seven_days_ago.isoformat()

    cursor.execute("""
        SELECT SUM(calories) as total_calories
        FROM nutrition
        WHERE user_id = ?
        AND date >= ? AND date <= ?
    """, (user_id, seven_days_ago_str, today_str))

    row = cursor.fetchone()
    if row and row["total_calories"] is not None:
        return row["total_calories"]
    else:
        return 0
