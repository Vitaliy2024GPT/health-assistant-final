import logging
from flask import Flask, request, jsonify
from database import init_db, get_db, close_connection

# Настройка логирования
logging.basicConfig(
    filename='app.log',
    level=logging.ERROR,
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
    return "Database is ready!"

@app.route('/add_food', methods=['POST'])
def add_food():
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        food_name = data.get('food_name')
        calories = data.get('calories')
        date = data.get('date')

        if not all([user_id, food_name, calories, date]):
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
            return jsonify({"message": "No food entries found for this user."}), 200

        food_entries = [dict(row) for row in rows]
        return jsonify(food_entries), 200
    except ValueError as ve:
        logging.error(str(ve))
        return jsonify({"error": str(ve)}), 400
    except Exception as e:
        logging.error(str(e))
        return jsonify({"error": "An error occurred while retrieving food data."}), 500

@app.route('/get_stats', methods=['GET'])
def get_stats():
    try:
        user_id = request.args.get('user_id')

        if not user_id:
            return jsonify({"error": "User ID is required."}), 400

        user_id = int(user_id)
        if user_id <= 0:
            raise ValueError("User ID must be a positive integer.")

        db = get_db()
        cursor = db.cursor()

        # Считаем общие калории за день
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
            return jsonify({"message": "No data available for the last week."}), 200

        # Считаем общее количество записей
        cursor.execute('SELECT COUNT(*) as total_entries FROM nutrition WHERE user_id = ?', (user_id,))
        total_entries = cursor.fetchone()["total_entries"]

        stats = {
            "total_entries": total_entries,
            "last_week_stats": [dict(row) for row in nutrition_stats]
        }

        return jsonify(stats), 200
    except ValueError as ve:
        logging.error(str(ve))
        return jsonify({"error": str(ve)}), 400
    except Exception as e:
        logging.error(str(e))
        return jsonify({"error": "An error occurred while retrieving statistics."}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
