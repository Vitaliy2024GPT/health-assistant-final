import os
import sys
import logging
from flask import Flask, request, jsonify
from telegram import Update
from telegram.ext import Updater, CommandHandler
from database import init_db, close_connection, add_user, get_user_by_chat_id, add_meal, get_user_meals, get_meals_last_7_days, get_calories_last_7_days
from datetime import date
import redis

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Инициализируем базу данных при старте приложения
with app.app_context():
    init_db()

# Регистрируем функцию для закрытия соединения с БД после обработки запроса
app.teardown_appcontext(close_connection)

# Подключение к Redis
redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
redis_client = redis.StrictRedis.from_url(redis_url, decode_responses=True)

# Telegram токен из переменных окружения
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

if not TELEGRAM_TOKEN:
    logger.error("TELEGRAM_TOKEN not set")
    sys.exit(1)

# Инициализация Telegram бота
updater = Updater(token=TELEGRAM_TOKEN, use_context=True)
dispatcher = updater.dispatcher

# Функции работы с Redis
def save_temp_data(key, value, ttl=3600):
    """Сохранение временных данных в Redis."""
    redis_client.set(key, value, ex=ttl)

def get_temp_data(key):
    """Получение временных данных из Redis."""
    return redis_client.get(key)

# Обработчики Telegram команд
def start(update, context):
    update.message.reply_text(
        "Welcome to Health Assistant Bot!\n"
        "Use /register <name> to create an account.\n"
        "Then /addmeal <food> <calories> to log meals.\n"
        "Use /meals to see all meals.\n"
        "/report to see weekly calories stats.\n"
        "/diet_advice for a simple diet tip!"
    )

def register_command(update, context):
    if len(context.args) < 1:
        update.message.reply_text("Usage: /register <name>")
        return
    name = context.args[0]
    chat_id = update.message.chat_id

    user = get_user_by_chat_id(chat_id)
    if user:
        update.message.reply_text(f"You are already registered as {user['name']}.")
    else:
        user_id = add_user(name, chat_id)
        update.message.reply_text(f"User registered! ID: {user_id} for this chat.")

def addmeal_command(update, context):
    if len(context.args) < 2:
        update.message.reply_text("Usage: /addmeal food_name calories")
        return

    chat_id = update.message.chat_id
    user = get_user_by_chat_id(chat_id)
    if not user:
        update.message.reply_text("You are not registered. Use /register <name> first.")
        return

    food_name = context.args[0]
    try:
        calories = int(context.args[1])
    except ValueError:
        update.message.reply_text("Calories must be a number.")
        return

    today_str = date.today().isoformat()
    add_meal(user["id"], food_name, calories, today_str)
    update.message.reply_text(f"Meal added: {food_name}, {calories} kcal")

def meals_command(update, context):
    chat_id = update.message.chat_id
    user = get_user_by_chat_id(chat_id)
    if not user:
        update.message.reply_text("You are not registered. Use /register <name> first.")
        return

    meals = get_user_meals(user["id"])
    if not meals:
        update.message.reply_text("No meals found.")
    else:
        lines = [f"{m['date']}: {m['food_name']} - {m['calories']} kcal" for m in meals]
        update.message.reply_text("\n".join(lines))

def report_command(update, context):
    """
    Показывает суммарные калории за последние 7 дней и средние калории в день.
    """
    chat_id = update.message.chat_id
    user = get_user_by_chat_id(chat_id)
    if not user:
        update.message.reply_text("You are not registered. Use /register <name> first.")
        return

    total_cal = get_calories_last_7_days(user["id"])
    avg_cal = total_cal / 7.0
    update.message.reply_text(f"Last 7 days total: {total_cal} kcal\nAverage per day: {avg_cal:.2f} kcal")

def diet_advice_command(update, context):
    """
    Простой совет диетолога на основе среднего потребления калорий за последние 7 дней.
    """
    chat_id = update.message.chat_id
    user = get_user_by_chat_id(chat_id)
    if not user:
        update.message.reply_text("You are not registered. Use /register <name> first.")
        return

    meals_7_days = get_meals_last_7_days(user["id"])
    if not meals_7_days:
        update.message.reply_text("No recent meal data found to analyze. Add some meals first.")
        return

    total_cal = sum(m['calories'] for m in meals_7_days)
    avg_cal = total_cal / 7.0

    if avg_cal > 3000:
        advice = "You consume quite a lot of calories. Try reducing portion sizes or replacing sugary snacks with fruits."
    elif avg_cal < 1500:
        advice = "Your calorie intake is quite low. Consider adding more nutritious meals."
    else:
        advice = "Your average calorie intake seems moderate. Keep it balanced!"

    update.message.reply_text(f"Average daily calories (last 7 days): {avg_cal:.2f} kcal\nAdvice: {advice}")

# Добавляем обработчики команд
dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(CommandHandler("register", register_command))
dispatcher.add_handler(CommandHandler("addmeal", addmeal_command))
dispatcher.add_handler(CommandHandler("meals", meals_command))
dispatcher.add_handler(CommandHandler("report", report_command))
dispatcher.add_handler(CommandHandler("diet_advice", diet_advice_command))

@app.route("/telegram_webhook", methods=["POST"])
def telegram_webhook():
    try:
        data = request.get_json(force=True)
        logger.info(f"Webhook received data: {data}")
        update = Update.de_json(data, updater.bot)
        dispatcher.process_update(update)
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        logger.error(f"Error handling webhook: {e}")
        return jsonify({"error": "Failed to process webhook"}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    logger.info("Starting Flask application...")
    app.run(host="0.0.0.0", port=port)
