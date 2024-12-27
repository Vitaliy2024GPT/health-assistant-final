import os
import sys
import logging
import json
from flask import Flask, request, jsonify
from telegram import Update
from telegram.ext import Updater, CommandHandler, Dispatcher, CallbackContext
from database import (
    init_db, close_connection, add_user, get_user_by_chat_id,
    add_meal, get_user_meals, get_meals_last_7_days, get_calories_last_7_days
)
from datetime import datetime
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

# === TELEGRAM КОМАНДЫ ===
def start(update: Update, context: CallbackContext):
    update.message.reply_text(
        "Welcome to Health Assistant Bot!\n"
        "Use /register <name> to create an account.\n"
        "/addmeal <food> <calories> to log meals.\n"
        "/meals to view your meals.\n"
        "/report to see weekly calories stats.\n"
        "/diet_advice for a diet tip.\n"
        "/googleauth to authorize Google Fit.\n"
        "/googlefit to get data from Google Fit API."
    )

def help_command(update: Update, context: CallbackContext):
    update.message.reply_text(
        "Available commands:\n"
        "/start - Introduction\n"
        "/register <name> - Register\n"
        "/addmeal <food> <calories> - Add a meal\n"
        "/meals - View meals\n"
        "/report - Weekly report\n"
        "/diet_advice - Diet tip\n"
        "/googleauth - Google Fit authorization\n"
        "/googlefit - Google Fit data"
    )

def diet_advice(update: Update, context: CallbackContext):
    update.message.reply_text("Drink water before meals to reduce hunger and improve digestion.")

def register(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    if len(context.args) < 1:
        update.message.reply_text("Usage: /register <name>")
        return

    if get_user_by_chat_id(chat_id):
        update.message.reply_text("You are already registered.")
        return

    name = " ".join(context.args)
    add_user(chat_id, name)
    update.message.reply_text(f"User {name} registered successfully!")

def addmeal(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    if len(context.args) < 2:
        update.message.reply_text("Usage: /addmeal <food> <calories>")
        return

    try:
        food = context.args[0]
        calories = int(context.args[1])
    except ValueError:
        update.message.reply_text("Please provide valid numeric value for calories.")
        return

    add_meal(chat_id, food, calories)
    update.message.reply_text(f"Meal '{food}' with {calories} calories added!")

def meals(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    meals = get_user_meals(chat_id)
    if not meals:
        update.message.reply_text("No meals logged.")
        return

    response = "\n".join([f"{meal['food']}: {meal['calories']} kcal" for meal in meals])
    update.message.reply_text(response)

def report(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    stats = get_calories_last_7_days(chat_id)
    if not stats:
        update.message.reply_text("No data for the last 7 days.")
        return

    response = "\n".join(f"{day}: {calories} kcal" for day, calories in stats.items())
    update.message.reply_text(response)

def googleauth(update: Update, context: CallbackContext):
    auth_link = os.getenv("GOOGLE_AUTH_REDIRECT")
    if not auth_link:
        update.message.reply_text("Authorization link is not configured. Please contact support.")
        return
    
    update.message.reply_text(
        f"Please authorize the bot to access your Google Fit account:\n[Authorize Here]({auth_link})",
        parse_mode="Markdown"
    )

def googlefit(update: Update, context: CallbackContext):
    service = google_fit_service()
    if not service:
        update.message.reply_text(
            "Failed to connect to Google Fit. Please authorize first by using /googleauth"
        )
        return

    update.message.reply_text("Successfully connected to Google Fit API!")

# === ВЕБХУК ДЛЯ TELEGRAM ===
@app.route('/telegram_webhook', methods=['POST'])
def telegram_webhook():
    update = Update.de_json(request.get_json(), updater.bot)
    dispatcher.process_update(update)
    return 'OK', 200

# === ОБРАБОТЧИКИ КОМАНД ===
dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(CommandHandler("help", help_command))
dispatcher.add_handler(CommandHandler("diet_advice", diet_advice))
dispatcher.add_handler(CommandHandler("register", register))
dispatcher.add_handler(CommandHandler("addmeal", addmeal))
dispatcher.add_handler(CommandHandler("meals", meals))
dispatcher.add_handler(CommandHandler("report", report))
dispatcher.add_handler(CommandHandler("googleauth", googleauth))
dispatcher.add_handler(CommandHandler("googlefit", googlefit))

# === ЗАПУСК ПРИЛОЖЕНИЯ ===
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
