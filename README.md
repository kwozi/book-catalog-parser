# Book Catalog Parser

Демонстрационный проект для вакансии Python-разработчика (автоматизация / трек Python).

## 🚀 Что умеет проект

- **Парсер** (`book_parser.py`) собирает данные о 1000 книгах с [books.toscrape.com](https://books.toscrape.com): название, цена, наличие, рейтинг, категория, UPC.
- **База данных SQLite** – данные сохраняются в `books.db` с защитой от дубликатов (`INSERT OR REPLACE`).
- **Веб-интерфейс на Flask** (`app.py`) – просмотр каталога, поиск по названию, фильтры по категории, цене, рейтингу и наличию (JavaScript, без перезагрузки страницы).
- **Webhook** `/run-parser` – запуск парсера по HTTP-запросу с проверкой секретного токена (имитация интеграции между сервисами).

## 🛠 Технологии

- **Backend:** Python 3, Flask, SQLite3
- **Парсинг:** Requests, BeautifulSoup4
- **Frontend:** Bootstrap 5, чистый JavaScript
- **Инструменты:** Git, pip

## 📦 Запуск

1. Клонируйте репозиторий:
   ```bash
   git clone https://github.com/kwozi/book-catalog-parser.git
   cd book-catalog-parser
