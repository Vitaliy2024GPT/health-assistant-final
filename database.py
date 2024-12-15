import sqlite3
from flask import g
import os

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
    Создаём таблицы: users, nutrition
    users: id, name, chat_id (unique)
    nutrition: id, user_id, food_name, calories, date
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
    Добавляет нового пользователя с указанным name и chat_id.
    Возвращает id пользователя.
    Если chat_id уже существует, будет ошибка (можно обработать).
    """
    db = get_db()
    cursor = db.cursor()
    cursor.execute("INSERT INTO users (name, chat_id) VALUES (?, ?)", (name, chat_id))
    db.commit()
    return cursor.lastrowid

def get_user_by_chat_id(chat_id):
    """
    Возвращает пользователя по chat_id или None.
    """
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM users WHERE chat_id = ?", (chat_id,))
    return cursor.fetchone()

def add_meal(user_id, food_name, calories, date):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("INSERT INTO nutrition (user_id, food_name, calories, date) VALUES (?, ?, ?, ?)",
                   (user_id, food_name, calories, date))
    db.commit()
    return cursor.lastrowid

def get_user_meals(user_id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM nutrition WHERE user_id = ?", (user_id,))
    rows = cursor.fetchall()
    meals = [dict(row) for row in rows]
    return meals
