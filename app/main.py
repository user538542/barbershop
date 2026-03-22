# app/main.py

# Важно для Render
# В .env или настройках Render добавить:
# BOT_TOKEN=xxx
# WEBHOOK_URL=https://your-app.onrender.com

import os
import asyncio
from contextlib import asynccontextmanager
from dotenv import load_dotenv

from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher, types
from aiogram.fsm.storage.memory import MemoryStorage

from app.handlers import router as bot_router
from app.admin_panel import router as admin_router
from app import db
from app.utils import logger
from app.reminders import reminder_task

from uvicorn import Config, Server

# Загружаем переменные окружения из .env
load_dotenv()

# Получаем настройки
TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # например: https://your-app.onrender.com

# Проверка токена
if not TOKEN:
    raise ValueError("BOT_TOKEN не задан в .env")

# Определяем режим работы:
# если есть WEBHOOK_URL → webhook (Render)
# если нет → polling (локально)
USE_WEBHOOK = WEBHOOK_URL is not None

# Формируем путь webhook (Telegram будет слать сюда запросы)
WEBHOOK_PATH = f"/webhook/{TOKEN}"
WEBHOOK_FULL_URL = f"{WEBHOOK_URL}{WEBHOOK_PATH}" if WEBHOOK_URL else None

logger.info(f"Запуск бота... Режим: {'WEBHOOK' if USE_WEBHOOK else 'POLLING'}")

# ----------------- FastAPI -----------------
app = FastAPI()

# HTTP-роутеры (админка)
# bot_router НЕ подключаем сюда — он для Telegram
# app.include_router(bot_router)
app.include_router(admin_router)

# ----------------- Telegram бот -----------------
bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Подключаем Telegram-обработчики
dp.include_router(bot_router)

# ----------------- Безопасный запуск фоновой задачи -----------------
async def safe_reminder_task(bot: Bot):
    """
    Обёртка для фоновой задачи:
    ловит ошибки и пишет их в лог, чтобы они не терялись
    """
    try:
        await reminder_task(bot)
    except Exception as e:
        logger.exception(f"Ошибка в reminder_task: {e}")

# ----------------- FastAPI lifecycle -----------------
@asynccontextmanager
async def lifespan(app: FastAPI):

    # Подключение БД
    logger.info("Подключение к базе...")
    await db.database.connect()
    logger.info("База подключена")

    # Устанавливаем webhook (если включен)
    if USE_WEBHOOK:
        logger.info(f"Установка webhook: {WEBHOOK_FULL_URL}")
        await bot.set_webhook(WEBHOOK_FULL_URL)
    else:
        logger.info("Webhook НЕ используется (polling режим)")

    # Запуск фоновой задачи (безопасный)
    logger.info("Запуск напоминаний...")
    asyncio.create_task(safe_reminder_task(bot))

    yield  # приложение работает

    # Удаляем webhook при остановке (важно для чистоты)
    if USE_WEBHOOK:
        logger.info("Удаление webhook...")
        await bot.delete_webhook()

    # Отключаем БД
    await db.database.disconnect()
    logger.info("База отключена")

# Регистрируем lifecycle
app.router.lifespan_context = lifespan

# ----------------- Webhook endpoint -----------------
@app.post(WEBHOOK_PATH)
async def bot_webhook(request: Request):

    # Получаем update от Telegram
    data = await request.json()

    logger.info("Получен update от Telegram")

    # Преобразуем в объект aiogram
    update = types.Update.model_validate(data, context={"bot": bot})

    # Передаем в обработчик
    await dp.feed_update(bot, update)

    return {"ok": True}

# ----------------- Проверка работы сервера -----------------
@app.get("/")
async def root():
    return {
        "status": "bot is running",
        "mode": "webhook" if USE_WEBHOOK else "polling"
    }

# ----------------- Запуск -----------------
async def main():

    config = Config(
        app=app,
        host="0.0.0.0",  # важно для Render!
        port=int(os.getenv("PORT", 8000)),
        log_level="info"
    )

    server = Server(config)

    if USE_WEBHOOK:
        # В режиме webhook запускаем ТОЛЬКО FastAPI
        logger.info("Запуск через WEBHOOK (только сервер)")
        await server.serve()
    else:
        # В режиме polling запускаем и бота, и сервер
        logger.info("Запуск через POLLING (бот + сервер)")
        await asyncio.gather(
            dp.start_polling(bot),
            server.serve()
        )

# Точка входа
if __name__ == "__main__":

    # Инициализация БД
    db.init_db()

    # Запуск
    asyncio.run(main())