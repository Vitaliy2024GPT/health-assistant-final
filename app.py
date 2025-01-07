import logging
import os
import json
from urllib.parse import urlparse
from datetime import timedelta

from flask import Flask, request, session, redirect, url_for, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_session import Session

import redis
import google_auth_httplib2
from google.oauth2 import service_account
from googleapiclient.discovery import build
from google.oauth2 import credentials
from google.auth.transport.requests import Request


from bot.telegram import TelegramBot
from google_auth_oauthlib.flow import Flow

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Инициализация Flask
app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'supersecretkey')
app.config['SESSION_TYPE'] = 'redis'
app.config['SESSION_PERMANENT'] = True
app.config['SESSION_USE_SIGNER'] = True
app.config['SESSION_REDIS'] = redis.from_url(os.environ.get('REDIS_URL'))
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=1)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///users.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Инициализация расширений Flask
db = SQLAlchemy(app)
server_session = Session(app)


# Модель пользователя
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    google_id = db.Column(db.String(100), unique=True, nullable=False)
    telegram_id = db.Column(db.String(100), unique=True, nullable=True)


# Создание таблиц базы данных при первом запуске
with app.app_context():
    db.create_all()


# Функция для проверки наличия пользователя в БД
def get_user_from_db(google_id):
    user = User.query.filter_by(google_id=google_id).first()
    if user:
        logging.info(f"User found in database: {user.google_id}")
        return user
    else:
        logging.info(f"User not found in database: {google_id}")
        return None


# Конфигурация Google OAuth
def get_google_flow():
    CLIENT_SECRET_JSON = json.loads(os.environ.get('GOOGLE_CLIENT_SECRET_JSON'))
    scopes =  [
            'https://www.googleapis.com/auth/fitness.activity.read',
            'https://www.googleapis.com/auth/fitness.body.read',
            'https://www.googleapis.com/auth/fitness.location.read',
            'openid', 'email', 'profile'
        ]
    flow = Flow.from_client_config(
        CLIENT_SECRET_JSON,
        scopes=scopes,
        redirect_uri=os.environ.get('GOOGLE_AUTH_REDIRECT')
    )
    return flow


# Маршрут для авторизации Google
@app.route('/googleauth', methods=['GET'])
def googleauth():
    flow = get_google_flow()
    authorization_url, state = flow.authorization_url(
        access_type='offline',
       
    )
    session['state'] = state
    logging.info(f"Redirecting user to Google for authorization: {authorization_url}")
    return redirect(authorization_url)


# Маршрут для колбека Google OAuth
@app.route('/googleauth/callback')
def googleauth_callback():
    if 'state' in session:
      state = session['state']
      flow = get_google_flow()
      flow.fetch_token(authorization_response=request.url)
      credentials = flow.credentials
      logging.info(f"Google credentials received and stored in session")
      session['credentials'] = credentials_to_dict(credentials)
  
      # Получение данных пользователя
      google_id = credentials.id_token['sub']
      user = get_user_from_db(google_id)
  
      if user:
          session['user_id'] = user.id
      else:
          # Создание нового пользователя
          new_user = User(google_id=google_id)
          db.session.add(new_user)
          db.session.commit()
          session['user_id'] = new_user.id
          logging.info(f"New user created with google_id: {google_id}")
      return redirect(url_for('dashboard'))
    else:
       return "State is missing"

# Маршрут для дэшборда
@app.route('/dashboard', methods=['GET'])
def dashboard():
    if 'user_id' not in session:
        logging.info(f"User not authorized")
        return redirect(url_for('googleauth'))

    user_id = session['user_id']
    logging.info(f"User with ID {user_id} is authorized and on the dashboard page")
    return render_template('dashboard.html', user_id=user_id)


# Маршрут для данных Google Fit
@app.route('/get_data', methods=['GET'])
def get_data():
    if 'credentials' not in session:
        return redirect(url_for('googleauth'))

    creds = credentials_from_dict(session['credentials'])
    logging.info(f"Fetching Google Fit data with credentials: {creds}")
    fitness_service = build('fitness', 'v1', credentials=creds)
    try:
      datasets = fitness_service.users().dataSources().datasets().get(
          userId='me',
          dataSourceId='derived:com.google.step_count.delta:com.google.android.gms:estimated_steps',
          datasetId='0-' + str(int((datetime.datetime.now() + timedelta(hours=3)).timestamp() * 1000000000))
      ).execute()
      logging.info(f"Successfully fetched datasets: {datasets}")
      return datasets

    except Exception as e:
       logging.error(f"Error fetching Google Fit data: {e}")
       return {"error": "Failed to fetch google fit data"}

# Конвертация credentials
def credentials_to_dict(credentials):
    return {
        'token': credentials.token,
        'refresh_token': credentials.refresh_token,
        'token_uri': credentials.token_uri,
        'client_id': credentials.client_id,
        'client_secret': credentials.client_secret,
        'scopes': credentials.scopes
    }


# Конвертация dict в credentials
def credentials_from_dict(data):
    return credentials.Credentials(**data)

telegram_bot = None
# Telegram Bot
@app.route('/telegram_webhook', methods=['POST'])
async def telegram_webhook():
    global telegram_bot
    if telegram_bot is None:
        telegram_bot = TelegramBot(os.environ.get('TELEGRAM_TOKEN'))

    try:
        data = request.get_json()
        if not data:
            logging.warning("No data received from Telegram webhook.")
            return {"status": "ok"}
        await telegram_bot.handle_update(data)
        logging.info("Telegram update processed successfully.")
        return {"status": "ok"}

    except Exception as e:
        logging.error(f"Error processing Telegram webhook: {e}")
        return {"status": "error", "message": str(e)}


if __name__ == '__main__':
    app_context = app.app_context()
    app_context.push()
    try:
      db.create_all()
    except Exception as e:
      logging.error(f"Error on db.create_all: {e}")
    finally:
      app_context.pop()
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
