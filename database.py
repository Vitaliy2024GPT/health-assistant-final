import sqlite3
from flask import g
import os

# Указываем директорию для базы данных
DATABASE_DIR = os.getenv("DATABASE_DIR", "/tmp")
os.makedirs(DATABASE_DIR, exist_ok=True)
DATABASE = os.path.join(DATABASE_DIR, "database.db")

def get_db():
    """
    Возвращает соединение с базой данных SQLite.
    """
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

def close_connection(exception):
    """
    Закрывает соединение с базой данных, если оно открыто.
    """
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    """
    Создаёт таблицы: users, nutrition, user_chat (если они не существуют)
    """
    db = get_db()
    cursor = db.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL
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
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_chat (
            user_id INTEGER NOT NULL,
            chat_id INTEGER NOT NULL,
            UNIQUE(user_id, chat_id)
        )
    ''')
    db.commit()

def add_user(name, email):
    """
    Добавляет нового пользователя в таблицу users.
    Возвращает id добавленного пользователя.
    """
    db = get_db()
    cursor = db.cursor()
    cursor.execute("INSERT INTO users (name, email) VALUES (?, ?)", (name, email))
    db.commit()
    return cursor.lastrowid

def get_user_by_email(email):
    """
    Возвращает информацию о пользователе по email или None.
    """
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
    return cursor.fetchone()

def add_meal(user_id, food_name, calories, date):
    """
    Добавляет запись о приёме пищи для конкретного user_id.
    """
    db = get_db()
    cursor = db.cursor()
    cursor.execute("INSERT INTO nutrition (user_id, food_name, calories, date) VALUES (?, ?, ?, ?)",
                   (user_id, food_name, calories, date))
    db.commit()
    return cursor.lastrowid

def get_user_meals(user_id):
    """
    Возвращает список приёмов пищи для указанного пользователя.
    """
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM nutrition WHERE user_id = ?", (user_id,))
    rows = cursor.fetchall()
    meals = [dict(row) for row in rows]
    return meals

def link_user_chat(user_id, chat_id):
    """
    Связывает пользователя (user_id) с телеграм-чатом (chat_id).
    """
    db = get_db()
    cursor = db.cursor()
    cursor.execute("INSERT OR IGNORE INTO user_chat (user_id, chat_id) VALUES (?, ?)", (user_id, chat_id))
    db.commit()

def get_user_id_by_chat_id(chat_id):
    """
    Возвращает user_id по chat_id. Если не найдено, возвращает None.
    """
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT user_id FROM user_chat WHERE chat_id = ?", (chat_id,))
    row = cursor.fetchone()
    return row["user_id"] if row else None
