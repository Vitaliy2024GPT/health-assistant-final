import os
import json
import logging
import redis
from flask import Flask, request, session, redirect, url_for
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from telegram import Update, BotCommand
from telegram.ext import Updater, CommandHandler, CallbackContext

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'supersecretkey')

# Redis для хранения токенов
redis_client = redis.StrictRedis(
    host=os.environ.get('REDIS_HOST', 'localhost'),
    port=int(os.environ.get('REDIS_PORT', 6379)),
    db=0,
    decode_responses=True
)

# Google OAuth2
GOOGLE_CLIENT_SECRETS_FILE = "client_secrets.json"
SCOPES = [
    'https://www.googleapis.com/auth/fitness.activity.read',
    'https://www.googleapis.com/auth/fitness.body.read',
    'https://www.googleapis.com/auth/userinfo.email',
    'https://www.googleapis.com/auth/userinfo.profile',
    'openid'
]

flow = Flow.from_client_secrets_file(
    GOOGLE_CLIENT_SECRETS_FILE,
    scopes=SCOPES,
    redirect_uri=os.environ.get('GOOGLE_REDIRECT_URI', 'http://localhost:5000/googleauth/callback')
)

# Telegram Bot
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN', 'your_telegram_token')
updater = Updater(TELEGRAM_TOKEN)
dispatcher = updater.dispatcher


# --- Google OAuth Routes ---
@app.route('/google_auth')
def google_auth():
    logger.info("Starting Google OAuth flow")
    authorization_url, state = flow.authorization_url()
    session['state'] = state
    logger.info(f"OAuth State saved in session: {state}")
    return redirect(authorization_url)


@app.route('/googleauth/callback')
def google_auth_callback():
    logger.info("Handling Google OAuth callback")
    
    state = request.args.get('state')
    code = request.args.get('code')
    
    if not state or state != session.get('state'):
        logger.error("OAuth State mismatch or missing state.")
        return "State mismatch error. Please try again.", 400
    
    if not code:
        logger.error("Missing authorization code in callback.")
        return "Missing authorization code. Please try again.", 400
    
    try:
        flow.fetch_token(authorization_response=request.url)
        credentials = flow.credentials
        user_id = session.get('user_id', 'default_user')

        # Сохраняем токены в Redis
        if redis_client:
            redis_client.set(
                f"user:{user_id}:google_credentials",
                json.dumps({
                    'token': credentials.token,
                    'refresh_token': credentials.refresh_token,
                    'token_uri': credentials.token_uri,
                    'client_id': credentials.client_id,
                    'client_secret': credentials.client_secret,
                    'scopes': credentials.scopes
                })
            )
            logger.info("OAuth tokens saved in Redis.")
        
        return "Authorization successful! You can now return to the bot."
    
    except Exception as e:
        logger.exception("Failed to fetch OAuth token:")
        return f"Failed to fetch OAuth token: {str(e)}", 500


# --- Telegram Bot Handlers ---
def start(update: Update, context: CallbackContext) -> None:
    logger.info("Command /start received")
    update.message.reply_text(
        "Добро пожаловать в Health Assistant 360! 🚀\n"
        "/start - Начать\n"
        "/profile - Показать профиль\n"
        "/health - Данные Google Fit\n"
        "/logout - Выйти\n"
        "/help - Справка"
    )


def help_command(update: Update, context: CallbackContext) -> None:
    logger.info("Command /help received")
    update.message.reply_text(
        "/start - Начать\n"
        "/profile - Показать профиль\n"
        "/health - Данные Google Fit\n"
        "/logout - Выйти\n"
        "/help - Справка"
    )


def profile(update: Update, context: CallbackContext) -> None:
    logger.info("Command /profile received")
    user_id = update.effective_user.id
    credentials = redis_client.get(f"user:{user_id}:google_credentials")
    
    if not credentials:
        update.message.reply_text(
            "Пожалуйста, пройдите авторизацию через Google: "
            "https://health-assistant-final.onrender.com/google_auth"
        )
    else:
        update.message.reply_text("Ваш профиль успешно загружен.")


def health(update: Update, context: CallbackContext) -> None:
    logger.info("Command /health received")
    user_id = update.effective_user.id
    credentials_json = redis_client.get(f"user:{user_id}:google_credentials")
    
    if not credentials_json:
        update.message.reply_text(
            "Требуется авторизация для доступа к данным Google Fit. "
            "Перейдите по ссылке: https://health-assistant-final.onrender.com/google_auth"
        )
        return
    
    try:
        credentials = Credentials.from_authorized_user_info(json.loads(credentials_json))
        service = build('fitness', 'v1', credentials=credentials)
        data = service.users().dataSources().list(userId='me').execute()
        update.message.reply_text(f"Данные Google Fit: {data}")
    except Exception as e:
        logger.exception("Failed to fetch Google Fit data:")
        update.message.reply_text(f"Ошибка при получении данных: {str(e)}")


def logout(update: Update, context: CallbackContext) -> None:
    logger.info("Command /logout received")
    user_id = update.effective_user.id
    redis_client.delete(f"user:{user_id}:google_credentials")
    update.message.reply_text("Вы успешно вышли из системы.")


# --- Telegram Command Registration ---
dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(CommandHandler("help", help_command))
dispatcher.add_handler(CommandHandler("profile", profile))
dispatcher.add_handler(CommandHandler("health", health))
dispatcher.add_handler(CommandHandler("logout", logout))

# --- Run Flask and Telegram Bot ---
if __name__ == '__main__':
    from threading import Thread
    
    def run_telegram_bot():
        logger.info("Starting Telegram bot...")
        updater.start_polling()
        updater.idle()
    
    telegram_thread = Thread(target=run_telegram_bot)
    telegram_thread.start()
    
    logger.info("Starting Flask server...")
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
