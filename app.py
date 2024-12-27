import os
import json
from google.oauth2 import service_account
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google.auth.exceptions import RefreshError
import logging

# === ЛОГИРОВАНИЕ ===
logger = logging.getLogger(__name__)

# === ФУНКЦИЯ ДЛЯ ПОДКЛЮЧЕНИЯ GOOGLE FIT ===
def google_fit_service():
    try:
        credentials_content = os.getenv("GOOGLE_CREDENTIALS")
        if not credentials_content:
            raise ValueError("Переменная GOOGLE_CREDENTIALS не установлена!")

        credentials_data = json.loads(credentials_content)
        credentials = service_account.Credentials.from_service_account_info(
            credentials_data, scopes=["https://www.googleapis.com/auth/fitness.activity.read"]
        )

        if credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())

        service = build("fitness", "v1", credentials=credentials)
        return service

    except RefreshError as e:
        logger.error("Ошибка при обновлении токена Google Fit: %s", e)
        return None
    except Exception as e:
        logger.error("Ошибка подключения к Google Fit: %s", e)
        return None


# === КОМАНДА GOOGLEAUTH ===
from telegram import Update
from telegram.ext import CallbackContext

def googleauth(update: Update, context: CallbackContext):
    auth_link = os.getenv("GOOGLE_AUTH_REDIRECT")
    if not auth_link:
        update.message.reply_text("Ссылка для авторизации Google не настроена. Обратитесь в поддержку.")
        return
    
    update.message.reply_text(
        f"Для авторизации в Google Fit, перейдите по ссылке:\n{auth_link}",
        parse_mode="Markdown"
    )


# === КОМАНДА GOOGLEFIT ===
def googlefit(update: Update, context: CallbackContext):
    service = google_fit_service()
    if not service:
        update.message.reply_text(
            "Не удалось подключиться к Google Fit. Проверьте авторизацию с помощью /googleauth."
        )
        return

    try:
        response = service.users().dataset().aggregate(
            userId="me",
            body={
                "aggregateBy": [{"dataTypeName": "com.google.step_count.delta"}],
                "bucketByTime": {"durationMillis": 86400000},
                "startTimeMillis": int((datetime.now() - timedelta(days=1)).timestamp() * 1000),
                "endTimeMillis": int(datetime.now().timestamp() * 1000),
            },
        ).execute()
        steps = response['bucket'][0]['dataset'][0]['point'][0]['value'][0]['intVal']
        update.message.reply_text(f"Вчера вы прошли {steps} шагов!")
    except Exception as e:
        logger.error(f"Ошибка при запросе данных из Google Fit: {e}")
        update.message.reply_text("Не удалось получить данные из Google Fit. Повторите попытку позже.")
