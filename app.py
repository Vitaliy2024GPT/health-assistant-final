import logging
import os
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Ваш Telegram токен
TELEGRAM_TOKEN = "7806534407:AAFfqucrckKwfGdNlWCZyLzUwoR7SxIuJOY"

# Убедимся, что токен установлен
if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_TOKEN not set")

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Welcome to Health Assistant Bot! Use /dashboard <user_id> to view your stats.")

# Команда /dashboard
async def dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        args = context.args
        if len(args) != 1:
            await update.message.reply_text("Please provide your user_id. Example: /dashboard 1")
            return

        user_id = args[0]
        dashboard_url = f"https://health-assistant-final.onrender.com/dashboard?user_id={user_id}"
        
        # Отправляем пользователю ссылку на дашборд
        await update.message.reply_text(f"Your dashboard is available at: {dashboard_url}")
    except Exception as e:
        logger.error(f"Error in /dashboard command: {e}")
        await update.message.reply_text("An error occurred while processing your request. Please try again later.")

# Основная функция
def main():
    # Создаем приложение Telegram Bot
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # Добавляем обработчики команд
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("dashboard", dashboard))

    # Запуск бота
    app.run_polling()

if __name__ == "__main__":
    main()
