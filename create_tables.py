import sqlite3

conn = sqlite3.connect('database.db')
cursor = conn.cursor()

# Создание таблицы users
cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        chat_id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        email TEXT NOT NULL
    )
''')

# Создание таблицы health_data
cursor.execute('''
    CREATE TABLE IF NOT EXISTS health_data (
        chat_id INTEGER,
        steps INTEGER,
        calories INTEGER,
        sleep INTEGER,
        FOREIGN KEY(chat_id) REFERENCES users(chat_id)
    )
''')

conn.commit()
conn.close()
