import os
import logging
from flask import Flask, request, jsonify
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)
import asyncio

# ====== Настройка логирования ======
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ====== Flask-приложение ======
app = Flask(__name__)

# Главная страница
@app.route("/")
def home():
    return "Welcome to the Health Assistant Bot API!"

# Проверка статуса сервера
@app.route("/status")
def status():
    return "Flask server is running!"

# ====== Telegram токен ======
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_TOKEN не задан в переменных окружения!")

# ====== Глобальная переменная для Telegram бота ======
bot_app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

# ====== Обработчики команд ======
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ответ на команду /start"""
    await update.message.reply_text("Welcome to Health Assistant Bot!")

# Добавляем обработчик команды /start
bot_app.add_handler(CommandHandler("start", start))

# ====== Обработчик Telegram webhook ======
@app.route("/telegram_webhook", methods=["POST"])
def telegram_webhook():
    global bot_app
    try:
        # Получаем данные от Telegram
        data = request.get_json()
        logger.info(f"Webhook received data: {data}")

        # Обрабатываем обновление в существующем цикле событий
        update = Update.de_json(data, bot_app.bot)
        loop = asyncio.get_event_loop()
        loop.create_task(bot_app.process_update(update))

        return jsonify({"status": "ok"}), 200
    except Exception as e:
        logger.error(f"Error handling webhook: {e}")
        return jsonify({"error": "Failed to process webhook"}), 500

# ====== Точка входа ======
if __name__ == "__main__":
    # Запускаем Flask-сервер
    logger.info("Starting Flask application...")
    app.run(host="0.0.0.0", port=10000, debug=False)
