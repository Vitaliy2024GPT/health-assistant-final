from flask import Flask, request, session, redirect, url_for
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
import redis
import os

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'your_secret_key')

# Redis client
redis_client = redis.StrictRedis(host=os.environ.get('REDIS_HOST', 'localhost'), port=6379, db=0, decode_responses=True)

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

flow = Flow.from_client_secrets_file(
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
    if session.get('authenticated'):
        user_email = session.get('user_email', 'неизвестно')
        user_name = session.get('user_name', 'неизвестно')
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
    redis_client.setex(state, 300, 'active')
    auth_url, _ = flow.authorization_url(state=state, access_type='offline', prompt='consent')
    return redirect(auth_url)

@app.route('/googleauth/callback', methods=['GET'])
def google_auth_callback():
    state = session.get('state')
    response_state = request.args.get('state')
    if state != response_state:
        return "Ошибка проверки состояния. Попробуйте снова.", 400
    
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
        session['authenticated'] = True
        
        user_info = build('oauth2', 'v2', credentials=credentials).userinfo().get().execute()
        session['user_email'] = user_info.get('email', 'неизвестно')
        session['user_name'] = user_info.get('name', 'неизвестно')
        
        redis_client.setex(f"user:{session['user_email']}", 3600, 'authenticated')
        return redirect('https://t.me/<ваш_бот>?start=profile')
    
    except Exception as e:
        app.logger.error(f"OAuth callback failed: {str(e)}")
        return "Ошибка авторизации. Попробуйте снова.", 500

@app.route('/logout')
def logout():
    session.clear()
    return "Вы успешно вышли из системы!"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000, debug=True)
