import requests
from bs4 import BeautifulSoup
import time
import sqlite3
import json
import re
import argparse
import sys
from typing import Optional, Dict, List

# Константы
BASE_URL = "https://books.toscrape.com/"
CATALOG_URL = "https://books.toscrape.com/catalogue/"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}
REQUEST_DELAY = 0.5
DB_NAME = "books.db"
JSON_NAME = "books_full.json"

# ------------------------------------------------------------
# Работа с базой данных SQLite
# ------------------------------------------------------------
def init_database(db_path: str = DB_NAME) -> None:
    """Создаёт таблицу books, если её нет."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            price TEXT,
            stock INTEGER,
            rating INTEGER,
            category TEXT,
            upc TEXT UNIQUE,
            reviews INTEGER,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()
    print(f"База данных инициализирована: {db_path}")

def save_to_database(books_data: List[Dict], db_path: str = DB_NAME) -> None:
    """
    Сохраняет список книг в SQLite.
    При конфликте по полю upc обновляет все поля кроме id.
    """
    if not books_data:
        print("Нет данных для сохранения в БД.")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    inserted_updated = 0

    for book in books_data:
        cursor.execute('''
            INSERT INTO books (title, price, stock, rating, category, upc, reviews, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(upc) DO UPDATE SET
                title = excluded.title,
                price = excluded.price,
                stock = excluded.stock,
                rating = excluded.rating,
                category = excluded.category,
                reviews = excluded.reviews,
                last_updated = CURRENT_TIMESTAMP
        ''', (
            book.get('title'),
            book.get('price'),
            book.get('stock'),
            book.get('rating'),
            book.get('category'),
            book.get('upc'),
            book.get('reviews')
        ))
        inserted_updated += cursor.rowcount  # rowcount может быть 1 или 2

    conn.commit()
    conn.close()
    print(f"В базу данных сохранено/обновлено записей: {len(books_data)}")

# ------------------------------------------------------------
# Вспомогательные функции HTTP
# ------------------------------------------------------------
def get_soup(url: str, retries: int = 3) -> Optional[BeautifulSoup]:
    for attempt in range(retries):
        try:
            response = requests.get(url, headers=HEADERS, timeout=10)
            response.raise_for_status()
            html = response.content.decode('utf-8', errors='replace')
            return BeautifulSoup(html, 'html.parser')
        except (requests.RequestException, UnicodeDecodeError) as e:
            print(f"Попытка {attempt + 1}/{retries} для {url} не удалась: {e}")
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
    print(f"Не удалось загрузить {url} после {retries} попыток.")
    return None

# ------------------------------------------------------------
# Парсинг детальной страницы книги
# ------------------------------------------------------------
def parse_book_page(book_url: str) -> Optional[Dict]:
    soup = get_soup(book_url)
    if not soup:
        return None

    # Название
    title_tag = soup.find('h1')
    title = title_tag.text.strip() if title_tag else 'Без названия'

    # Цена
    price_tag = soup.find('p', class_='price_color')
    price = price_tag.text.strip() if price_tag else '£0.00'

    # Наличие
    stock = 0
    stock_tag = soup.find('p', class_='instock availability')
    if stock_tag:
        match = re.search(r'\((\d+)\s+available\)', stock_tag.text.strip())
        if match:
            stock = int(match.group(1))

    # Рейтинг
    rating = 0
    rating_map = {'One': 1, 'Two': 2, 'Three': 3, 'Four': 4, 'Five': 5}
    rating_tag = soup.find('p', class_='star-rating')
    if rating_tag:
        for cls in rating_tag.get('class', []):
            if cls in rating_map:
                rating = rating_map[cls]
                break

    # Категория
    category = ''
    breadcrumb = soup.find('ul', class_='breadcrumb')
    if breadcrumb:
        links = breadcrumb.find_all('a')
        if len(links) >= 3:
            category = links[2].text.strip()

    # Таблица с UPC и отзывами
    upc = ''
    reviews = 0
    table = soup.find('table', class_='table-striped')
    if not table:
        table = soup.find('table', class_='table')

    if table:
        for row in table.find_all('tr'):
            th = row.find('th')
            td = row.find('td')
            if th and td:
                header_text = th.text.strip()
                cell_text = td.text.strip()
                if header_text == 'UPC':
                    upc = cell_text
                elif 'reviews' in header_text.lower():
                    match = re.search(r'\d+', cell_text)
                    if match:
                        reviews = int(match.group())

    if not upc:
        print(f"Пропущена книга без UPC: {title}")
        return None

    return {
        'title': title,
        'price': price,
        'stock': stock,
        'rating': rating,
        'category': category,
        'upc': upc,
        'reviews': reviews
    }

# ------------------------------------------------------------
# Парсинг страницы каталога
# ------------------------------------------------------------
def parse_catalog_page(page_url: str) -> tuple[List[Dict], Optional[str]]:
    soup = get_soup(page_url)
    if not soup:
        return [], None

    books_on_page = []
    articles = soup.find_all('article', class_='product_pod')

    for article in articles:
        link_tag = article.h3.a
        if not link_tag:
            continue
        relative_url = link_tag.get('href')
        if relative_url.startswith('catalogue/'):
            book_url = BASE_URL + relative_url
        else:
            book_url = CATALOG_URL + relative_url

        print(f"Обработка: {book_url}")
        book_data = parse_book_page(book_url)
        if book_data:
            books_on_page.append(book_data)

        time.sleep(REQUEST_DELAY)

    # Поиск ссылки на следующую страницу
    next_button = soup.find('li', class_='next')
    next_url = None
    if next_button:
        next_link = next_button.find('a')
        if next_link:
            next_href = next_link.get('href')
            if next_href.startswith('catalogue/'):
                next_url = BASE_URL + next_href
            else:
                next_url = CATALOG_URL + next_href

    return books_on_page, next_url

# ------------------------------------------------------------
# Основная функция
# ------------------------------------------------------------
def main(save_to_json: bool = True):
    # Инициализация базы данных
    init_database(DB_NAME)

    start_url = "https://books.toscrape.com/catalogue/page-1.html"
    current_url = start_url
    page_num = 1
    all_books = []

    while current_url:
        print(f"\n=== Парсинг страницы {page_num}: {current_url} ===")
        page_books, next_url = parse_catalog_page(current_url)
        print(f"Найдено книг на странице: {len(page_books)}")

        all_books.extend(page_books)

        current_url = next_url
        page_num += 1
        if current_url:
            time.sleep(REQUEST_DELAY)

    print(f"\nПарсинг завершён. Всего собрано книг: {len(all_books)}")

    # Сохранение в базу данных
    save_to_database(all_books, DB_NAME)

    # Сохранение в JSON (если не отключено)
    if save_to_json:
        with open(JSON_NAME, 'w', encoding='utf-8') as f:
            json.dump(all_books, f, indent=2, ensure_ascii=False)
        print(f"Данные сохранены в JSON: {JSON_NAME}")

    # Статистика из БД
    conn = sqlite3.connect(DB_NAME)
    total = conn.execute("SELECT COUNT(*) FROM books").fetchone()[0]
    conn.close()
    print(f"Всего книг в базе данных: {total}")

# ------------------------------------------------------------
# Точка входа с аргументами командной строки
# ------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Парсер книг с books.toscrape.com")
    parser.add_argument(
        '--db-only',
        action='store_true',
        help='Сохранять только в SQLite, без создания JSON файла'
    )
    args = parser.parse_args()

    # Если флаг --db-only установлен, JSON не сохраняется
    save_json = not args.db_only
    main(save_to_json=save_json)
