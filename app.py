import os
import json
from flask import Flask, request, redirect, session, url_for
from flask_session import Session
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from telegram import Update, Bot
from telegram.ext import Updater, CommandHandler, CallbackContext
import logging

# Инициализация Flask приложения
app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY')
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)

# Логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Телеграм бот
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
bot = Bot(token=TELEGRAM_TOKEN)

# Google OAuth 2.0
google_credentials = json.loads(os.getenv('GOOGLE_CREDENTIALS'))
GOOGLE_REDIRECT_URI = os.getenv('GOOGLE_AUTH_REDIRECT')

flow = Flow.from_client_config(
    google_credentials,
    scopes=['https://www.googleapis.com/auth/fitness.activity.read',
            'https://www.googleapis.com/auth/fitness.body.read',
            'https://www.googleapis.com/auth/userinfo.profile',
            'https://www.googleapis.com/auth/userinfo.email',
            'openid'],
    redirect_uri=GOOGLE_REDIRECT_URI
)

# ====================
# 📌 Flask маршруты
# ====================

@app.route('/')
def home():
    return 'Health Assistant 360 is running! 🚀'


@app.route('/google_auth')
def google_auth():
    auth_url, _ = flow.authorization_url(prompt='consent')
    return redirect(auth_url)


@app.route('/googleauth/callback')
def google_auth_callback():
    try:
        flow.fetch_token(authorization_response=request.url)
        credentials = flow.credentials
        session['google_credentials'] = credentials_to_dict(credentials)
        return redirect(url_for('profile'))
    except Exception as e:
        logger.error(f"Ошибка авторизации: {e}")
        return 'Ошибка авторизации Google.', 500


@app.route('/profile')
def profile():
    credentials = session.get('google_credentials')
    if not credentials:
        return redirect(url_for('google_auth'))

    try:
        creds = Credentials(**credentials)
        service = build('oauth2', 'v2', credentials=creds)
        user_info = service.userinfo().get().execute()
        return f'Привет, {user_info["name"]}! Ваш email: {user_info["email"]}'
    except Exception as e:
        logger.error(f"Ошибка получения профиля: {e}")
        return 'Ошибка получения данных профиля.', 500


@app.route('/health')
def health():
    credentials = session.get('google_credentials')
    if not credentials:
        return redirect(url_for('google_auth'))

    try:
        creds = Credentials(**credentials)
        fitness_service = build('fitness', 'v1', credentials=creds)
        data = fitness_service.users().dataset().aggregate(userId='me', body={
            "aggregateBy": [{"dataTypeName": "com.google.step_count.delta"}],
            "bucketByTime": {"durationMillis": 86400000},
            "startTimeMillis": 0,
            "endTimeMillis": 0
        }).execute()
        return f'Данные Google Fit: {data}'
    except Exception as e:
        logger.error(f"Ошибка данных Google Fit: {e}")
        return 'Ошибка получения данных Google Fit.', 500


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))


# ====================
# 📌 Telegram Bot
# ====================

def start(update: Update, context: CallbackContext):
    update.message.reply_text(
        "Добро пожаловать в Health Assistant 360! 🚀\n"
        "/profile - Показать профиль\n"
        "/health - Данные Google Fit\n"
        "/logout - Выйти\n"
        "/help - Справка"
    )


def profile_command(update: Update, context: CallbackContext):
    update.message.reply_text(
        f"Пожалуйста, пройдите авторизацию через Google: {GOOGLE_REDIRECT_URI}"
    )


def health_command(update: Update, context: CallbackContext):
    update.message.reply_text(
        "Требуется авторизация для доступа к данным Google Fit."
    )


def help_command(update: Update, context: CallbackContext):
    update.message.reply_text(
        "/start - Начать\n"
        "/profile - Показать профиль\n"
        "/health - Данные Google Fit\n"
        "/logout - Выйти\n"
        "/help - Справка"
    )


def logout_command(update: Update, context: CallbackContext):
    update.message.reply_text("Вы успешно вышли из системы.")


def telegram_bot():
    updater = Updater(token=TELEGRAM_TOKEN, use_context=True)
    dispatcher = updater.dispatcher

    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("profile", profile_command))
    dispatcher.add_handler(CommandHandler("health", health_command))
    dispatcher.add_handler(CommandHandler("help", help_command))
    dispatcher.add_handler(CommandHandler("logout", logout_command))

    updater.start_polling()
    updater.idle()


# ====================
# 📌 Вспомогательные функции
# ====================

def credentials_to_dict(credentials):
    return {
        'token': credentials.token,
        'refresh_token': credentials.refresh_token,
        'token_uri': credentials.token_uri,
        'client_id': credentials.client_id,
        'client_secret': credentials.client_secret,
        'scopes': credentials.scopes
    }


# ====================
# 📌 Запуск приложения
# ====================

if __name__ == '__main__':
    from threading import Thread

    # Запуск Telegram бота в отдельном потоке
    bot_thread = Thread(target=telegram_bot)
    bot_thread.start()

    # Запуск Flask приложения
    app.run(host='0.0.0.0', port=10000)
