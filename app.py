import os
import sys
import logging
import json
from flask import Flask, request, jsonify
from telegram import Update
from telegram.ext import Updater, CommandHandler, Dispatcher, CallbackContext
from database import (
    init_db, close_connection, add_user, get_user_by_chat_id
)
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
        "Then /googlefit to get data from Google Fit API."
    )

def register(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    if len(context.args) < 1:
        update.message.reply_text("Please provide a name. Usage: /register <name>")
        return

    name = " ".join(context.args)
    if len(name) > 50:
        update.message.reply_text("Name is too long. Please use a shorter name.")
        return

    add_user(chat_id, name)
    update.message.reply_text(f"User {name} registered successfully!")

def googlefit_command(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    user = get_user_by_chat_id(chat_id)
    if not user:
        update.message.reply_text("You are not registered. Use /register <name> first.")
        return

    try:
        service = google_fit_service()
        if not service:
            update.message.reply_text("Failed to connect to Google Fit API. Please try again later.")
            return

        # Example: Fetch data sources from Google Fit
        data_sources = service.users().dataSources().list(userId="me").execute()
        if not data_sources.get("dataSource"):
            update.message.reply_text("No data available in Google Fit.")
            return

        update.message.reply_text(f"Successfully connected to Google Fit! Found {len(data_sources['dataSource'])} data sources.")
    except Exception as e:
        logger.error(f"Error in /googlefit command: {e}")
        update.message.reply_text("An error occurred while fetching Google Fit data.")

@app.route("/telegram_webhook", methods=["POST"])
def telegram_webhook():
    try:
        logger.info("Received webhook update")
        data = request.get_json(force=True)
        update = Update.de_json(data, updater.bot)
        dispatcher.process_update(update)
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        logger.error(f"Error handling webhook: {e}")
        return jsonify({"error": "Failed to process webhook"}), 500

@app.route("/", methods=["GET"])
def health_check():
    return "Bot is running", 200

# === ОБРАБОТЧИКИ КОМАНД ===
dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(CommandHandler("register", register))
dispatcher.add_handler(CommandHandler("googlefit", googlefit_command))

# === ЗАПУСК ПРИЛОЖЕНИЯ ===
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    logger.info(f"Starting Flask application on port {port}")
    Thread(target=lambda: app.run(host="0.0.0.0", port=port)).start()
    updater.start_webhook(listen='0.0.0.0', port=port, url_path='/telegram_webhook')
    updater.bot.set_webhook(url=f"https://{os.getenv('RENDER_EXTERNAL_HOSTNAME')}/telegram_webhook")
    updater.idle()
