from flask import Flask, request, redirect, url_for, session, jsonify
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
import redis
import os
import json
from io import StringIO

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'your_secret_key')

# Redis client for session management
redis_client = redis.StrictRedis(
    host=os.environ.get('REDIS_HOST', 'localhost'),
    port=int(os.environ.get('REDIS_PORT', 6379)),
    db=0,
    decode_responses=True
)

# Google OAuth configuration
SCOPES = [
    'https://www.googleapis.com/auth/userinfo.email',
    'https://www.googleapis.com/auth/userinfo.profile',
    'openid',
    'https://www.googleapis.com/auth/fitness.body.read',
    'https://www.googleapis.com/auth/fitness.activity.read'
]
REDIRECT_URI = 'https://health-assistant-final.onrender.com/googleauth/callback'

# Использование данных из переменной окружения GOOGLE_CLIENT_SECRET_JSON
def get_flow():
    google_credentials_json = os.environ.get('GOOGLE_CLIENT_SECRET_JSON')
    if not google_credentials_json:
        raise ValueError("Переменная окружения GOOGLE_CLIENT_SECRET_JSON не установлена")
    
    client_secrets = json.load(StringIO(google_credentials_json))
    return Flow.from_client_config(
        client_secrets,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI
    )

# Маршруты API
@app.route('/google_auth')
def google_auth():
    state = os.urandom(24).hex()
    session['state'] = state
    try:
        redis_client.setex(state, 300, 'active')
    except redis.RedisError as e:
        app.logger.error(f"Redis error: {e}")
        return "Ошибка сервера. Попробуйте позже.", 500
    
    auth_url, _ = get_flow().authorization_url(state=state, access_type='offline', prompt='consent')
    return redirect(auth_url)

@app.route('/googleauth/callback', methods=['GET'])
def google_auth_callback():
    state = request.args.get('state')
    if not state or not redis_client.get(state):
        return "Ошибка проверки состояния. Попробуйте снова.", 400
    
    try:
        flow = get_flow()
        flow.fetch_token(authorization_response=request.url)
        credentials = flow.credentials
        user_info = build('oauth2', 'v2', credentials=credentials).userinfo().get().execute()
        chat_id = request.args.get('chat_id', 'unknown')
        redis_client.setex(f'user:{chat_id}:email', 3600, user_info.get('email', 'неизвестно'))
        redis_client.setex(f'user:{chat_id}:name', 3600, user_info.get('name', 'неизвестно'))
    except Exception as e:
        app.logger.error(f"OAuth callback failed: {str(e)}")
        return "Ошибка авторизации. Попробуйте снова.", 500
    finally:
        redis_client.delete(state)
    
    return redirect('https://t.me/<ваш_бот>?start=profile')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000, debug=True)
