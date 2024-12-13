from flask import Flask, jsonify
from database import init_db, get_db

app = Flask(__name__)

@app.before_first_request
def setup():
    init_db()

@app.route('/')
def home():
    return jsonify({"message": "Health Assistant API is running!"})

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
