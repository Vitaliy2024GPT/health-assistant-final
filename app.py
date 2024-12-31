import os
from flask import Flask, request, session, redirect, url_for, jsonify
from flask_session import Session
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from telegram import Bot, Update
from telegram.ext import Dispatcher, CommandHandler
from threading import Thread
import redis
import logging

# === Настройка логирования ===
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# === Инициализация Flask-приложения ===
app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY')

# === Настройка сессий ===
try:
    redis_url = os.getenv('REDIS_URL')
    app.config['SESSION_TYPE'] = 'redis'
    app.config['SESSION_PERMANENT'] = False
    app.config['SESSION_USE_SIGNER'] = True
    app.config['SESSION_KEY_PREFIX'] = 'health_assistant_'
    app.config['SESSION_REDIS'] = redis.from_url(redis_url)
    Session(app)
    logger.info("✅ Redis session initialized successfully!")
except Exception as e:
    logger.error(f"❌ Redis session initialization failed: {e}")

# === Настройка Telegram-бота ===
try:
    TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
    WEBHOOK_URL = os.getenv('WEBHOOK_URL')
    bot = Bot(token=TELEGRAM_TOKEN)
    logger.info("✅ Telegram bot initialized successfully!")
except Exception as e:
    logger.error(f"❌ Telegram bot initialization failed: {e}")

# === Google OAuth 2.0 ===
try:
    GOOGLE_AUTH_REDIRECT = os.getenv('GOOGLE_AUTH_REDIRECT')
    GOOGLE_CREDENTIALS = os.getenv('GOOGLE_CREDENTIALS')
    flow = Flow.from_client_config(
        client_config=eval(GOOGLE_CREDENTIALS),
        scopes=[
            "https://www.googleapis.com/auth/fitness.activity.read",
            "https://www.googleapis.com/auth/fitness.body.read",
            "https://www.googleapis.com/auth/userinfo.email",
            "https://www.googleapis.com/auth/userinfo.profile",
            "openid"
        ],
        redirect_uri=GOOGLE_AUTH_REDIRECT
    )
    logger.info("✅ Google OAuth flow initialized successfully!")
except Exception as e:
    logger.error(f"❌ Google OAuth flow initialization failed: {e}")

# === Flask Маршруты ===

@app.route('/')
def home():
    return "Health Assistant 360 is running!"


@app.route('/google_auth')
def google_auth():
    try:
        session.clear()  # Очистка старой сессии
        authorization_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true'
        )
        session['state'] = state
        session.modified = True  # Обновление сессии
        logger.info(f"OAuth state сохранён: {state}")
        return redirect(authorization_url)
    except Exception as e:
        logger.error(f"Ошибка Google OAuth: {e}")
        return f"Ошибка Google OAuth: {e}", 500


@app.route('/googleauth/callback')
def google_auth_callback():
    try:
        state = request.args.get('state')
        session_state = session.get('state')

        if not state:
            logger.error("State отсутствует в запросе.")
            session.pop('state', None)
            return "State is missing. Please try again.", 400

        if state != session_state:
            logger.error(f"State mismatch. Expected: {session_state}, Got: {state}")
            session.pop('state', None)
            return "State mismatch. Please try again.", 400

        if 'code' not in request.args:
            logger.error("Missing 'code' parameter in callback.")
            return "Missing 'code' parameter. Please try again.", 400

        # Получаем токен
        flow.fetch_token(authorization_response=request.url)
        credentials = flow.credentials
        session['credentials'] = credentials_to_dict(credentials)
        session.pop('state', None)
        session.modified = True
        logger.info("✅ OAuth авторизация успешно завершена.")
        return redirect(url_for('profile'))

    except Exception as e:
        logger.error(f"Ошибка Google OAuth: {e}")
        session.pop('state', None)
        return f"Ошибка Google OAuth: {e}", 500


@app.route('/profile')
def profile():
    if 'credentials' not in session:
        return redirect(url_for('google_auth'))
    
    credentials = Credentials(**session['credentials'])
    service = build('oauth2', 'v2', credentials=credentials)
    user_info = service.userinfo().get().execute()
    return jsonify(user_info)


@app.route('/health')
def health():
    if 'credentials' not in session:
        return redirect(url_for('google_auth'))
    
    credentials = Credentials(**session['credentials'])
    fitness_service = build('fitness', 'v1', credentials=credentials)
    data = fitness_service.users().dataset().aggregate(userId='me', body={
        "aggregateBy": [{"dataTypeName": "com.google.step_count.delta"}],
        "bucketByTime": {"durationMillis": 86400000},
    }).execute()
    return jsonify(data)


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))


@app.route('/telegram_webhook', methods=['POST'])
def telegram_webhook():
    try:
        update = Update.de_json(request.get_json(force=True), bot)
        dispatcher = Dispatcher(bot, None, workers=1)
        
        dispatcher.add_handler(CommandHandler("start", start))
        dispatcher.add_handler(CommandHandler("profile", profile_command))
        dispatcher.add_handler(CommandHandler("health", health_command))
        dispatcher.add_handler(CommandHandler("help", help_command))
        dispatcher.add_handler(CommandHandler("logout", logout_command))
        dispatcher.add_handler(CommandHandler("google_auth", google_auth_command))
        
        dispatcher.process_update(update)
        return 'OK', 200
    
    except Exception as e:
        logger.error(f"Ошибка в telegram_webhook: {e}")
        return f"Internal Server Error: {e}", 500


# === Telegram Команды ===

def start(update, context):
    update.message.reply_text("Добро пожаловать в Health Assistant 360! 🚀")


def profile_command(update, context):
    update.message.reply_text("Пожалуйста, авторизуйтесь через Google: /google_auth")


def health_command(update, context):
    update.message.reply_text("Получение данных Google Fit. Пожалуйста, подождите...")


def help_command(update, context):
    update.message.reply_text(
        "/start - Начать\n"
        "/profile - Показать профиль\n"
        "/health - Данные Google Fit\n"
        "/logout - Выйти\n"
        "/help - Справка"
    )


def logout_command(update, context):
    session.clear()
    update.message.reply_text("Вы вышли из системы. До встречи!")


def google_auth_command(update, context):
    auth_url = GOOGLE_AUTH_REDIRECT
    update.message.reply_text(f"Перейдите по ссылке для авторизации: {auth_url}")


# === Запуск приложения ===

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
