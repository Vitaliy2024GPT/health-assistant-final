import os
from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext

def start(update: Update, context: CallbackContext):
    """Обработчик команды /start"""
    update.message.reply_text('Привет! Я медицинский ассистент.')

def main():
    """Запускает бота."""
    # Получаем токен бота из переменной окружения (необходимо создать переменную BOT_TOKEN)
    bot_token = os.environ.get('BOT_TOKEN')

    if not bot_token:
        print("Ошибка: Не установлен BOT_TOKEN в переменных окружения.")
        return

    updater = Updater(bot_token)
    dispatcher = updater.dispatcher

    # Добавляем обработчик команды /start
    dispatcher.add_handler(CommandHandler("start", start))

    # Запускаем бота
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
