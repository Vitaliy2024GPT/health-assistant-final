from flask import Flask, request, render_template
from flask_sqlalchemy import SQLAlchemy
import os
import logging
import asyncio
from telegram import Bot, Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes,  Defaults, CallbackContext
from telegram.error import TelegramError


app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL') or 'sqlite:///site.db'  # Получаем URL из переменных окружения или используем SQLite по умолчанию
db = SQLAlchemy(app)

# Настройка логирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Получаем токен бота из переменных окружения
bot_token = os.environ.get('TELEGRAM_TOKEN')

# Инициализируем бота и диспетчера
bot = Bot(bot_token)
application = ApplicationBuilder().token(bot_token).defaults(Defaults(parse_mode="HTML", allow_sending_without_reply=True)).build()

async def initialize_bot():
    await application.initialize()
    application.add_handler(CommandHandler("start", start))
    application.add_error_handler(error_handler)

asyncio.run(initialize_bot())



class User(db.Model):  # Пример модели
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    telegram_id = db.Column(db.Integer, unique=True, nullable=True)

# ... другие ваши модели ...

with app.app_context():  # Создаем контекст приложения Flask
    db.create_all()      # Создаем таблицы в базе данных


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    await update.message.reply_text('Привет! Я медицинский ассистент.')



async def error_handler(update: Update, context: CallbackContext) -> None:
    """Log the error and send a telegram message to notify the developer."""
    # Log the error before we have a chance to try to access context.chat_data
    logger.error(f"Exception while handling an update: {context.error}")
    try:
      pass
    except Exception as e:
       logger.error(f"Exception in error handler {e}")



@app.route('/')
def index():
    return render_template('index.html')

async def process_update(update:Update):
    await application.process_update(update)

@app.route('/telegram_webhook', methods=['POST'])
def telegram_webhook():
    """Обработчик для приема обновлений от Telegram"""
    try:
        update = Update.de_json(request.get_json(force=True), bot)
        asyncio.run(process_update(update))
    except Exception as e:
        logger.error(f"Ошибка при обработке вебхука: {e}")
    return 'ok', 200

if __name__ == '__main__':
   app.run(debug=True)
