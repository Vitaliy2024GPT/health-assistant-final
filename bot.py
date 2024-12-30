import os
from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext

# Токен Telegram-бота
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

def start(update: Update, context: CallbackContext):
    update.message.reply_text("Добро пожаловать в Health Assistant 360! 🚀")

def profile(update: Update, context: CallbackContext):
    update.message.reply_text(
        "Пожалуйста, пройдите авторизацию через Google для просмотра профиля: "
        "https://health-assistant-final.onrender.com/google_auth"
    )

def main():
    updater = Updater(TELEGRAM_TOKEN)
    dispatcher = updater.dispatcher

    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("profile", profile))

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
