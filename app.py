from googleapiclient.discovery import build
import googleapiclient.discovery_cache

# Отключаем file_cache
googleapiclient.discovery_cache = None

def google_fit_service():
    try:
        credentials_json = os.getenv("GOOGLE_CREDENTIALS")
        if not credentials_json:
            raise ValueError("GOOGLE_CREDENTIALS environment variable not set")
        credentials = service_account.Credentials.from_service_account_info(
            eval(credentials_json),
            scopes=["https://www.googleapis.com/auth/fitness.activity.read"]
        )
        # Инициализация сервиса без кэша
        service = build("fitness", "v1", credentials=credentials, cache_discovery=False)
        return service
    except Exception as e:
        logger.error(f"Failed to connect to Google Fit API: {e}")
        return None
