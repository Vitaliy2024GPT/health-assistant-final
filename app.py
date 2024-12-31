from flask import Flask, redirect, request, session, url_for
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from flask_session import Session
import redis
import os
import logging

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'supersecretkey')

# Конфигурация Redis для хранения сессий
app.config['SESSION_TYPE'] = 'redis'
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_USE_SIGNER'] = True
app.config['SESSION_KEY_PREFIX'] = 'health_assistant_'
app.config['SESSION_REDIS'] = redis.StrictRedis(host='localhost', port=6379, db=0)
Session(app)

# Логирование
logging.basicConfig(level=logging.INFO)
app.logger.setLevel(logging.INFO)

# OAuth параметры
GOOGLE_CLIENT_SECRETS_FILE = 'client_secret.json'
SCOPES = [
    'https://www.googleapis.com/auth/userinfo.profile',
    'https://www.googleapis.com/auth/userinfo.email',
    'https://www.googleapis.com/auth/fitness.activity.read',
    'https://www.googleapis.com/auth/fitness.body.read'
]
REDIRECT_URI = 'https://health-assistant-final.onrender.com/googleauth/callback'


### 1. Маршрут для начала OAuth авторизации
@app.route('/google_auth')
def google_auth():
    flow = Flow.from_client_secrets_file(
        GOOGLE_CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI
    )
    auth_url, state = flow.authorization_url(
        access_type='offline',  # Обязательно для получения refresh_token
        include_granted_scopes='true',
        prompt='consent'  # Принудительно запрашиваем повторное согласие
    )
    session['state'] = state
    app.logger.info(f'🔑 OAuth state сохранён: {state}')
    return redirect(auth_url)


### 2. Маршрут для обработки ответа от Google
@app.route('/googleauth/callback')
def callback():
    state = session.get('state')
    if not state:
        app.logger.error('❌ State отсутствует в сессии.')
        return 'Ошибка: State отсутствует в сессии.', 400

    flow = Flow.from_client_secrets_file(
        GOOGLE_CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        state=state,
        redirect_uri=REDIRECT_URI
    )
    flow.fetch_token(authorization_response=request.url)

    credentials = flow.credentials
    session['credentials'] = {
        'token': credentials.token,
        'refresh_token': credentials.refresh_token,  # Должен быть сохранён
        'token_uri': credentials.token_uri,
        'client_id': credentials.client_id,
        'client_secret': credentials.client_secret,
        'scopes': credentials.scopes
    }

    if not credentials.refresh_token:
        app.logger.error('❌ Отсутствует refresh_token.')
        return 'Ошибка: Отсутствует refresh_token.', 400

    app.logger.info('✅ OAuth авторизация успешно завершена.')
    return redirect('/profile')


### 3. Маршрут для отображения профиля пользователя
@app.route('/profile')
def profile():
    credentials_data = session.get('credentials')
    if not credentials_data:
        app.logger.error('❌ Отсутствуют учётные данные.')
        return redirect('/google_auth')

    credentials = Credentials(
        token=credentials_data['token'],
        refresh_token=credentials_data['refresh_token'],
        token_uri=credentials_data['token_uri'],
        client_id=credentials_data['client_id'],
        client_secret=credentials_data['client_secret'],
        scopes=credentials_data['scopes']
    )

    if not credentials.refresh_token:
        app.logger.error('❌ Отсутствует refresh_token.')
        return 'Ошибка: Отсутствует refresh_token', 400

    from googleapiclient.discovery import build
    service = build('oauth2', 'v2', credentials=credentials)
    user_info = service.userinfo().get().execute()

    return f"Добро пожаловать, {user_info['name']}! Ваш email: {user_info['email']}"


### 4. Маршрут для выхода из системы
@app.route('/logout')
def logout():
    session.clear()
    app.logger.info('✅ Сессия очищена.')
    return redirect('/')


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000, debug=True)
