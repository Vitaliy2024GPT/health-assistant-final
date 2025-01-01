from flask import Flask, request, redirect, url_for, session
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
import redis
import os

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'your_secret_key')

# Redis client for session management
redis_client = redis.StrictRedis(
    host=os.environ.get('REDIS_HOST', 'localhost'),
    port=6379,
    db=0,
    decode_responses=True
)

# Google OAuth configuration
CLIENT_SECRETS_FILE = "client_secret.json"
SCOPES = [
    'https://www.googleapis.com/auth/userinfo.email',
    'https://www.googleapis.com/auth/userinfo.profile',
    'openid',
    'https://www.googleapis.com/auth/fitness.body.read',
    'https://www.googleapis.com/auth/fitness.activity.read'
]
REDIRECT_URI = 'https://health-assistant-final.onrender.com/googleauth/callback'

def get_flow():
    return Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI
    )

@app.route('/start')
def start():
    return "Добро пожаловать в Health Assistant 360! 🚀"

@app.route('/profile')
def profile():
    chat_id = request.args.get('chat_id')
    user_email = redis_client.get(f'user:{chat_id}:email')
    user_name = redis_client.get(f'user:{chat_id}:name')
    if user_email and user_name:
        return f"👤 Профиль пользователя:\nИмя: {user_name}\nEmail: {user_email}"
    else:
        return redirect('/google_auth')

@app.route('/health')
def health():
    return "📊 Ваши данные о здоровье: [здесь будет информация о здоровье]."

@app.route('/help')
def help():
    return '''🛠 Доступные команды:
    /start - Начать взаимодействие
    /profile - Показать профиль
    /health - Показать данные о здоровье
    /logout - Выйти из системы
    /help - Показать это сообщение'''

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

@app.route('/logout')
def logout():
    chat_id = request.args.get('chat_id', 'unknown')
    redis_client.delete(f'user:{chat_id}:email')
    redis_client.delete(f'user:{chat_id}:name')
    return "Вы успешно вышли из системы!"

@app.route('/telegram_webhook', methods=['POST'])
def telegram_webhook():
    data = request.get_json()
    if not data:
        app.logger.error("Empty or invalid webhook payload.")
        return "Invalid payload", 400
    
    message = data.get('message', {})
    text = message.get('text', '')
    chat_id = message.get('chat', {}).get('id')
    
    if not chat_id:
        app.logger.error("Chat ID not found in webhook payload.")
        return "Missing chat ID", 400
    
    if text == '/start':
        return "Добро пожаловать в Health Assistant 360! 🚀"
    elif text == '/help':
        return '''🛠 Доступные команды:
    /start - Начать взаимодействие
    /profile - Показать профиль
    /health - Показать данные о здоровье
    /logout - Выйти из системы
    /help - Показать это сообщение'''
    elif text == '/profile':
        return redirect(f"/profile?chat_id={chat_id}")
    elif text == '/health':
        return redirect(f"/health?chat_id={chat_id}")
    else:
        return "Неизвестная команда. Используйте /help для списка доступных команд."

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000, debug=True)
