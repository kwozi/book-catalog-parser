import sqlite3
import subprocess
import threading
from flask import Flask, render_template, jsonify, request

app = Flask(__name__)

DATABASE = 'books.db'
SECRET_TOKEN = "my_secret_webhook_token_123"

# ------------------------------------------------------------
# Работа с базой данных
# ------------------------------------------------------------
def get_db_connection():
    """Возвращает соединение с SQLite, если БД существует, иначе None."""
    try:
        conn = sqlite3.connect(DATABASE)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error:
        return None

def get_all_books():
    """Возвращает все книги из БД. Если БД нет — пустой список."""
    conn = get_db_connection()
    if conn is None:
        return []
    try:
        books = conn.execute('''
            SELECT id, title, price, stock, rating, category, upc, reviews
            FROM books
            ORDER BY title
        ''').fetchall()
        return books
    except sqlite3.Error:
        return []
    finally:
        conn.close()

def get_unique_categories():
    """Возвращает отсортированный список уникальных категорий."""
    conn = get_db_connection()
    if conn is None:
        return []
    try:
        categories = conn.execute('SELECT DISTINCT category FROM books ORDER BY category').fetchall()
        return [cat['category'] for cat in categories if cat['category']]
    except sqlite3.Error:
        return []
    finally:
        conn.close()

# ------------------------------------------------------------
# Фоновый запуск парсера
# ------------------------------------------------------------
def run_parser_background():
    """Запускает скрипт парсера books_scraper.py с флагом --db-only."""
    print("[INFO] Запуск парсера в фоновом режиме...")
    try:
        # Запускаем парсер, предполагаем что файл books_scraper.py лежит рядом
        result = subprocess.run(
            ['python', 'books_scraper.py', '--db-only'],
            capture_output=True,
            text=True,
            timeout=600  # 10 минут на выполнение
        )
        if result.returncode == 0:
            print("[INFO] Парсер успешно завершён.")
            print(result.stdout)
        else:
            print("[ERROR] Парсер завершился с ошибкой.")
            print(result.stderr)
    except Exception as e:
        print(f"[ERROR] Исключение при запуске парсера: {e}")

# ------------------------------------------------------------
# Маршруты Flask
# ------------------------------------------------------------
@app.route('/')
def index():
    """Главная страница с таблицей книг."""
    books = get_all_books()
    categories = get_unique_categories()
    return render_template('index.html', books=books, categories=categories)

@app.route('/api/books')
def api_books():
    """API-эндпоинт, возвращающий JSON со всеми книгами."""
    books = get_all_books()
    books_list = [dict(book) for book in books]
    return jsonify(books_list)

@app.route('/run-parser', methods=['POST'])
def run_parser():
    """Webhook для запуска парсера в фоне."""
    data = request.get_json(silent=True)
    if not data or data.get('secret_token') != SECRET_TOKEN:
        return jsonify({'status': 'error', 'message': 'Forbidden'}), 403

    # Запускаем парсер в отдельном потоке, чтобы не блокировать ответ
    thread = threading.Thread(target=run_parser_background)
    thread.start()

    return jsonify({'status': 'started', 'message': 'Parser started in background'})

# ------------------------------------------------------------
# Запуск приложения
# ------------------------------------------------------------
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
