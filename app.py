from flask import Flask, request, jsonify
from database import init_db, get_db, close_connection

app = Flask(__name__)

@app.before_first_request
def setup_database():
    init_db()

@app.teardown_appcontext
def teardown(exception):
    close_connection(exception)

@app.route('/')
def home():
    return "Database is ready!"

@app.route('/add_food', methods=['POST'])
def add_food():
    data = request.get_json()
    user_id = data.get('user_id')
    food_name = data.get('food_name')
    calories = data.get('calories')
    date = data.get('date')

    if not all([user_id, food_name, calories, date]):
        return jsonify({"error": "All fields are required."}), 400

    db = get_db()
    cursor = db.cursor()
    cursor.execute('''
        INSERT INTO nutrition (user_id, food_name, calories, date)
        VALUES (?, ?, ?, ?)
    ''', (user_id, food_name, calories, date))
    db.commit()

    return jsonify({"message": "Food entry added successfully."}), 201

@app.route('/get_food', methods=['GET'])
def get_food():
    user_id = request.args.get('user_id')
    
    if not user_id:
        return jsonify({"error": "User ID is required."}), 400

    db = get_db()
    cursor = db.cursor()
    cursor.execute('''
        SELECT * FROM nutrition WHERE user_id = ?
    ''', (user_id,))
    rows = cursor.fetchall()

    food_entries = [dict(row) for row in rows]
    return jsonify(food_entries), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
from flask import Flask, request, jsonify
from database import init_db, get_db, close_connection

app = Flask(__name__)

@app.teardown_appcontext
def teardown(exception):
    close_connection(exception)

@app.route('/')
def home():
    return "Database is ready!"

@app.route('/add_food', methods=['POST'])
def add_food():
    data = request.get_json()
    user_id = data.get('user_id')
    food_name = data.get('food_name')
    calories = data.get('calories')
    date = data.get('date')

    if not all([user_id, food_name, calories, date]):
        return jsonify({"error": "All fields are required."}), 400

    db = get_db()
    cursor = db.cursor()
    cursor.execute('''
        INSERT INTO nutrition (user_id, food_name, calories, date)
        VALUES (?, ?, ?, ?)
    ''', (user_id, food_name, calories, date))
    db.commit()

    return jsonify({"message": "Food entry added successfully."}), 201

# Новый эндпоинт для получения данных о питании
@app.route('/get_food', methods=['GET'])
def get_food():
    user_id = request.args.get('user_id')
    
    if not user_id:
        return jsonify({"error": "User ID is required."}), 400

    db = get_db()
    cursor = db.cursor()
    cursor.execute('''
        SELECT * FROM nutrition WHERE user_id = ?
    ''', (user_id,))
    rows = cursor.fetchall()

    food_entries = [dict(row) for row in rows]
    return jsonify(food_entries), 200

if __name__ == '__main__':
    with app.app_context():
        init_db()
    app.run(host='0.0.0.0', port=5000)
