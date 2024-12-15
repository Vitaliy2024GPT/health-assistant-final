import os
import logging
import threading
from flask import Flask, request, jsonify
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)

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

# ====== Глобальная переменная для Telegram бота ======
bot_app = None

# Обработчик для Telegram webhook
@app.route("/telegram_webhook", methods=["POST"])
def telegram_webhook():
    global bot_app
    try:
        if not bot_app:
            raise ValueError("Bot is not initialized!")

        # Получаем данные от Telegram
        data = request.get_json()
        logger.info(f"Webhook received data: {data}")

        # Обрабатываем обновление через Telegram Bot API
        update = Update.de_json(data, bot_app.bot)
        bot_app.process_update(update)

        return jsonify({"status": "ok"}), 200
    except Exception as e:
        logger.error(f"Error handling webhook: {e}")
        return jsonify({"error": "Failed to process webhook"}), 500

# ====== Telegram токен ======
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_TOKEN не задан в переменных окружения!")

# ====== Обработчики команд ======
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ответ на команду /start"""
    await update.message.reply_text("Welcome to Health Assistant Bot!")

# ====== Запуск Telegram-бота ======
def start_bot():
    global bot_app
    if bot_app:
        logger.info("Telegram Bot already running.")
        return

    bot_app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # Добавляем обработчик команды /start
    bot_app.add_handler(CommandHandler("start", start))

    # Логируем успешный запуск бота
    logger.info("Telegram Bot started successfully")

    # Запуск бота в фоновом потоке
    threading.Thread(target=bot_app.run_polling, daemon=True).start()
    logger.info("Telegram Bot is running in a separate thread.")

# ====== Точка входа ======
if __name__ == "__main__":
    try:
        # Запускаем Telegram бота
        start_bot()

        # Запускаем Flask-сервер
        logger.info("Starting Flask application...")
        app.run(host="0.0.0.0", port=10000, debug=False)
    except Exception as e:
        logger.error(f"An error occurred: {e}")
