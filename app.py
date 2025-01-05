from quart import Quart, request, render_template
import os
import logging
import asyncio
from telegram import Bot, Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes,  Defaults, CallbackContext
from telegram.error import TelegramError


app = Quart(__name__)

# Настройка логирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Получаем токен бота из переменных окружения
bot_token = os.environ.get('TELEGRAM_TOKEN')

# Инициализируем бота и диспетчера
bot = Bot(bot_token)
application = ApplicationBuilder().token(bot_token).defaults(Defaults(parse_mode="HTML", allow_sending_without_reply=True)).build()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    await update.message.reply_text('Привет! Я медицинский ассистент.')

async def error_handler(update: Update, context: CallbackContext) -> None:
    """Log the error and send a telegram message to notify the developer."""
    # Log the error before we have a chance to try to access context.chat_data
    logger.error(f"Exception while handling an update: {context.error}")
    try:
      pass
    except Exception as e:
       logger.error(f"Exception in error handler {e}")

@app.before_serving
async def initialize_bot():
    application.add_handler(CommandHandler("start", start))
    application.add_error_handler(error_handler)
    await application.initialize()

@app.route('/')
async def index():
    return await render_template('index.html')

@app.route('/telegram_webhook', methods=['POST'])
async def telegram_webhook():
    """Обработчик для приема обновлений от Telegram"""
    try:
        update = Update.de_json(await request.get_data(as_text=True), bot)
        await application.process_update(update)
    except Exception as e:
        logger.error(f"Ошибка при обработке вебхука: {e}")
    return 'ok', 200

if __name__ == '__main__':
   app.run(debug=True)
