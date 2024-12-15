import logging
from flask import Flask, request, jsonify
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Flask-приложение
app = Flask(__name__)

# Главная страница
@app.route("/")
def home():
    return "Welcome to the Health Assistant Bot API!"

@app.route("/status")
def status():
    return "Flask server is running!"

# Telegram webhook
@app.route("/telegram_webhook", methods=["POST"])
def telegram_webhook():
    try:
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

# Telegram токен
TELEGRAM_TOKEN = "ваш_токен"

# Обработчик команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Welcome to Health Assistant Bot!")

# Функция запуска Telegram-бота
def start_bot():
    global bot_app
    bot_app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    bot_app.add_handler(CommandHandler("start", start))
    logger.info("Telegram Bot started")

if __name__ == "__main__":
    # Запуск Telegram бота
    start_bot()

    # Запуск Flask-сервера
    logger.info("Starting Flask application...")
    app.run(host="0.0.0.0", port=10000, debug=False)
