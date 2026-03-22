# app/utils.py

import logging
from datetime import datetime
from app import db

# ------------------------ Настройка логирования ------------------------
# Лог пишется:
# 1) в файл bot.log
# 2) в консоль (чтобы видеть в терминале / Render)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[
        logging.FileHandler("bot.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)

# основной логгер проекта
logger = logging.getLogger("barbershop_bot")


# ------------------------ Проверка ролей ------------------------

async def is_admin(user_id: int) -> bool:
    """
    Проверяет, является ли пользователь администратором.
    """
    user = await db.get_user(user_id)

    logger.info(f"Проверка admin прав | user_id={user_id}")

    return user and user.get("role") == "admin"


# ------------------------ Логирование действий ------------------------

def log_user_action(user_id: int, action: str):
    """
    Лог действий пользователя.
    """

    logger.info(f"USER {user_id}: {action}")


def log_admin_action(admin_id: int, action: str):
    """
    Лог действий администратора.
    """

    logger.warning(f"ADMIN {admin_id}: {action}")


# ------------------------ Вспомогательные функции ------------------------

def format_date(day: int, month: int, year: int) -> str:
    """
    Форматирует дату в строку ДД.ММ.ГГГГ
    """

    return f"{day:02}.{month:02}.{year}"


def parse_date(date_str: str):
    """
    Парсит дату из строки ДД.ММ.ГГГГ
    """

    try:
        day, month, year = map(int, date_str.split("."))
        return day, month, year

    except Exception as e:

        logger.error(f"Ошибка парсинга даты: {date_str}")

        return None