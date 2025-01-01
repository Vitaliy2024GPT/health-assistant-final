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
if redis_url:
    redis_client = redis.from_url(redis_url)
else:
    logger.warning("REDIS_URL is not set. Redis functionality will be disabled.")
    redis_client = None

# Настройка Flask-Session
app.config['SESSION_TYPE'] = 'redis'
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_USE_SIGNER'] = True
app.config['SESSION_KEY_PREFIX'] = 'health_assistant_'
app.config['SESSION_REDIS'] = redis_client if redis_client else None
Session(app)

# Явный путь к client_secret.json
CLIENT_SECRET_PATH = os.path.join(os.path.dirname(__file__), 'client_secret.json')
if not os.path.exists(CLIENT_SECRET_PATH):
    raise FileNotFoundError(f"client_secret.json not found at {CLIENT_SECRET_PATH}")

# Инициализация Google OAuth2 Flow
flow = Flow.from_client_secrets_file(
    CLIENT_SECRET_PATH,
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
    logger.info("Starting Google OAuth flow")
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true'
    )
    session['state'] = state
    logger.info(f"OAuth state saved in session: {state}")
    return redirect(authorization_url)

# Callback для Google OAuth
@app.route('/googleauth/callback')
def google_auth_callback():
    logger.info("Handling Google OAuth callback")
    session_state = session.pop('state', None)  # Очищаем state после извлечения
    response_state = request.args.get('state')
    logger.info(f"Session state: {session_state}, Response state: {response_state}")

    if not session_state or session_state != response_state:
        logger.error("State mismatch error during OAuth callback")
        return "State mismatch error. Please try again.", 400

    try:
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

        user_info_service = build('oauth2', 'v2', credentials=credentials)
        user_info = user_info_service.userinfo().get().execute()

        if redis_client:
            redis_client.set(f"user:{user_info['email']}:google_credentials", json.dumps(session['credentials']))

        return jsonify(user_info)

    except Exception as e:
        logger.error(f"Failed during OAuth callback: {e}")
        return f"Error during OAuth callback: {e}", 500

# Telegram Webhook
@app.route('/telegram_webhook', methods=['POST'])
def telegram_webhook():
    logger.info("Received webhook update")
    update = request.get_json()
    logger.info(update)

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

# Вспомогательные функции

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

def show_profile(chat_id):
    credentials = session.get('credentials')
    if not credentials:
        auth_url = url_for('google_auth', _external=True)
        send_telegram_message(chat_id, f"Пожалуйста, пройдите авторизацию через Google: {auth_url}")
    else:
        user_info_service = build('oauth2', 'v2', credentials=Credentials(**credentials))
        user_info = user_info_service.userinfo().get().execute()
        send_telegram_message(chat_id, f"👤 Профиль:\nИмя: {user_info.get('name')}\nEmail: {user_info.get('email')}")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 10000)))
