import os
import json
from flask import Flask, request, redirect, session, jsonify, url_for
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import redis
import logging
import requests
from flask_session import Session

# Инициализация приложения Flask
app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'supersecretkey')

# Логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация Redis
redis_url = os.getenv('REDIS_URL')
redis_client = redis.from_url(redis_url) if redis_url else None

# Настройка Flask-Session
app.config['SESSION_TYPE'] = 'redis'
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_USE_SIGNER'] = True
app.config['SESSION_KEY_PREFIX'] = 'health_assistant_'
app.config['SESSION_REDIS'] = redis_client
Session(app)

# Google OAuth 2.0
google_credentials = os.getenv('GOOGLE_CREDENTIALS')
if not google_credentials:
    raise ValueError("GOOGLE_CREDENTIALS environment variable is not set")

credentials_info = json.loads(google_credentials)
flow = Flow.from_client_config(
    credentials_info,
    scopes=[
        'https://www.googleapis.com/auth/userinfo.email',
        'https://www.googleapis.com/auth/userinfo.profile',
        'openid',
        'https://www.googleapis.com/auth/fitness.activity.read',
        'https://www.googleapis.com/auth/fitness.body.read'
    ],
    redirect_uri=os.getenv('GOOGLE_AUTH_REDIRECT', 'https://health-assistant-final.onrender.com/googleauth/callback')
)

# Главная страница
@app.route('/')
def index():
    return "Welcome to Health Assistant 360"


# Google OAuth 2.0 авторизация
@app.route('/google_auth')
def google_auth():
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true'
    )
    session['state'] = state
    return redirect(authorization_url)


# Callback для Google OAuth
@app.route('/googleauth/callback')
def google_auth_callback():
    if session.get('state') != request.args.get('state'):
        return "State mismatch error. Please try again.", 400

    flow.fetch_token(authorization_response=request.url)
    credentials = flow.credentials
    session['credentials'] = {
        'token': credentials.token,
        'refresh_token': credentials.refresh_token,
        'token_uri': credentials.token_uri,
        'client_id': credentials.client_id,
        'client_secret': credentials.client_secret,
        'scopes': credentials.scopes
    }

    # Сохраняем в Redis
    if redis_client:
        redis_client.set(f"user:{session['credentials']['token']}:google_credentials", json.dumps(session['credentials']))

    return "Authorization successful! You can now return to the bot."


# Telegram Webhook
@app.route('/telegram_webhook', methods=['POST'])
def telegram_webhook():
    update = request.get_json()
    if update and 'message' in update:
        message_text = update['message'].get('text', '')
        chat_id = update['message']['chat']['id']

        commands = {
            '/start': lambda: send_telegram_message(chat_id, "Добро пожаловать в Health Assistant 360! 🚀"),
            '/profile': lambda: show_profile(chat_id),
            '/logout': lambda: logout_user(chat_id),
            '/health': lambda: show_health_data(chat_id),
            '/help': lambda: show_help(chat_id),
        }

        command = commands.get(message_text, lambda: send_telegram_message(chat_id, "Извините, я не понимаю эту команду."))
        command()

    return jsonify({"status": "ok"})


# Вспомогательная функция для отправки сообщений
def send_telegram_message(chat_id, text):
    telegram_token = os.getenv('TELEGRAM_TOKEN')
    if not telegram_token:
        logger.error("TELEGRAM_TOKEN is not set")
        return

    url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
    payload = {'chat_id': chat_id, 'text': text}
    response = requests.post(url, json=payload)
    if response.status_code != 200:
        logger.error(f"Failed to send message: {response.text}")


# Показ профиля
def show_profile(chat_id):
    credentials = session.get('credentials')
    if not credentials:
        auth_url = url_for('google_auth', _external=True)
        send_telegram_message(chat_id, f"Пожалуйста, пройдите авторизацию через Google: {auth_url}")
    else:
        user_info_service = build('oauth2', 'v2', credentials=Credentials(**credentials))
        user_info = user_info_service.userinfo().get().execute()
        send_telegram_message(chat_id, f"👤 Профиль:\nИмя: {user_info.get('name')}\nEmail: {user_info.get('email')}")


# Показ данных о здоровье
def show_health_data(chat_id):
    credentials = session.get('credentials')
    if not credentials:
        send_telegram_message(chat_id, "Требуется авторизация для доступа к данным Google Fit.")
    else:
        fitness_service = build('fitness', 'v1', credentials=Credentials(**credentials))
        data = fitness_service.users().dataset().aggregate(
            userId='me',
            body={
                "aggregateBy": [{"dataTypeName": "com.google.step_count.delta"}],
                "bucketByTime": {"durationMillis": 86400000},
                "startTimeMillis": 0,
                "endTimeMillis": 0
            }
        ).execute()
        send_telegram_message(chat_id, f"🏃 Данные здоровья:\n{json.dumps(data)}")


# Команда помощи
def show_help(chat_id):
    help_text = (
        "/start - Начать\n"
        "/profile - Показать профиль\n"
        "/health - Данные Google Fit\n"
        "/logout - Выйти\n"
        "/help - Справка"
    )
    send_telegram_message(chat_id, help_text)


# Выход из системы
def logout_user(chat_id):
    session.clear()
    send_telegram_message(chat_id, "Вы успешно вышли из системы.")


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 10000)))
