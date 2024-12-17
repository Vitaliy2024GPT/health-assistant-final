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
from googleapiclient.discovery import build
from datetime import datetime, timedelta

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

# Инициализация бота
updater = Updater(token=TELEGRAM_TOKEN, use_context=True)
dispatcher = updater.dispatcher

# Получение данных из Google Fit
def get_google_fit_data(access_token):
    try:
        # Создаём сервис Google Fit API
        service = build('fitness', 'v1', credentials=None)
        headers = {"Authorization": f"Bearer {access_token}"}

        # Временной диапазон: последние 24 часа
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(days=1)
        start_time_ns = int(start_time.timestamp()) * 1000000000
        end_time_ns = int(end_time.timestamp()) * 1000000000

        # Запрос активных калорий
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
            calories = 0
            for bucket in data.get('bucket', []):
                for dataset in bucket.get('dataset', []):
                    for point in dataset.get('point', []):
                        for value in point.get('value', []):
                            calories += value.get('fpVal', 0)
            return round(calories, 2)
        else:
            logger.error(f"Error fetching Google Fit data: {response.text}")
            return None
    except Exception as e:
        logger.error(f"Exception: {e}")
        return None

# Обработчик команды /fit_data
def fit_data_command(update, context):
    chat_id = update.message.chat_id
    access_token = session.get("access_token")

    if not access_token:
        update.message.reply_text("Google Fit is not connected. Use /google_fit to connect.")
        return

    calories = get_google_fit_data(access_token)
    if calories is not None:
        update.message.reply_text(f"Your active calories burned in the last 24 hours: {calories} kcal.")
    else:
        update.message.reply_text("Failed to fetch data from Google Fit. Try again later.")

# Добавляем команду в диспетчер
dispatcher.add_handler(CommandHandler("fit_data", fit_data_command))

# Старт Flask-сервера
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
