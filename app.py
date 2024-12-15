import logging
import os
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Получение токена из переменных окружения
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

# Проверка на наличие токена
if not TELEGRAM_TOKEN:
    raise ValueError("Telegram token not found. Set the TELEGRAM_TOKEN environment variable.")

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"User {update.effective_user.username} used /start")
    await update.message.reply_text(
        "Welcome to Health Assistant Bot! 🎉\n\n"
        "Commands available:\n"
        "/dashboard <user_id> - View your health stats.\n"
        "Example: /dashboard 1"
    )

# Команда /dashboard
async def dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        # Получаем аргументы команды
        args = context.args
        if len(args) != 1 or not args[0].isdigit():
            await update.message.reply_text("⚠️ Please provide a valid user_id (a number).\nExample: /dashboard 1")
            return

        user_id = args[0]
        dashboard_url = f"https://health-assistant-final.onrender.com/dashboard?user_id={user_id}"
        
        # Запрос к API
        logger.info(f"Fetching dashboard for user_id {user_id}")
        response = requests.get(dashboard_url)

        if response.status_code == 200:
            await update.message.reply_text(
                f"✅ Your dashboard is ready!\n\nClick the link below:\n{dashboard_url}"
            )
        elif response.status_code == 204:
            await update.message.reply_text("⚠️ No data available for this user_id.")
        else:
            await update.message.reply_text(
                "❌ Something went wrong while retrieving your dashboard. Please try again later."
            )
            logger.error(f"Error {response.status_code}: {response.text}")

    except Exception as e:
        logger.error(f"Error in /dashboard command: {e}")
        await update.message.reply_text("❌ An unexpected error occurred. Please try again later.")

# Основная функция
def main():
    logger.info("Starting Health Assistant Bot...")
    
    # Создаем приложение Telegram Bot
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # Добавляем обработчики команд
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("dashboard", dashboard))

    # Запуск бота
    logger.info("Bot is running and polling for updates.")
    app.run_polling()

if __name__ == "__main__":
    main()
