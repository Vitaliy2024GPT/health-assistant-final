import os
import sys
import logging
from flask import Flask, request, jsonify, redirect, session, url_for
from telegram import Update
from telegram.ext import Updater, CommandHandler
from database import (
    init_db, close_connection, add_user, get_user_by_chat_id,
    add_meal, get_user_meals, get_meals_last_7_days, get_calories_last_7_days
)
from datetime import date
import requests
import urllib.parse

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Инициализация базы данных
with app.app_context():
    init_db()
app.teardown_appcontext(close_connection)

# Переменные окружения
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
REDIRECT_URI = "https://health-assistant-final.onrender.com/oauth2callback"

if not TELEGRAM_TOKEN or not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
    logger.error("Required environment variables are missing!")
    sys.exit(1)

# Инициализация Telegram бота
updater = Updater(token=TELEGRAM_TOKEN, use_context=True)
dispatcher = updater.dispatcher

# --- Telegram Команды ---
def start(update, context):
    update.message.reply_text(
        "Welcome to Health Assistant Bot!\n"
        "Use /register <name> to create an account.\n"
        "Then /addmeal <food> <calories> to log meals.\n"
        "Use /meals to see all meals.\n"
        "/report to see weekly calories stats.\n"
        "/diet_advice for a simple diet tip!\n"
        "/google_fit to connect Google Fit account."
    )

def register_command(update, context):
    if len(context.args) < 1:
        update.message.reply_text("Usage: /register <name>")
        return
    name, chat_id = context.args[0], update.message.chat_id

    user = get_user_by_chat_id(chat_id)
    if user:
        update.message.reply_text(f"You are already registered as {user['name']}.")
    else:
        user_id = add_user(name, chat_id)
        update.message.reply_text(f"Registered successfully! ID: {user_id}")

def addmeal_command(update, context):
    try:
        food_name, calories = context.args[0], int(context.args[1])
        today_str = date.today().isoformat()
        user = get_user_by_chat_id(update.message.chat_id)
        if not user:
            raise ValueError("You are not registered.")
        add_meal(user["id"], food_name, calories, today_str)
        update.message.reply_text(f"Meal logged: {food_name}, {calories} kcal.")
    except (IndexError, ValueError):
        update.message.reply_text("Usage: /addmeal <food_name> <calories>")

def google_fit_command(update, context):
    update.message.reply_text(f"Connect your Google Fit account here: {url_for('authorize', _external=True)}")

# Google Fit OAuth маршруты
@app.route("/authorize")
def authorize():
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": "https://www.googleapis.com/auth/fitness.activity.read",
        "access_type": "offline",
        "prompt": "consent"
    }
    return redirect(f"https://accounts.google.com/o/oauth2/v2/auth?{urllib.parse.urlencode(params)}")

@app.route("/oauth2callback")
def oauth2callback():
    code = request.args.get("code")
    payload = {
        "code": code, "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI, "grant_type": "authorization_code"
    }
    response = requests.post("https://oauth2.googleapis.com/token", data=payload)
    if response.ok:
        session["access_token"] = response.json().get("access_token")
        return "Google Fit connected successfully!"
    return "Error during authorization."

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

# Добавление команд
dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(CommandHandler("register", register_command))
dispatcher.add_handler(CommandHandler("addmeal", addmeal_command))
dispatcher.add_handler(CommandHandler("google_fit", google_fit_command))

# Запуск сервера
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
