import os
import sys
import logging
from flask import Flask, request, jsonify
from telegram import Update
from telegram.ext import Updater, CommandHandler
from database import init_db, close_connection, add_user, get_user_by_email, add_meal, get_user_meals, link_user_chat, get_user_id_by_chat_id

# ====== Логирование ======
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Инициализируем базу данных
with app.app_context():
    init_db()

app.teardown_appcontext(close_connection)

@app.route("/")
def home():
    return "Welcome to the Health Assistant Bot API!"

@app.route("/status")
def status():
    return "Flask server is running!"

# ====== Telegram токен ======
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

if not TELEGRAM_TOKEN:
    logger.error("TELEGRAM_TOKEN not set")
    sys.exit(1)

# Инициализация бота
updater = Updater(token=TELEGRAM_TOKEN, use_context=True)
dispatcher = updater.dispatcher

def start(update, context):
    """Ответ на команду /start"""
    update.message.reply_text("Welcome to Health Assistant Bot!\nUse /register name email to create an account.")

def register_command(update, context):
    """
    /register name email
    Регистрирует нового пользователя и связывает его с текущим chat_id.
    """
    if len(context.args) < 2:
        update.message.reply_text("Usage: /register name email")
        return
    name = context.args[0]
    email = context.args[1]

    user = get_user_by_email(email)
    if user:
        # Пользователь уже есть, просто свяжем с этим чат_id, если не связаны
        user_id = user["id"]
        link_user_chat(user_id, update.message.chat_id)
        update.message.reply_text(f"User already existed. Linked this chat to user_id {user_id}.")
    else:
        # Создаём нового пользователя
        user_id = add_user(name, email)
        link_user_chat(user_id, update.message.chat_id)
        update.message.reply_text(f"User registered! ID: {user_id} linked to this chat.")

def addmeal_command(update, context):
    """
    /addmeal food_name calories
    Добавляет приём пищи для текущего пользователя (определяем по chat_id).
    """
    if len(context.args) < 2:
        update.message.reply_text("Usage: /addmeal food_name calories")
        return
    
    user_id = get_user_id_by_chat_id(update.message.chat_id)
    if not user_id:
        update.message.reply_text("You are not registered. Use /register name email first.")
        return

    food_name = context.args[0]
    try:
        calories = int(context.args[1])
    except ValueError:
        update.message.reply_text("Calories must be a number.")
        return

    from datetime import date
    today = date.today().isoformat()
    add_meal(user_id, food_name, calories, today)
    update.message.reply_text(f"Meal added: {food_name}, {calories} kcal")

def meals_command(update, context):
    """
    /meals
    Показывает все приёмы пищи для текущего пользователя.
    """
    user_id = get_user_id_by_chat_id(update.message.chat_id)
    if not user_id:
        update.message.reply_text("You are not registered. Use /register name email first.")
        return

    meals = get_user_meals(user_id)
    if not meals:
        update.message.reply_text("No meals found.")
    else:
        lines = [f"{m['date']}: {m['food_name']} - {m['calories']} kcal" for m in meals]
        update.message.reply_text("\n".join(lines))

# Добавляем обработчики команд
dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(CommandHandler("register", register_command))
dispatcher.add_handler(CommandHandler("addmeal", addmeal_command))
dispatcher.add_handler(CommandHandler("meals", meals_command))

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
