# app/config.py

import os
from dotenv import load_dotenv

# ------------------------ Загрузка .env ------------------------
load_dotenv()

# ------------------------ Telegram Bot ------------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")           # токен бота
WEBHOOK_URL = os.getenv("WEBHOOK_URL")       # url вебхука (если используется)
USE_WEBHOOK = WEBHOOK_URL is not None        # флаг использования webhook
WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"       # путь для FastAPI

# ------------------------ База данных ------------------------
# URL базы данных. Пример для SQLite:
# "sqlite+aiosqlite:///./barbershop.db"
# Для MySQL: "mysql+aiomysql://user:pass@host/dbname"
# Для PostgreSQL: "postgresql+asyncpg://user:pass@host/dbname"
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./barbershop.db")

# ------------------------ Прочие настройки ------------------------
DEFAULT_USER_ROLE = "user"
DEFAULT_ADMIN_ROLE = "admin"

# Настройки логирования
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")