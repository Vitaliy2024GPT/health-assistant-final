import os
import sys
import logging
import json
from flask import Flask, request, jsonify
from telegram import Update
from telegram.ext import Updater, CommandHandler, Dispatcher, CallbackContext
from database import (
    init_db, close_connection, add_user, get_user_by_chat_id,
    get_calories_last_7_days
)
from google.oauth2 import service_account
from googleapiclient.discovery import build
from threading import Thread
from retrying import retry
import redis

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

def redis_safe_set(key, value, ttl=3600):
    """Обертка для безопасного сохранения данных в Redis."""
    try:
        redis_client.set(key, value, ex=ttl)
    except Exception as e:
        logger.error(f"Failed to save data in Redis: {e}")

def redis_safe_get(key):
    """Обертка для безопасного извлечения данных из Redis."""
    try:
        return redis_client.get(key)
    except Exception as e:
        logger.error(f"Failed to retrieve data from Redis: {e}")
        return None

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
    """Стартовая команда."""
    update.message.reply_text(
        "Welcome to Health Assistant Bot!\n"
        "Commands:\n"
        "/register <name> - Register your account\n"
        "/report - View your weekly calorie report\n"
        "/diet_advice - Receive diet advice\n"
        "/googlefit - Connect to Google Fit API"
    )

def register(update: Update, context: CallbackContext):
    """Регистрация пользователя."""
    chat_id = update.message.chat_id
    if len(context.args) < 1:
        update.message.reply_text("Usage: /register <name>")
        return
    if get_user_by_chat_id(chat_id):
        update.message.reply_text("You are already registered.")
        return
    name = " ".join(context.args)
    if len(name) > 50:
        update.message.reply_text("Name is too long. Use a shorter name.")
        return
    add_user(chat_id, name)
    update.message.reply_text(f"User {name} registered successfully!")

def report(update: Update, context: CallbackContext):
    """Отчет по потреблению калорий за неделю."""
    chat_id = update.message.chat_id
    user = get_user_by_chat_id(chat_id)
    if not user:
        update.message.reply_text("You are not registered. Use /register <name>.")
        return
    stats = get_calories_last_7_days(user["id"])
    if not stats:
        update.message.reply_text("No data available for the last 7 days.")
        return
    report_text = "\n".join(f"{day}: {calories} kcal" for day, calories in stats.items())
    update.message.reply_text(f"Weekly calorie report:\n{report_text}")

def diet_advice(update: Update, context: CallbackContext):
    """Совет по диете."""
    advice = "Drink water before meals to reduce hunger and improve digestion."
    update.message.reply_text(advice)

def google_auth(update: Update, context: CallbackContext):
    """Ссылка для авторизации Google Fit."""
    auth_link = os.getenv("GOOGLE_AUTH_REDIRECT", "https://your-default-url.com")
    update.message.reply_text(
        f"Please authorize access to Google Fit: [Authorize Here]({auth_link})",
        parse_mode="Markdown"
    )

# === ОБРАБОТКА ВЕБХУКА ===
@app.route("/telegram_webhook", methods=["POST"])
def telegram_webhook():
    """Обработка обновлений Telegram через вебхук."""
    try:
        logger.info("Received webhook update")
        data = request.get_json(force=True)
        if not data:
            logger.error("Invalid JSON received")
            return jsonify({"error": "Invalid JSON"}), 400
        update = Update.de_json(data, updater.bot)
        dispatcher.process_update(update)
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/", methods=["GET"])
def health_check():
    """Проверка состояния сервиса."""
    return "Bot is running", 200

# === РЕГИСТРАЦИЯ ОБРАБОТЧИКОВ КОМАНД ===
dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(CommandHandler("register", register))
dispatcher.add_handler(CommandHandler("report", report))
dispatcher.add_handler(CommandHandler("diet_advice", diet_advice))
dispatcher.add_handler(CommandHandler("googleauth", google_auth))

# === ЗАПУСК ===
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    logger.info(f"Starting Flask app on port {port}")
    Thread(target=lambda: app.run(host="0.0.0.0", port=port)).start()
    webhook_url = f"https://{os.getenv('RENDER_EXTERNAL_HOSTNAME')}/telegram_webhook"
    updater.start_webhook(listen="0.0.0.0", port=port, url_path="/telegram_webhook")
    updater.bot.set_webhook(url=webhook_url)
    updater.idle()
