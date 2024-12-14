import logging
from flask import Flask, request, jsonify, render_template
from database import init_db, get_db, close_connection
import threading
from bot import main as bot_main  # Импорт функции main из файла bot.py

# Настройка логирования
logging.basicConfig(
    filename='app.log',
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s]: %(message)s'
)

app = Flask(__name__)

# Инициализируем базу данных сразу при запуске приложения
with app.app_context():
    init_db()

@app.teardown_appcontext
def teardown(exception):
    close_connection(exception)

@app.route('/')
def home():
    logging.info("Home endpoint accessed")
    return "Database is ready!"

@app.route('/add_food', methods=['POST'])
def add_food():
    try:
        data = request.get_json()
        logging.info(f"Received data for /add_food: {data}")
        user_id = data.get('user_id')
        food_name = data.get('food_name')
        calories = data.get('calories')
        date = data.get('date')

        if not all([user_id, food_name, calories, date]):
            logging.warning("Missing fields in /add_food request")
            return jsonify({"error": "All fields are required."}), 400

        user_id = int(user_id)
        if user_id <= 0:
            raise ValueError("User ID must be a positive integer.")

        db = get_db()
        cursor = db.cursor()
        cursor.execute('''
            INSERT INTO nutrition (user_id, food_name, calories, date)
            VALUES (?, ?, ?, ?)
        ''', (user_id, food_name, calories, date))
        db.commit()

        logging.info("Successfully added food entry to the database")
        return jsonify({"message": "Food entry added successfully."}), 201
    except ValueError as ve:
        logging.error(str(ve))
        return jsonify({"error": str(ve)}), 400
    except Exception as e:
        logging.error(str(e))
        return jsonify({"error": "An error occurred while adding food."}), 500

@app.route('/get_food', methods=['GET'])
def get_food():
    try:
        user_id = request.args.get('user_id')
        logging.info(f"Fetching food entries for user_id: {user_id}")

        if not user_id:
            return jsonify({"error": "User ID is required."}), 400

        user_id = int(user_id)
        if user_id <= 0:
            raise ValueError("User ID must be a positive integer.")

        db = get_db()
        cursor = db.cursor()
        cursor.execute('''
            SELECT * FROM nutrition WHERE user_id = ?
        ''', (user_id,))
        rows = cursor.fetchall()

        if not rows:
            logging.info(f"No food entries found for user_id: {user_id}")
            return '', 204  # HTTP 204 No Content

        food_entries = [dict(row) for row in rows]
        return jsonify(food_entries), 200
    except ValueError as ve:
        logging.error(str(ve))
        return jsonify({"error": str(ve)}), 400
    except Exception as e:
        logging.error(str(e))
        return jsonify({"error": "An error occurred while retrieving food data."}), 500

@app.route('/dashboard', methods=['GET'])
def dashboard():
    try:
        user_id = request.args.get('user_id')
        if not user_id:
            return jsonify({"error": "User ID is required."}), 400

        user_id = int(user_id)
        if user_id <= 0:
            raise ValueError("User ID must be a positive integer.")

        db = get_db()
        cursor = db.cursor()

        # Получаем статистику за последние 7 дней
        cursor.execute('''
            SELECT SUM(calories) as total_calories, date
            FROM nutrition
            WHERE user_id = ?
            GROUP BY date
            ORDER BY date DESC
            LIMIT 7
        ''', (user_id,))
        nutrition_stats = cursor.fetchall()

        if not nutrition_stats:
            logging.info(f"No data found for dashboard, user_id: {user_id}")
            return "No data available for the dashboard", 200

        # Преобразуем данные для графика
        stats = {
            "dates": [row['date'] for row in nutrition_stats],
            "calories": [row['total_calories'] for row in nutrition_stats]
        }

        # Вычисляем среднее
        average_calories = sum(stats["calories"]) / len(stats["calories"])
        stats["average_calories"] = round(average_calories, 2)

        return render_template('dashboard.html', stats=stats, user_id=user_id)
    except ValueError as ve:
        logging.error(f"ValueError occurred: {ve}")
        return jsonify({"error": str(ve)}), 400
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        return jsonify({"error": "An unexpected error occurred. Please try again later."}), 500

if __name__ == '__main__':
    # Запускаем Telegram-бота в отдельном потоке
    threading.Thread(target=bot_main, daemon=True).start()

    # Запускаем Flask-приложение
    logging.info("Starting the Flask application with bot integration")
    app.run(host='0.0.0.0', port=5000)
