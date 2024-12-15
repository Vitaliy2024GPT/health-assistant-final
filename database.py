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
    Если соединение еще не установлено, создаёт его и возвращает.
    """
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

def close_connection(exception):
    """
    Закрывает соединение с базой данных, если оно открыто.
    Эта функция может быть зарегистрирована в Flask и будет вызываться автоматически.
    """
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    """
    Создаёт таблицы 'users' и 'nutrition', если они не существуют.
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
    db.commit()

def add_user(name, email):
    """
    Добавляет нового пользователя в таблицу users.
    Возвращает id добавленного пользователя.
    Если email уже существует, вернёт ошибку (можете обработать её снаружи).
    """
    db = get_db()
    cursor = db.cursor()
    cursor.execute("INSERT INTO users (name, email) VALUES (?, ?)", (name, email))
    db.commit()
    return cursor.lastrowid

def get_user_by_email(email):
    """
    Возвращает информацию о пользователе по email.
    Если пользователя нет, вернёт None.
    """
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
    user = cursor.fetchone()
    return user  # user будет объектом Row или None

def add_meal(user_id, food_name, calories, date):
    """
    Добавляет запись о приёме пищи в таблицу nutrition.
    user_id — id пользователя из таблицы users.
    food_name — название продукта.
    calories — количество калорий.
    date — строка с датой, например "2024-12-16".
    """
    db = get_db()
    cursor = db.cursor()
    cursor.execute("INSERT INTO nutrition (user_id, food_name, calories, date) VALUES (?, ?, ?, ?)",
                   (user_id, food_name, calories, date))
    db.commit()
    return cursor.lastrowid

def get_user_meals(user_id):
    """
    Возвращает список всех приёмов пищи для указанного пользователя.
    Возвращает список словарей формата:
    [{'id': 1, 'user_id': 1, 'food_name': 'Apple', 'calories': 100, 'date': '2024-12-16'}, ...]
    Если нет записей, вернёт пустой список.
    """
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM nutrition WHERE user_id = ?", (user_id,))
    rows = cursor.fetchall()
    meals = [dict(row) for row in rows]  # конвертируем Row объекты в словари
    return meals
