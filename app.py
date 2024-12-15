import os
import logging
import sys
from flask import Flask, request, jsonify
from telegram import Update
from telegram.ext import Updater, CommandHandler

# ====== Настройка логирования ======
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ====== Flask-приложение ======
app = Flask(__name__)

@app.route("/")
def home():
    return "Welcome to the Health Assistant Bot API!"

@app.route("/status")
def status():
    return "Flask server is running!"

# ====== Telegram токен ======
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

if not TELEGRAM_TOKEN:
    logger.error("TELEGRAM_TOKEN не задан в переменных окружения!")
    sys.exit(1)

# ====== Инициализация бота (python-telegram-bot v13.x) ======
updater = Updater(token=TELEGRAM_TOKEN, use_context=True)
dispatcher = updater.dispatcher

# ====== Обработчик команды /start ======
def start(update, context):
    """Ответ на команду /start"""
    update.message.reply_text("Welcome to Health Assistant Bot!")

dispatcher.add_handler(CommandHandler("start", start))

# ====== Обработчик Telegram webhook ======
@app.route("/telegram_webhook", methods=["POST"])
def telegram_webhook():
    try:
        data = request.get_json(force=True)
        logger.info(f"Webhook received data: {data}")
        update = Update.de_json(data, updater.bot)
        dispatcher.process_update(update)
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        logger.error(f"Error handling webhook: {e}")
        return jsonify({"error": "Failed to process webhook"}), 500

if __name__ == "__main__":
    # На Render порт задаётся переменной окружения PORT
    port = int(os.environ.get("PORT", 5000))
    logger.info("Starting Flask application...")
    app.run(host="0.0.0.0", port=port)
