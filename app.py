import os
from flask import Flask, request, session, redirect, url_for, jsonify
from flask_session import Session
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from telegram import Bot, Update
from telegram.ext import Updater, CommandHandler, Dispatcher
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
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
WEBHOOK_URL = os.getenv('WEBHOOK_URL')
bot = Bot(token=TELEGRAM_TOKEN)

# === Google OAuth 2.0 ===
GOOGLE_AUTH_REDIRECT = os.getenv('GOOGLE_AUTH_REDIRECT')
GOOGLE_CREDENTIALS = os.getenv('GOOGLE_CREDENTIALS')

# === Google OAuth Flow ===
try:
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

        if not state or state != session_state:
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
        session.modified = True  # Обновление сессии
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


def credentials_to_dict(credentials):
    return {
        'token': credentials.token,
        'refresh_token': credentials.refresh_token,
        'token_uri': credentials.token_uri,
        'client_id': credentials.client_id,
        'client_secret': credentials.client_secret,
        'scopes': credentials.scopes
    }


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))


# === Запуск приложения ===

if __name__ == '__main__':
    bot_thread = Thread(target=lambda: app.run(host='0.0.0.0', port=10000))
    bot_thread.start()
