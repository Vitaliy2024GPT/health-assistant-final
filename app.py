import os
import sys
import logging
import tempfile
import io
import json
from flask import Flask, request, jsonify, redirect
from telegram import Update
from telegram.ext import Updater, CommandHandler, Dispatcher, CallbackContext
from database import (
    init_db, close_connection, add_user, get_user_by_chat_id,
    add_meal, get_user_meals, get_meals_last_7_days, get_calories_last_7_days
)
from datetime import date, datetime
import redis
from google.oauth2 import service_account
from googleapiclient.discovery import build
from threading import Thread
from retrying import retry

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
@retry(stop_max_attempt_number=3, wait_fixed=2000)
def connect_to_redis():
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    return redis.StrictRedis.from_url(redis_url, decode_responses=True)

try:
    redis_client = connect_to_redis()
except Exception as e:
    logger.error(f"Failed to connect to Redis: {e}")
    sys.exit(1)

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

        credentials = service_account.Credentials.from_service_account_info(
            json.loads(credentials_content), scopes=["https://www.googleapis.com/auth/fitness.activity.read"]
        )
        return build("fitness", "v1", credentials=credentials)
    except Exception as e:
        logger.error(f"Failed to connect to Google Fit API: {e}")
        return None

# === REDIS ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ===
def save_temp_data(key, value, ttl=3600):
    try:
        redis_client.set(key, value, ex=ttl)
    except Exception as e:
        logger.error(f"Failed to save data in Redis: {e}")

def get_temp_data(key):
    try:
        return redis_client.get(key)
    except Exception as e:
        logger.error(f"Failed to retrieve data from Redis: {e}")
        return None

# === TELEGRAM КОМАНДЫ ===
def start(update: Update, context: CallbackContext):
    update.message.reply_text(
        "Welcome to Health Assistant Bot!\n"
        "Use /register <name> to create an account.\n"
        "Then /addmeal <food> <calories> to log meals.\n"
        "Use /meals to see all meals.\n"
        "/report to see weekly calories stats.\n"
        "/diet_advice for a simple diet tip!\n"
        "/googlefit to get data from Google Fit API."
    )

def help_command(update: Update, context: CallbackContext):
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

def diet_advice(update: Update, context: CallbackContext):
    advice = "Drink water before meals to reduce hunger and improve digestion."
    update.message.reply_text(advice)

def register(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    if len(context.args) < 1:
        update.message.reply_text("Please provide a name. Usage: /register <name>")
        return

    if get_user_by_chat_id(chat_id):
        update.message.reply_text("You are already registered.")
        return

    name = " ".join(context.args)
    if len(name) > 50:
        update.message.reply_text("Name is too long. Please use a shorter name.")
        return

    add_user(chat_id, name)
    update.message.reply_text(f"User {name} registered successfully!")

def report_command(update: Update, context: CallbackContext):
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

def google_auth(update: Update, context: CallbackContext):
    auth_link = os.getenv("GOOGLE_AUTH_REDIRECT")
    if not auth_link:
        update.message.reply_text("Authorization link is not configured. Please contact support.")
        return
    update.message.reply_text(
        f"Please authorize the bot to access your Google Fit account: [Authorize Here]({auth_link})",
        parse_mode="Markdown"
    )

@app.route("/telegram_webhook", methods=["POST"])
def telegram_webhook():
    try:
        logger.info("Received webhook update")
        data = request.get_json(force=True)
        if not data:
            logger.error("Empty or invalid JSON received")
            return jsonify({"error": "Invalid JSON"}), 400
        update = Update.de_json(data, updater.bot)
        dispatcher.process_update(update)
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        logger.error(f"Error handling webhook: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/", methods=["GET"])
def health_check():
    return "Bot is running", 200

# === ОБРАБОТЧИКИ КОМАНД ===
dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(CommandHandler("help", help_command))
dispatcher.add_handler(CommandHandler("diet_advice", diet_advice))
dispatcher.add_handler(CommandHandler("register", register))
dispatcher.add_handler(CommandHandler("report", report_command))
dispatcher.add_handler(CommandHandler("googleauth", google_auth))

# === ЗАПУСК ПРИЛОЖЕНИЯ ===
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    logger.info(f"Starting Flask application on port {port}")
    Thread(target=lambda: app.run(host="0.0.0.0", port=port)).start()
    updater.start_webhook(listen='0.0.0.0', port=port, url_path='/telegram_webhook')
    updater.bot.set_webhook(url=f"https://{os.getenv('RENDER_EXTERNAL_HOSTNAME')}/telegram_webhook")
    updater.idle()
