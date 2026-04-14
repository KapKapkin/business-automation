# business-automation

Flask-приложение с MySQL, задеплоенное через Docker Compose. Включает полный CI/CD pipeline на GitHub Actions: линтинг → тесты → сборка образа → деплой на сервер. Для каждого Pull Request автоматически поднимается изолированный preview-стенд.

---

## Структура проекта

```
business-automation/
├── app/                        # Пакет Flask-приложения
│   ├── __init__.py             # Фабрика create_app()
│   ├── config.py               # Конфиги Development/Production
│   ├── extensions.py           # SQLAlchemy и Flask-Migrate
│   ├── api/
│   │   ├── __init__.py         # Blueprint api_bp
│   │   └── routes.py           # Эндпоинты API
│   └── models/
│       └── __init__.py         # Реэкспорт db для миграций
├── tests/
│   ├── conftest.py             # Pytest-фикстуры (app, client)
│   └── test_health.py          # Тест GET /api/health
├── nginx/
│   └── nginx.conf              # Reverse proxy: /python/ → flask:5000
├── .github/
│   ├── CODEOWNERS              # Все изменения требуют approve @KapKapkin
│   └── workflows/
│       ├── deploy.yml          # CI/CD: lint → test → build → deploy (push в main)
│       ├── preview-deploy.yml  # Поднять preview-стенд (открытие/обновление PR)
│       └── preview-cleanup.yml # Уничтожить preview-стенд (закрытие PR)
├── Dockerfile                  # Python 3.12-slim, gunicorn, 2 воркера
├── docker-compose.yml          # Production: flask + MySQL + сети
├── docker-compose.preview.yml  # Preview: flask + MySQL, порт 9000+PR_NUMBER
├── deploy.sh                   # Ручной деплой (сборка + запуск через docker compose)
├── run.py                      # Точка входа WSGI-приложения
├── requirements.txt            # Production-зависимости
├── requirements-dev.txt        # Dev-зависимости (pytest, ruff)
└── ruff.toml                   # Настройки линтера (E, F, W, I; Python 3.12)
```

---

## Описание файлов

### `app/__init__.py` — фабрика приложения
Функция `create_app(config_name)` создаёт экземпляр Flask, подключает конфиг из `config_by_name`, инициализирует `db` и `migrate`, регистрирует Blueprint `/api`.

### `app/config.py` — конфигурация
`BaseConfig` читает переменные окружения (`SECRET_KEY`, `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`) и собирает `SQLALCHEMY_DATABASE_URI` для MySQL через PyMySQL. `DevelopmentConfig` включает `DEBUG=True`, `ProductionConfig` — выключает.

### `app/extensions.py` — расширения Flask
Единственное место, где создаются объекты `SQLAlchemy()` и `Migrate()`. Они инициализируются без `app`, чтобы не возникало циклических импортов — привязка к приложению происходит в `create_app()`.

### `app/api/__init__.py` — Blueprint
Регистрирует Blueprint `api_bp` и импортирует `routes`, чтобы декораторы маршрутов сработали.

### `app/api/routes.py` — маршруты
Содержит эндпоинты API. Сейчас единственный маршрут — `GET /api/health`, возвращает `{"status": "ok"}`.

### `app/models/__init__.py` — модели
Реэкспортирует `db` (`from .extensions import db as db`), чтобы Flask-Migrate автоматически обнаруживал все модели при генерации миграций.

### `run.py` — точка входа
Создаёт приложение через `create_app()`, используя `FLASK_ENV` из окружения. Используется gunicorn: `gunicorn run:app`.

### `tests/conftest.py` — фикстуры
Фикстура `app` создаёт приложение с конфигом `development`, переключает его на `sqlite:///:memory:` и `TESTING=True`. Фикстура `client` возвращает тестовый HTTP-клиент.

### `Dockerfile`
Базовый образ `python:3.12-slim`. Копирует `requirements.txt`, устанавливает зависимости, копирует код. Запускает `gunicorn` с 2 воркерами на порту 5000.

### `docker-compose.yml`
- **flask** — контейнер приложения, берёт образ из `$FLASK_IMAGE` (или собирает локально), подключается к сетям `ba-network` (внутренняя с MySQL) и `app-network` (внешняя, общая с Nginx).
- **db** — MySQL 9.1, данные хранятся в volume `ba_db_data`.

### `docker-compose.preview.yml`
Аналог `docker-compose.yml` для PR-стендов. Всегда собирает образ локально (`build: .`), порт — `9000 + PR_NUMBER`, все контейнеры и volume изолированы по номеру PR.

