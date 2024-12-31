import os
from flask import Flask, request, session, redirect, url_for, jsonify
from flask_session import Session
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import redis
import logging

# === Логирование ===
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# === Инициализация Flask ===
app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY')

# === Настройка Redis и сессий ===
try:
    redis_url = os.getenv('REDIS_URL')
    app.config['SESSION_TYPE'] = 'redis'
    app.config['SESSION_PERMANENT'] = False
    app.config['SESSION_USE_SIGNER'] = True
    app.config['SESSION_KEY_PREFIX'] = 'health_assistant_'
    app.config['SESSION_REDIS'] = redis.from_url(redis_url)
    app.config['SESSION_COOKIE_NAME'] = 'health_assistant_session'
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SECURE'] = False
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    Session(app)
    logger.info("✅ Redis session initialized successfully!")
except Exception as e:
    logger.error(f"❌ Redis session initialization failed: {e}")

# === Google OAuth ===
GOOGLE_AUTH_REDIRECT = os.getenv('GOOGLE_AUTH_REDIRECT')
GOOGLE_CREDENTIALS = os.getenv('GOOGLE_CREDENTIALS')

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

# === Вспомогательные функции ===
def credentials_to_dict(credentials):
    return {
        'token': credentials.token,
        'refresh_token': credentials.refresh_token,
        'token_uri': credentials.token_uri,
        'client_id': credentials.client_id,
        'client_secret': credentials.client_secret,
        'scopes': credentials.scopes
    }

# === Маршруты ===
@app.route('/')
def home():
    return "Health Assistant 360 is running!"


@app.route('/google_auth')
def google_auth():
    try:
        session.clear()
        authorization_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent'  # Принудительный запрос refresh_token
        )
        session['state'] = state
        session.modified = True

        # Логируем сессию и Redis-состояние
        logger.info(f"✅ OAuth state сохранён: {state}")
        logger.info(f"✅ Session после сохранения state: {dict(session)}")
        redis_client = redis.from_url(redis_url)
        logger.info(f"✅ Redis ключи: {redis_client.keys('*')}")

        return redirect(authorization_url)
    except Exception as e:
        logger.error(f"❌ Ошибка Google OAuth: {e}")
        return f"Ошибка Google OAuth: {e}", 500


@app.route('/googleauth/callback')
def google_auth_callback():
    try:
        state = request.args.get('state')
        session_state = session.get('state')

        logger.info(f"🔄 Callback State: {state}, Session State: {session_state}")
        logger.info(f"🔄 Session data: {dict(session)}")

        if not state:
            logger.error("❌ State отсутствует в запросе.")
            return "State is missing. Please try again.", 400

        if not session_state:
            logger.error("❌ State в сессии отсутствует.")
            return "Session expired. Please start the authorization again.", 400

        if state != session_state:
            logger.error(f"❌ State mismatch. Expected: {session_state}, Got: {state}")
            session.pop('state', None)
            return "State mismatch. Please try again.", 400

        flow.fetch_token(authorization_response=request.url)
        credentials = flow.credentials

        if not credentials.refresh_token:
            logger.warning("❗ Refresh token отсутствует. Потребуется повторная авторизация.")

        session['credentials'] = credentials_to_dict(credentials)
        session.pop('state', None)
        session.modified = True
        logger.info("✅ OAuth авторизация успешно завершена.")
        return redirect(url_for('profile'))
    except Exception as e:
        logger.error(f"❌ Ошибка Google OAuth: {e}")
        session.pop('state', None)
        return f"Ошибка Google OAuth: {e}", 500


@app.route('/profile')
def profile():
    if 'credentials' not in session:
        logger.error("❌ Нет данных учетных данных в сессии.")
        return redirect(url_for('google_auth'))
    
    credentials = Credentials(**session['credentials'])

    if not credentials.refresh_token:
        logger.error("❌ Отсутствует refresh_token.")
        return "Ошибка: отсутствует refresh_token. Повторите авторизацию.", 400

    try:
        service = build('oauth2', 'v2', credentials=credentials)
        user_info = service.userinfo().get().execute()
        return jsonify(user_info)
    except Exception as e:
        logger.error(f"❌ Ошибка профиля: {e}")
        return f"Ошибка профиля: {e}", 500


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))


# === Запуск приложения ===
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
