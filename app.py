import os
import sys
import logging
from flask import Flask, request, jsonify, redirect, session, url_for
from flask_session import Session
from telegram import Update
from telegram.ext import Updater, CommandHandler
from database import (
    init_db, close_connection, get_user_by_chat_id, save_google_token
)
import requests
from datetime import datetime, timedelta
import urllib.parse

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Настройка Flask-Session
app.config["SESSION_TYPE"] = "filesystem"
app.config["SESSION_PERMANENT"] = False
Session(app)

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

# Telegram команды
def start(update, context):
    update.message.reply_text(
        "Welcome to Health Assistant Bot!\nUse /google_fit to connect Google Fit."
    )

def google_fit_command(update, context):
    chat_id = update.message.chat_id
    session["chat_id"] = chat_id  # Сохраняем chat_id в сессии
    logger.info(f"Chat ID {chat_id} saved in session.")
    fit_url = url_for('authorize', _external=True)
    update.message.reply_text(f"Connect Google Fit here: {fit_url}")

# Google OAuth маршруты
@app.route("/")
def home():
    return "Health Assistant API is running!", 200

@app.route("/authorize")
def authorize():
    chat_id = session.get("chat_id")
    if not chat_id:
        logger.error("Chat ID is missing in session during /authorize.")
        return "Error: Chat ID is missing. Please restart the connection.", 400

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
    chat_id = session.get("chat_id")
    if not chat_id:
        logger.error("Chat ID is missing in session during /oauth2callback.")
        return "Error: Chat ID is missing. Please restart the connection."

    payload = {
        "code": code,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code"
    }
    response = requests.post("https://oauth2.googleapis.com/token", data=payload)
    if response.ok:
        access_token = response.json().get("access_token")
        save_google_token(chat_id, access_token)  # Сохраняем токен в базе данных
        logger.info(f"Google Fit token saved for chat ID {chat_id}.")
        return "Google Fit connected successfully!"
    logger.error(f"Error during Google Fit authorization: {response.text}")
    return f"Error during authorization: {response.text}", 400

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

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
