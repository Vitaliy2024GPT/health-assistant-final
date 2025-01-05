from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import os

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL') or 'sqlite:///site.db'  # Получаем URL из переменных окружения или используем SQLite по умолчанию
db = SQLAlchemy(app)

class User(db.Model):  # Пример модели
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)

# ... другие ваши модели ...

with app.app_context():  # Создаем контекст приложения Flask
    db.create_all()      # Создаем таблицы в базе данных
