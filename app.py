import os
import logging
from flask import Flask, request, redirect, session, url_for
from flask_session import Session
from redis import Redis
from telegram.ext import Updater, CommandHandler
from database import save_google_token, get_user_by_chat_id

app = Flask(__name__)

# Конфигурация Flask
app.secret_key = os.urandom(24)
app.config['SESSION_TYPE'] = 'redis'
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_USE_SIGNER'] = True
app.config['SESSION_KEY_PREFIX'] = 'health_assistant:'
app.config['SESSION_REDIS'] = Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))

# Активируем сессии
Session(app)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
REDIRECT_URI = "https://health-assistant-final.onrender.com/oauth2callback"

updater = Updater(token=TELEGRAM_TOKEN, use_context=True)
dispatcher = updater.dispatcher

def start(update, context):
    update.message.reply_text("Welcome! Use /google_fit to connect Google Fit.")

def google_fit_command(update, context):
    chat_id = update.message.chat_id
    session["chat_id"] = chat_id
    update.message.reply_text(f"Authorize here: {url_for('authorize', _external=True)}")

@app.route("/authorize")
def authorize():
    chat_id = session.get("chat_id")
    if not chat_id:
        return "Error: Chat ID is missing. Please restart the connection.", 400

    return redirect(
        f"https://accounts.google.com/o/oauth2/v2/auth?"
        f"client_id={GOOGLE_CLIENT_ID}&redirect_uri={REDIRECT_URI}&response_type=code&scope=https://www.googleapis.com/auth/fitness.activity.read"
    )

@app.route("/oauth2callback")
def oauth2callback():
    code = request.args.get("code")
    chat_id = session.get("chat_id")
    if not chat_id:
        return "Error: Chat ID is missing. Please restart the connection.", 400

    response = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "code": code,
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "redirect_uri": REDIRECT_URI,
            "grant_type": "authorization_code"
        }
    )
    if response.ok:
        save_google_token(chat_id, response.json().get("access_token"))
        return "Google Fit connected successfully!"
    return "Error during authorization.", 400

dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(CommandHandler("google_fit", google_fit_command))

@app.route("/telegram_webhook", methods=["POST"])
def telegram_webhook():
    data = request.get_json()
    update = telegram.Update.de_json(data, updater.bot)
    dispatcher.process_update(update)
    return "OK"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
