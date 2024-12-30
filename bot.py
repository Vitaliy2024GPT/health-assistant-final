import os
from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext
import requests

# Токен Telegram-бота
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GOOGLE_API_URL = "https://www.googleapis.com/oauth2/v1/userinfo"

def start(update: Update, context: CallbackContext):
    update.message.reply_text("Добро пожаловать в Health Assistant 360! 🚀")

def profile(update: Update, context: CallbackContext):
    # Проверка сохранённого токена в сессии
    google_token = os.getenv("GOOGLE_OAUTH_TOKEN")
    if not google_token:
        update.message.reply_text(
            "Пожалуйста, пройдите авторизацию через Google для просмотра профиля: "
            "https://health-assistant-final.onrender.com/google_auth"
        )
        return

    # Запрос данных профиля
    headers = {"Authorization": f"Bearer {google_token}"}
    response = requests.get(GOOGLE_API_URL, headers=headers)
    
    if response.status_code == 200:
        user_data = response.json()
        update.message.reply_text(
            f"👤 Профиль пользователя:\n"
            f"Имя: {user_data.get('name')}\n"
            f"Email: {user_data.get('email')}\n"
            f"Фото: {user_data.get('picture')}"
        )
    else:
        update.message.reply_text("Ошибка при получении профиля. Пожалуйста, авторизуйтесь заново.")

def main():
    updater = Updater(TELEGRAM_TOKEN)
    dispatcher = updater.dispatcher

    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("profile", profile))

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
