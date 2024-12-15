import logging
from flask import Flask
from threading import Thread
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

@app.route("/")
def home():
    return "Welcome to the Health Assistant Bot API!"

@app.route("/status")
def status():
    return "Flask server is running!"

# Telegram токен
TELEGRAM_TOKEN = "ваш_токен"

# Обработчик команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Welcome to Health Assistant Bot! Use /dashboard <user_id> to view your stats."
    )

# Обработчик команды /dashboard
async def dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        args = context.args
        if len(args) != 1:
            await update.message.reply_text(
                "Please provide your user_id. Example: /dashboard 1"
            )
            return

        user_id = args[0]
        dashboard_url = f"https://health-assistant-final.onrender.com/dashboard?user_id={user_id}"
        
        # Отправляем ссылку на дашборд
        await update.message.reply_text(f"Your dashboard is available at: {dashboard_url}")
    except Exception as e:
        logger.error(f"Error in /dashboard command: {e}")
        await update.message.reply_text(
            "An error occurred while processing your request. Please try again later."
        )

# Функция запуска Telegram-бота
def start_bot():
    try:
        # Создаем приложение Telegram Bot
        bot_app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

        # Добавляем обработчики команд
        bot_app.add_handler(CommandHandler("start", start))
        bot_app.add_handler(CommandHandler("dashboard", dashboard))

        # Запуск бота
        logger.info("Starting Telegram Bot...")
        bot_app.run_polling()
    except Exception as e:
        logger.error(f"Failed to start Telegram Bot: {e}")

# Основной блок
if __name__ == "__main__":
    # Запуск Telegram-бота в отдельном потоке
    Thread(target=start_bot).start()

    # Запуск Flask-приложения
    logger.info("Starting Flask application...")
    app.run(host="0.0.0.0", port=5000, debug=False)
