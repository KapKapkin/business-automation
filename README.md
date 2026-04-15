# business-automation

Flask-приложение с MySQL, задеплоенное через Docker Compose. Включает полный CI/CD pipeline на GitHub Actions: линтинг → тесты → сборка образа → деплой на сервер. Для каждого Pull Request автоматически поднимается изолированный preview-стенд.

---

## Процесс разработки

1. Создайте ветку: `git checkout -b feature/my-feature` (вместо my-future лучше писать то, что было добавлено)
2. Внесите изменения, напишите тесты
3. Комментарий для коммита пишем следующим образом: сначала область изменений, к примеру вы добавили новую модель для учреждения, значит пишем "models: add Department model."
3. Откройте Pull Request — GitHub Actions автоматически:
   - запустит CI (lint → test → build)
   - поднимет preview-стенд и добавит комментарий с URL: `http://oz.mospolytech.ru/python/preview/prN/` (вместо prN будет что-то по типу pr1, pr2 и т.д.)
4. После прохождения CI и approve (после ревью кода) от `@KapKapkin` — merge в `main` запустит деплой в production

---

## Локальный запуск

```bash
cp .env.example .env
# Отредактируйте .env при необходимости, учетные данные могут отличаться

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

## Структура проекта

```
business-automation/
├── app/
│   ├── __init__.py             # Регистрация Blueprint-ов
│   ├── api/
│   │   └── routes.py           # Эндпоинты API
│   └── models/
│       ├── __init__.py         # Импорт моделей для Flask-Migrate
│       └── *.py                # Модели SQLAlchemy
└── tests/
    ├── conftest.py             # Pytest-фикстуры (app, client)
    └── test_*.py               # Тесты
```

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

## Настройка сервера для preview-стендов

nginx-proxy должен иметь volume-mount папки с конфигами и `include` в основном конфиге:

```yaml
# docker-compose.yml nginx-proxy
services:
  nginx-proxy:
    volumes:
      - /home/oz-admin/nginx-previews:/etc/nginx/conf.d/previews
```

```nginx
# nginx.conf внутри nginx-proxy
include /etc/nginx/conf.d/previews/*.conf;
```

```bash
mkdir -p /home/oz-admin/nginx-previews
docker compose up -d nginx-proxy
```

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

---

## Описание файлов

### `app/__init__.py` — регистрация Blueprint-ов
При добавлении нового Blueprint его нужно зарегистрировать здесь через `app.register_blueprint(...)`.

### `app/api/routes.py` — маршруты
Эндпоинты API. Сейчас единственный маршрут — `GET /api/health`, возвращает `{"status": "OK"}`.

### `app/models/__init__.py` — регистрация моделей
Все модели SQLAlchemy нужно импортировать в этом файле, чтобы Flask-Migrate их обнаруживал при генерации миграций.

### `tests/conftest.py` — фикстуры
Фикстура `app` создаёт приложение на `sqlite:///:memory:` с `TESTING=True`. Фикстура `client` возвращает тестовый HTTP-клиент.
