from flask import Flask, request, redirect, url_for, session, jsonify
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
import redis
import os
import json
import time
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

# Главная страница
@app.route('/')
def home():
    return "Добро пожаловать в Health Assistant 360! 🚀"

# Страница профиля пользователя
@app.route('/profile')
def profile():
    chat_id = request.args.get('chat_id')
    if not chat_id:
        return "Не указан chat_id. Попробуйте снова.", 400
    
    try:
        user_email = redis_client.get(f'user:{chat_id}:email')
        user_name = redis_client.get(f'user:{chat_id}:name')
        
        if user_email and user_name:
            return f"👤 Профиль пользователя:\nИмя: {user_name}\nEmail: {user_email}"
        else:
            return redirect('/google_auth')
    except redis.RedisError as e:
        app.logger.error(f"Redis error: {e}")
        return "Ошибка сервера. Попробуйте позже.", 500

# Аутентификация Google OAuth
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

# Callback для Google OAuth
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
        
        # Получение данных Google Fit
        fitness_service = build('fitness', 'v1', credentials=credentials)
        dataset = fitness_service.users().dataset().aggregate(
            userId='me',
            body={
                "aggregateBy": [{"dataTypeName": "com.google.weight"}, {"dataTypeName": "com.google.height"}],
                "bucketByTime": {"durationMillis": 86400000},
                "startTimeMillis": int((time.time() - 86400) * 1000),
                "endTimeMillis": int(time.time() * 1000)
            }
        ).execute()
        
        # Сохраняем данные в Redis
        health_data = json.dumps(dataset)
        redis_client.setex(f'user:{chat_id}:health', 3600, health_data)
        
    except Exception as e:
        app.logger.error(f"OAuth callback failed: {str(e)}")
        return "Ошибка авторизации. Попробуйте снова.", 500
    finally:
        redis_client.delete(state)
    
    return redirect(f'https://health-assistant-final.onrender.com/health?chat_id={chat_id}')

# Страница здоровья пользователя
@app.route('/health')
def health():
    chat_id = request.args.get('chat_id')
    if not chat_id:
        return "Не указан chat_id. Попробуйте снова.", 400
    
    try:
        health_data = redis_client.get(f'user:{chat_id}:health')
        if health_data:
            parsed_data = json.loads(health_data)
            return jsonify(parsed_data)
        else:
            return "Данные о здоровье отсутствуют. Пройдите синхронизацию с Google Fit."
    except redis.RedisError as e:
        app.logger.error(f"Redis error: {e}")
        return "Ошибка сервера. Попробуйте позже.", 500

# Выход из системы
@app.route('/logout')
def logout():
    chat_id = request.args.get('chat_id', 'unknown')
    redis_client.delete(f'user:{chat_id}:email')
    redis_client.delete(f'user:{chat_id}:name')
    return "Вы успешно вышли из системы!"

# Обработка команд Telegram-бота
@app.route('/telegram_webhook', methods=['POST'])
def telegram_webhook():
    data = request.get_json()
    if not data:
        app.logger.error("Empty or invalid webhook payload.")
        return jsonify({"error": "Invalid payload"}), 400
    
    message = data.get('message', {})
    text = message.get('text', '')
    chat_id = message.get('chat', {}).get('id')
    
    if not chat_id:
        app.logger.error("Chat ID not found in webhook payload.")
        return jsonify({"error": "Missing chat ID"}), 400
    
    if text == '/start':
        response_text = "Добро пожаловать в Health Assistant 360! 🚀"
    elif text == '/profile':
        response_text = f"Переход к вашему профилю: https://health-assistant-final.onrender.com/profile?chat_id={chat_id}"
    elif text == '/health':
        response_text = f"Переход к вашим данным о здоровье: https://health-assistant-final.onrender.com/health?chat_id={chat_id}"
    elif text == '/help':
        response_text = '''🛠 Доступные команды:
- /start - Начать взаимодействие
- /profile - Показать профиль
- /health - Показать данные о здоровье
- /logout - Выйти из системы
- /help - Показать это сообщение'''
    else:
        response_text = "Неизвестная команда. Используйте /help для списка доступных команд."
    
    return jsonify({
        "method": "sendMessage",
        "chat_id": chat_id,
        "text": response_text
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000, debug=True)
