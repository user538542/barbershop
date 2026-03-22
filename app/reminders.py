# app/reminders.py
import asyncio
from datetime import datetime, timedelta
from app import db
from app.utils import logger

# Интервал проверки будущих записей в секундах.
# 60 = проверка один раз в минуту
CHECK_INTERVAL = 60  # проверяем каждую минуту

async def reminder_task(bot):
    """
    Фоновая задача, которая проверяет будущие записи и отправляет напоминания
    за 24 часа и за 1 час до записи.
    """
    # Логируем запуск фоновой задачи
    logger.info("Запущена задача напоминаний о записях")

    # Бесконечный цикл:
    # задача постоянно работает, пока запущено приложение
    while True:
        try:
            # Текущие дата и время
            now = datetime.now()

            # Получаем из базы все будущие записи
            # Предполагается, что функция db.get_upcoming_bookings()
            # возвращает только те записи, дата/время которых больше текущего момента
            bookings = await db.get_upcoming_bookings()  # нужно сделать в db

            # Перебираем найденные записи
            for b in bookings:
                # Преобразуем строковые дату и время записи в объект datetime
                booking_time = datetime.strptime(f"{b['date']} {b['time']}", "%d.%m.%Y %H:%M")

                # Вычисляем, сколько времени осталось до записи
                delta = booking_time - now

                # Напоминание за 24 часа
                # Условие сделано с "окном" примерно в 1 минуту,
                # потому что задача запускается не каждую секунду, а раз в минуту
                if timedelta(hours=23, minutes=59) < delta <= timedelta(hours=24):
                    await bot.send_message(
                        b['user_id'],
                        f"📅 Напоминание: завтра у вас запись на {b['service']} в {b['time']} {b['date']}"
                    )

                    # Записываем в лог, что сообщение отправлено
                    logger.info(f"Отправлено 24h напоминание пользователю {b['user_id']}")

                # Напоминание за 1 час
                # Аналогично используется окно примерно в 1 минуту
                elif timedelta(minutes=59) < delta <= timedelta(hours=1):
                    await bot.send_message(
                        b['user_id'],
                        f"⏰ Напоминание: через 1 час у вас запись на {b['service']} в {b['time']} {b['date']}"
                    )

                    # Записываем в лог отправку напоминания
                    logger.info(f"Отправлено 1h напоминание пользователю {b['user_id']}")

        except Exception as e:
            # Ловим любые ошибки, чтобы фоновая задача не остановилась полностью
            # при первой же проблеме
            logger.error(f"Ошибка в задаче напоминаний: {e}")

        # Пауза перед следующей проверкой
        await asyncio.sleep(CHECK_INTERVAL)