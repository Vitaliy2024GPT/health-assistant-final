import os
import sys
import logging
from flask import Flask, request, jsonify, redirect, session, url_for
from telegram import Update
from telegram.ext import Updater, CommandHandler
from database import (
    init_db, close_connection, get_user_by_chat_id
)
import requests
from datetime import datetime, timedelta
import urllib.parse

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Переменные окружения
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
REDIRECT_URI = "https://health-assistant-final.onrender.com/oauth2callback"

if not TELEGRAM_TOKEN or not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
    logger.error("Missing environment variables!")
    sys.exit(1)

# Инициализация базы данных
with app.app_context():
    init_db()
app.teardown_appcontext(close_connection)

# Инициализация Telegram бота
updater = Updater(token=TELEGRAM_TOKEN, use_context=True)
dispatcher = updater.dispatcher

# Получение данных из Google Fit
def get_google_fit_data(access_token):
    try:
        headers = {"Authorization": f"Bearer {access_token}"}
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(days=1)
        start_time_ns = int(start_time.timestamp()) * 1000000000
        end_time_ns = int(end_time.timestamp()) * 1000000000

        url = "https://www.googleapis.com/fitness/v1/users/me/dataset:aggregate"
        payload = {
            "aggregateBy": [{"dataTypeName": "com.google.calories.expended"}],
            "bucketByTime": {"durationMillis": 86400000},
            "startTimeMillis": start_time_ns // 1000000,
            "endTimeMillis": end_time_ns // 1000000
        }
        response = requests.post(url, json=payload, headers=headers)
        if response.ok:
            data = response.json()
            calories = sum(value.get('fpVal', 0)
                           for bucket in data.get('bucket', [])
                           for dataset in bucket.get('dataset', [])
                           for point in dataset.get('point', [])
                           for value in point.get('value', []))
            return round(calories, 2)
        else:
            logger.error(f"Error fetching Google Fit data: {response.text}")
            return None
    except Exception as e:
        logger.error(f"Exception: {e}")
        return None

# Telegram команды
def start(update, context):
    update.message.reply_text("Welcome to Health Assistant Bot!\nUse /google_fit to connect Google Fit.")

def fit_data_command(update, context):
    access_token = session.get("access_token")
    if not access_token:
        update.message.reply_text("Google Fit is not connected. Use /google_fit to connect.")
        return
    calories = get_google_fit_data(access_token)
    if calories is not None:
        update.message.reply_text(f"Calories burned in the last 24 hours: {calories} kcal.")
    else:
        update.message.reply_text("Failed to fetch data. Try again later.")

def google_fit_command(update, context):
    update.message.reply_text(f"Connect Google Fit here: {url_for('authorize', _external=True)}")

# Google OAuth маршруты
@app.route("/")
def home():
    return "Health Assistant API is running! Use /start in Telegram Bot to interact.", 200

@app.route("/authorize")
def authorize():
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": "https://www.googleapis.com/auth/fitness.activity.read",
        "access_type": "offline"
    }
    return redirect(f"https://accounts.google.com/o/oauth2/v2/auth?{urllib.parse.urlencode(params)}")

@app.route("/oauth2callback")
def oauth2callback():
    code = request.args.get("code")
    payload = {
        "code": code,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code"
    }
    response = requests.post("https://oauth2.googleapis.com/token", data=payload)
    if response.ok:
        session["access_token"] = response.json().get("access_token")
        return "Google Fit connected successfully!"
    return "Error during authorization."

@app.route("/telegram_webhook", methods=["POST"])
def telegram_webhook():
    try:
        data = request.get_json()
        update = Update.de_json(data, updater.bot)
        dispatcher.process_update(update)
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        logger.error(f"Error: {e}")
        return jsonify({"error": "failed"}), 500

# Добавление команд
dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(CommandHandler("google_fit", google_fit_command))
dispatcher.add_handler(CommandHandler("fit_data", fit_data_command))

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
