import os
import json
from flask import Flask, request, redirect, session, jsonify
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import redis
import logging

# Инициализация приложения Flask
app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'supersecretkey')

# Логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация Redis
redis_url = os.getenv('REDIS_URL')
redis_client = redis.from_url(redis_url)

# Чтение учетных данных Google из переменной окружения
google_credentials = os.getenv('GOOGLE_CREDENTIALS')
if not google_credentials:
    raise ValueError("GOOGLE_CREDENTIALS environment variable is not set")
credentials_info = json.loads(google_credentials)

# Инициализация Google OAuth2 Flow
flow = Flow.from_client_config(
    credentials_info,
    scopes=[
        'https://www.googleapis.com/auth/userinfo.email',
        'https://www.googleapis.com/auth/userinfo.profile',
        'openid'
    ],
    redirect_uri=os.getenv('GOOGLE_AUTH_REDIRECT')
)

# Главная страница
@app.route('/')
def index():
    return "Welcome to Health Assistant 360"

# Google OAuth 2.0 авторизация
@app.route('/google_auth')
def google_auth():
    logger.info("Starting Google OAuth flow")
    authorization_url, state = flow.authorization_url()
    session['state'] = state
    return redirect(authorization_url)

# Callback для Google OAuth
@app.route('/googleauth/callback')
def google_auth_callback():
    logger.info("Handling Google OAuth callback")
    state = session.get('state')
    if not state:
        return "State mismatch error", 400

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

    return jsonify(user_info)

# Webhook для Telegram
@app.route('/telegram_webhook', methods=['POST'])
def telegram_webhook():
    logger.info("Received webhook update")
    update = request.get_json()
    logger.info(update)
    return jsonify({"status": "ok"})

# Обновление токена Google
@app.route('/refresh_token')
def refresh_token():
    if 'credentials' not in session:
        return redirect('/google_auth')

    creds_info = session['credentials']
    credentials = Credentials(**creds_info)

    if credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())
        session['credentials'] = {
            'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': credentials.scopes
        }

    return "Token refreshed successfully"

# Тестовый маршрут для проверки работы сервиса
@app.route('/ping')
def ping():
    return "Pong!"

# Точка входа
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 10000)))
