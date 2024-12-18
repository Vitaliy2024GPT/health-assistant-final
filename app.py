import os
import sys
import logging
from flask import Flask, request, jsonify
from telegram import Update
from telegram.ext import Updater, CommandHandler
from database import (
    init_db, close_connection, add_user, get_user_by_chat_id,
    add_meal, get_user_meals, get_meals_last_7_days, get_calories_last_7_days
)
from datetime import date
import redis
from google.oauth2 import service_account
from googleapiclient.discovery import build

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Инициализация базы данных при старте приложения
with app.app_context():
    init_db()

app.teardown_appcontext(close_connection)

# Подключение к Redis
redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
redis_client = redis.StrictRedis.from_url(redis_url, decode_responses=True)

# Telegram токен из переменных окружения
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

if not TELEGRAM_TOKEN:
    logger.error("TELEGRAM_TOKEN not set")
    sys.exit(1)

# Инициализация Telegram бота
updater = Updater(token=TELEGRAM_TOKEN, use_context=True)
dispatcher = updater.dispatcher

# Подключение к Google Fit API
def google_fit_service():
    credentials_path = "credentials.json"  # Файл с ключами
    try:
        credentials = service_account.Credentials.from_service_account_file(
            credentials_path, scopes=["https://www.googleapis.com/auth/fitness.activity.read"]
        )
        service = build("fitness", "v1", credentials=credentials)
        return service
    except Exception as e:
        logger.error(f"Failed to connect to Google Fit API: {e}")
        return None

# Функции работы с Redis
def save_temp_data(key, value, ttl=3600):
    redis_client.set(key, value, ex=ttl)

def get_temp_data(key):
    return redis_client.get(key)

# Telegram команды
def start(update, context):
    update.message.reply_text(
        "Welcome to Health Assistant Bot!\n"
        "Use /register <name> to create an account.\n"
        "Then /addmeal <food> <calories> to log meals.\n"
        "Use /meals to see all meals.\n"
        "/report to see weekly calories stats.\n"
        "/diet_advice for a simple diet tip!\n"
        "/googlefit to get data from Google Fit API."
    )

def register_command(update, context):
    if len(context.args) < 1:
        update.message.reply_text("Usage: /register <name>")
        return
    name = context.args[0]
    chat_id = update.message.chat_id

    user = get_user_by_chat_id(chat_id)
    if user:
        update.message.reply_text(f"You are already registered as {user['name']}.")
    else:
        user_id = add_user(name, chat_id)
        update.message.reply_text(f"User registered! ID: {user_id} for this chat.")

def addmeal_command(update, context):
    if len(context.args) < 2:
        update.message.reply_text("Usage: /addmeal food_name calories")
        return

    chat_id = update.message.chat_id
    user = get_user_by_chat_id(chat_id)
    if not user:
        update.message.reply_text("You are not registered. Use /register <name> first.")
        return

    food_name = context.args[0]
    try:
        calories = int(context.args[1])
    except ValueError:
        update.message.reply_text("Calories must be a number.")
        return

    today_str = date.today().isoformat()
    add_meal(user["id"], food_name, calories, today_str)
    update.message.reply_text(f"Meal added: {food_name}, {calories} kcal")

def googlefit_command(update, context):
    chat_id = update.message.chat_id
    service = google_fit_service()
    if not service:
        update.message.reply_text("Failed to connect to Google Fit API. Try again later.")
        return

    try:
        # Пример запроса данных Google Fit
        response = service.users().dataset().aggregate(
            userId="me", body={
                "aggregateBy": [{"dataTypeName": "com.google.step_count.delta"}],
                "bucketByTime": {"durationMillis": 86400000},
                "startTimeMillis": 0,  # Настройте диапазон
                "endTimeMillis": int(date.today().strftime("%s")) * 1000
            }
        ).execute()

        steps = response.get("bucket", [])[0]["dataset"][0]["point"][0]["value"][0]["intVal"]
        update.message.reply_text(f"Your total steps for today: {steps}")
    except Exception as e:
        logger.error(f"Error fetching Google Fit data: {e}")
        update.message.reply_text("Could not retrieve Google Fit data.")

# Добавляем обработчики команд
dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(CommandHandler("register", register_command))
dispatcher.add_handler(CommandHandler("addmeal", addmeal_command))
dispatcher.add_handler(CommandHandler("googlefit", googlefit_command))

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
    port = int(os.environ.get("PORT", 5000))
    logger.info("Starting Flask application...")
    app.run(host="0.0.0.0", port=port)
