from flask import Flask, request, redirect, url_for, session, jsonify
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
import redis
import os
import json
from urllib.parse import urlparse
from io import StringIO

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'your_secret_key')

# Redis client for session management
redis_url = os.environ.get('REDIS_URL')
parsed_url = urlparse(redis_url)

redis_client = redis.StrictRedis(
    host=parsed_url.hostname,
    port=parsed_url.port,
    password=parsed_url.password,
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

@app.route('/')
def home():
    return "Добро пожаловать в Health Assistant 360! 🚀"

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
    else:
        response_text = "Неизвестная команда. Используйте /help для списка доступных команд."
    
    return jsonify({
        "method": "sendMessage",
        "chat_id": chat_id,
        "text": response_text
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000, debug=True)