### `nginx/nginx.conf`
Слушает порт 8080. Проксирует запросы с префиксом `/python/` на `flask:5000/`, передаёт заголовки `X-Real-IP`, `X-Forwarded-For`, `X-Forwarded-Proto`.

### `deploy.sh`
Ручной деплой: проверяет наличие Docker и Compose, создаёт `.env` из `.env.example` если нет, собирает образы и запускает `docker compose up -d`.

### `.github/workflows/deploy.yml` — production CI/CD
Запускается при push в `main`. Четыре последовательных job:
1. **lint** — `ruff check .`
2. **test** — `pytest tests/ -v --cov=app`
3. **build** — собирает Docker-образ, пушит в GHCR с тегами `sha-<commit>` и `latest`
4. **deploy** — по SSH: `git pull`, записывает `.env`, логинится в GHCR, `docker compose pull flask && docker compose up -d --no-build`

### `.github/workflows/preview-deploy.yml` — preview-стенды
Запускается при открытии/обновлении Pull Request. По SSH клонирует ветку PR в `/home/oz-admin/ba-previews/prN`, генерирует `.env`, запускает `docker compose -f docker-compose.preview.yml up -d --build`. Добавляет комментарий к PR со ссылкой на стенд.

### `.github/workflows/preview-cleanup.yml` — очистка стендов
Запускается при закрытии PR. По SSH делает `docker compose down -v --remove-orphans` и удаляет папку стенда.

---

## Локальный запуск

```bash
cp .env.example .env
# Отредактируйте .env при необходимости

docker compose up -d --build
# Приложение: http://localhost:8080/python/api/health
```

Или без Docker:

```bash
pip install -r requirements-dev.txt
export FLASK_ENV=development
# Потребуется локально запущенный MySQL
python run.py
```

---

## GitHub Actions: необходимые секреты

| Секрет | Описание |
|---|---|
| `SERVER_HOST` | IP или домен продакшн-сервера |
| `SERVER_USER` | SSH-пользователь (например, `oz-admin`) |
| `SSH_PRIVATE_KEY` | Приватный SSH-ключ для подключения к серверу |
| `BA_SECRET_KEY` | `SECRET_KEY` для Flask |
| `BA_DB_NAME` | Имя базы данных |
| `BA_DB_USER` | Пользователь MySQL |
| `BA_DB_PASSWORD` | Пароль MySQL |

`GITHUB_TOKEN` предоставляется автоматически.

---

## Добавление нового функционала

### 1. Новый эндпоинт

Добавьте маршрут в `app/api/routes.py`:

```python
@api_bp.get("/items")
def get_items():
    return jsonify([])
```

Напишите тест в `tests/`:

```python
def test_get_items(client):
    response = client.get("/api/items")
    assert response.status_code == 200
```

### 2. Новая модель базы данных

Создайте файл `app/models/item.py`:

```python
from ..extensions import db

class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
```

Импортируйте модель в `app/models/__init__.py`, чтобы Flask-Migrate её увидел:

```python
from .extensions import db as db
from .item import Item  # noqa: F401
```

Сгенерируйте миграцию локально:

```bash
flask db migrate -m "add item table"
flask db upgrade
```

### 3. Новый Blueprint (группа маршрутов)

Создайте пакет `app/items/`:

```
app/items/__init__.py   # Blueprint items_bp
app/items/routes.py     # Маршруты
```

Зарегистрируйте Blueprint в `app/__init__.py`:

```python
from .items import items_bp
app.register_blueprint(items_bp, url_prefix="/api/items")
```

### 4. Процесс разработки через PR

1. Создайте ветку: `git checkout -b feature/my-feature`
2. Внесите изменения, напишите тесты
3. Откройте Pull Request — GitHub Actions автоматически поднимет preview-стенд на `http://SERVER_HOST:9000+PR_NUMBER`
4. После approve от `@KapKapkin` и merge в `main` — автоматически запустится деплой в production

---

## Переменные окружения

| Переменная | По умолчанию | Описание |
|---|---|---|
| `FLASK_ENV` | `development` | Режим запуска (`development` / `production`) |
| `SECRET_KEY` | `change-me-in-production` | Секретный ключ Flask |
| `DB_HOST` | `db` | Хост MySQL |
| `DB_PORT` | `3306` | Порт MySQL |
| `DB_NAME` | `business_automation_db` | Имя базы |
| `DB_USER` | `root` | Пользователь MySQL |
| `DB_PASSWORD` | _(пусто)_ | Пароль MySQL |
