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

# Инициализация Flask-приложения
app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY')

# Настройка сессий
app.config['SESSION_TYPE'] = 'redis'
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_USE_SIGNER'] = True
app.config['SESSION_KEY_PREFIX'] = 'health_assistant_'
app.config['SESSION_REDIS'] = redis.from_url(os.getenv('REDIS_URL'))
Session(app)

# Настройка Telegram-бота
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
WEBHOOK_URL = os.getenv('WEBHOOK_URL')
bot = Bot(token=TELEGRAM_TOKEN)

# Google OAuth 2.0
GOOGLE_AUTH_REDIRECT = os.getenv('GOOGLE_AUTH_REDIRECT')
GOOGLE_CREDENTIALS = os.getenv('GOOGLE_CREDENTIALS')

# Google OAuth Flow
flow = Flow.from_client_config(
    client_config=eval(GOOGLE_CREDENTIALS),
    scopes=[
        "https://www.googleapis.com/auth/fitness.activity.read",
        "https://www.googleapis.com/auth/fitness.body.read",
        "openid", "email", "profile"
    ],
    redirect_uri=GOOGLE_AUTH_REDIRECT
)

# === Flask Маршруты ===

@app.route('/')
def home():
    return "Health Assistant 360 is running!"


@app.route('/google_auth')
def google_auth():
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true'
    )
    session['state'] = state
    return redirect(authorization_url)


@app.route('/googleauth/callback')
def google_auth_callback():
    flow.fetch_token(authorization_response=request.url)
    credentials = flow.credentials
    session['credentials'] = credentials_to_dict(credentials)
    return redirect(url_for('profile'))


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
        "startTimeMillis": 0,
        "endTimeMillis": 1
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


@app.route('/telegram_webhook', methods=['POST'])
def telegram_webhook():
    from telegram import Update
    from telegram.ext import Dispatcher
    
    dispatcher = Dispatcher(bot, None, workers=0)
    update = Update.de_json(request.get_json(force=True), bot)
    dispatcher.process_update(update)
    return 'OK', 200


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


# Восстановленные недостающие функции
def show_help(chat_id):
    bot.send_message(chat_id=chat_id, text="""
    Доступные команды:
    /start - Начать
    /profile - Показать профиль
    /health - Показать данные Google Fit
    /help - Показать помощь
    /logout - Выйти
    """)


def start_telegram_bot():
    updater = Updater(token=TELEGRAM_TOKEN, use_context=True)
    dispatcher = updater.dispatcher

    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("profile", profile_command))
    dispatcher.add_handler(CommandHandler("health", health_command))
    dispatcher.add_handler(CommandHandler("help", help_command))
    dispatcher.add_handler(CommandHandler("logout", logout_command))

    updater.start_webhook(
        listen='0.0.0.0',
        port=10000,
        url_path=TELEGRAM_TOKEN,
        webhook_url=f"{WEBHOOK_URL}/telegram_webhook"
    )
    updater.idle()


# === Запуск приложения ===

if __name__ == '__main__':
    from threading import Thread
    
    # Запуск Telegram-бота в отдельном потоке
    bot_thread = Thread(target=start_telegram_bot)
    bot_thread.start()
    
    # Запуск Flask-приложения
    app.run(host='0.0.0.0', port=10000)
