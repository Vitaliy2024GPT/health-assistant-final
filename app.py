import os
import sys
import logging
import tempfile
from flask import Flask, request, jsonify
from telegram import Update
from telegram.ext import Updater, CommandHandler, Dispatcher
from database import (
    init_db, close_connection, add_user, get_user_by_chat_id,
    add_meal, get_user_meals, get_meals_last_7_days, get_calories_last_7_days
)
from datetime import date, datetime
import redis
from google.oauth2 import service_account
from googleapiclient.discovery import build
from threading import Thread

# === ЛОГИРОВАНИЕ ===
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# === ИНИЦИАЛИЗАЦИЯ FLASK ===
app = Flask(__name__)

# === ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ ===
with app.app_context():
    init_db()
app.teardown_appcontext(close_connection)

# === ПОДКЛЮЧЕНИЕ К REDIS ===
redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
redis_client = redis.StrictRedis.from_url(redis_url, decode_responses=True)

# === ПОДКЛЮЧЕНИЕ К TELEGRAM ===
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
if not TELEGRAM_TOKEN:
    logger.error("TELEGRAM_TOKEN is not set")
    sys.exit(1)

updater = Updater(token=TELEGRAM_TOKEN, use_context=True)
dispatcher: Dispatcher = updater.dispatcher

# === GOOGLE FIT API ===
def google_fit_service():
    try:
        credentials_content = os.getenv("GOOGLE_CREDENTIALS")
        if not credentials_content:
            raise ValueError("GOOGLE_CREDENTIALS is not set in environment variables")
        
        with tempfile.NamedTemporaryFile(mode="w+", delete=False) as temp_file:
            temp_file.write(credentials_content)
            temp_file_path = temp_file.name

        credentials = service_account.Credentials.from_service_account_file(
            temp_file_path, scopes=["https://www.googleapis.com/auth/fitness.activity.read"]
        )
        os.remove(temp_file_path)
        return build("fitness", "v1", credentials=credentials)
    except Exception as e:
        logger.error(f"Failed to connect to Google Fit API: {e}")
        return None

# === REDIS ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ===
def save_temp_data(key, value, ttl=3600):
    redis_client.set(key, value, ex=ttl)

def get_temp_data(key):
    return redis_client.get(key)

# === TELEGRAM КОМАНДЫ ===
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

def help_command(update, context):
    update.message.reply_text(
        "Available commands:\n"
        "/start - Introduction to the bot\n"
        "/register <name> - Register your account\n"
        "/addmeal <food> <calories> - Log a meal\n"
        "/meals - View all logged meals\n"
        "/report - Get weekly calorie report\n"
        "/diet_advice - Receive a diet tip\n"
        "/googlefit - Fetch step data from Google Fit"
    )

def diet_advice(update, context):
    advice = "Drink water before meals to reduce hunger and improve digestion."
    update.message.reply_text(advice)

def report_command(update, context):
    chat_id = update.message.chat_id
    user = get_user_by_chat_id(chat_id)
    if not user:
        update.message.reply_text("You are not registered. Use /register <name> first.")
        return

    stats = get_calories_last_7_days(user["id"])
    if not stats:
        update.message.reply_text("No data available for the last 7 days.")
        return

    try:
        response = "\n".join(f"{day}: {calories} kcal" for day, calories in stats.items())
        update.message.reply_text(f"Calories consumed in the last 7 days:\n{response}")
    except Exception as e:
        logger.error(f"Error generating report: {e}")
        update.message.reply_text("Error generating report.")

def googlefit_command(update, context):
    service = google_fit_service()
    if not service:
        update.message.reply_text("Failed to connect to Google Fit API. Try again later.")
        return

    try:
        now = datetime.utcnow()
        start_time = int(datetime(now.year, now.month, now.day).timestamp()) * 1000
        end_time = int(datetime.utcnow().timestamp()) * 1000

        response = service.users().dataset().aggregate(
            userId="me", body={
                "aggregateBy": [{"dataTypeName": "com.google.step_count.delta"}],
                "bucketByTime": {"durationMillis": 86400000},
                "startTimeMillis": start_time,
                "endTimeMillis": end_time
            }
        ).execute()

        buckets = response.get("bucket", [])
        steps = sum(
            point.get("value", [{}])[0].get("intVal", 0)
            for bucket in buckets for data in bucket.get("dataset", [])
            for point in data.get("point", [])
        )
        update.message.reply_text(f"Your total steps for today: {steps}")
    except Exception as e:
        logger.error(f"Error fetching Google Fit data: {e}")
        update.message.reply_text("Could not retrieve Google Fit data.")

# === ОБРАБОТЧИКИ КОМАНД ===
dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(CommandHandler("help", help_command))
dispatcher.add_handler(CommandHandler("diet_advice", diet_advice))
dispatcher.add_handler(CommandHandler("report", report_command))
dispatcher.add_handler(CommandHandler("googlefit", googlefit_command))

# === ВЕБХУК ДЛЯ TELEGRAM ===
@app.route("/telegram_webhook", methods=["POST"])
def telegram_webhook():
    try:
        data = request.get_json(force=True)
        update = Update.de_json(data, updater.bot)
        dispatcher.process_update(update)
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        logger.error(f"Error handling webhook: {e}")
        return jsonify({"error": "Failed to process webhook"}), 500

# === ЗАПУСК ПРИЛОЖЕНИЯ ===
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    logger.info(f"Starting Flask application on port {port}")
    Thread(target=lambda: app.run(host="0.0.0.0", port=port)).start()
    updater.start_polling()
    updater.idle()
