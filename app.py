from flask import Flask, request, redirect, jsonify
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from telegram.ext import CommandHandler, Updater
import os

# Инициализация Flask-приложения
app = Flask(__name__)

# Переменные окружения
GOOGLE_AUTH_REDIRECT = os.getenv('GOOGLE_AUTH_REDIRECT', 'https://your-app.com/googleauth/callback')
GOOGLE_CREDENTIALS = os.getenv('GOOGLE_CREDENTIALS')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# Инициализация Google OAuth Flow
flow = Flow.from_client_secrets_file(
    'credentials.json',  # Убедитесь, что этот файл загружен в проект
    scopes=['https://www.googleapis.com/auth/fitness.activity.read'],
    redirect_uri=GOOGLE_AUTH_REDIRECT
)

# ==========================
# Flask Routes
# ==========================

@app.route('/')
def home():
    return "Health Assistant 360 is running!"

@app.route('/googleauth')
def google_auth():
    """Инициализация авторизации Google Fit."""
    auth_url, _ = flow.authorization_url(prompt='consent')
    return redirect(auth_url)

@app.route('/googleauth/callback')
def google_auth_callback():
    """Обработка кода авторизации и обмен на токен."""
    code = request.args.get('code')
    if code:
        flow.fetch_token(code=code)
        credentials = flow.credentials
        # Сохранение токена в файл (или в базу данных)
        with open('google_fit_token.json', 'w') as token_file:
            token_file.write(credentials.to_json())
        return "Успешно авторизовано через Google Fit! Можете вернуться в Telegram-бот."
    return "Ошибка авторизации через Google Fit."

@app.route('/googlefit')
def google_fit():
    """Получение данных из Google Fit."""
    try:
        with open('google_fit_token.json', 'r') as token_file:
            creds_data = token_file.read()
        credentials = Credentials.from_authorized_user_info(eval(creds_data))
        service = build('fitness', 'v1', credentials=credentials)
        
        data = service.users().dataset().aggregate(userId='me', body={
            "aggregateBy": [{"dataTypeName": "com.google.step_count.delta"}],
            "bucketByTime": {"durationMillis": 86400000},
            "startTimeMillis": 1704067200000,
            "endTimeMillis": 1704153600000
        }).execute()
        
        return jsonify(data)
    except Exception as e:
        return f"Ошибка при получении данных из Google Fit: {e}"

# ==========================
# Telegram Bot Handlers
# ==========================

updater = Updater(TELEGRAM_TOKEN)
dispatcher = updater.dispatcher

def start(update, context):
    update.message.reply_text("Добро пожаловать в Health Assistant Bot!\n"
                              "Команды:\n"
                              "/googleauth - Авторизация Google Fit\n"
                              "/googlefit - Получить данные из Google Fit")

def googleauth(update, context):
    update.message.reply_text(f'Пожалуйста, авторизуйтесь через Google Fit по ссылке: {GOOGLE_AUTH_REDIRECT}')

def googlefit(update, context):
    try:
        with open('google_fit_token.json', 'r') as token_file:
            creds_data = token_file.read()
        credentials = Credentials.from_authorized_user_info(eval(creds_data))
        service = build('fitness', 'v1', credentials=credentials)
        
        data = service.users().dataset().aggregate(userId='me', body={
            "aggregateBy": [{"dataTypeName": "com.google.step_count.delta"}],
            "bucketByTime": {"durationMillis": 86400000},
            "startTimeMillis": 1704067200000,
            "endTimeMillis": 1704153600000
        }).execute()
        
        update.message.reply_text(f'Данные из Google Fit:\n{data}')
    except Exception as e:
        update.message.reply_text(f'Ошибка при получении данных из Google Fit: {e}')

# Добавление обработчиков команд
dispatcher.add_handler(CommandHandler('start', start))
dispatcher.add_handler(CommandHandler('googleauth', googleauth))
dispatcher.add_handler(CommandHandler('googlefit', googlefit))

# Запуск Telegram-бота
def run_telegram_bot():
    updater.start_polling()
    updater.idle()

# ==========================
# Main Entry Point
# ==========================

if __name__ == '__main__':
    import threading
    telegram_thread = threading.Thread(target=run_telegram_bot)
    telegram_thread.start()
    app.run(host='0.0.0.0', port=10000)
