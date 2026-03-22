# app/db.py
import sqlalchemy
from sqlalchemy import func
import databases
from typing import List, Dict, Optional
from datetime import datetime
import os
import asyncio
import random


# ------------------- Настройки -------------------
# URL подключения к базе данных.
# Если переменная окружения DATABASE_URL не задана,
# будет использоваться локальная SQLite-база barbershop.db
DB_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./barbershop.db")

# Асинхронное подключение к базе через библиотеку databases
database = databases.Database(DB_URL)

# Объект metadata хранит описание всех таблиц SQLAlchemy
metadata = sqlalchemy.MetaData()

# ------------------- Таблицы -------------------

# Пользователи
# Хранит данные пользователей Telegram-бота
users = sqlalchemy.Table(
    "users",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.BigInteger, primary_key=True),
    sqlalchemy.Column("username", sqlalchemy.String, nullable=True),
    sqlalchemy.Column("first_name", sqlalchemy.String, nullable=True),
    sqlalchemy.Column("last_name", sqlalchemy.String, nullable=True),
    sqlalchemy.Column("role", sqlalchemy.String, default="user")
)

# Услуги
# Справочник услуг барбершопа/салона
services = sqlalchemy.Table(
    "services",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True, autoincrement=True),
    sqlalchemy.Column("name", sqlalchemy.String(50), nullable=False, unique=True),
    sqlalchemy.Column("price", sqlalchemy.Integer, nullable=False)
)

# Мастера
# Таблица сотрудников, которые оказывают услуги
masters = sqlalchemy.Table(
    "masters",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True, autoincrement=True),
    sqlalchemy.Column("name", sqlalchemy.String, nullable=False),
    sqlalchemy.Column("specialty", sqlalchemy.String, nullable=True)
)

# Расписания мастеров
# Для каждого мастера задаются дни недели и рабочее время
schedules = sqlalchemy.Table(
    "schedules",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True, autoincrement=True),
    sqlalchemy.Column("master_id", sqlalchemy.Integer, sqlalchemy.ForeignKey("masters.id"), nullable=False),
    sqlalchemy.Column("day_of_week", sqlalchemy.Integer, nullable=False),  # 0=Пн, 6=Вс
    sqlalchemy.Column("start_time", sqlalchemy.String, nullable=False),
    sqlalchemy.Column("end_time", sqlalchemy.String, nullable=False)
)

# ------------------- Записи -------------------
# Таблица бронирований клиентов
bookings = sqlalchemy.Table(
    "bookings",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True, autoincrement=True),
    sqlalchemy.Column("user_id", sqlalchemy.BigInteger, 
                      sqlalchemy.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    sqlalchemy.Column("service", sqlalchemy.String(50), nullable=False),
    sqlalchemy.Column("date", sqlalchemy.String(20), nullable=False),
    sqlalchemy.Column("time", sqlalchemy.String(10), nullable=False),
    sqlalchemy.Column("master_id", sqlalchemy.Integer, 
                      sqlalchemy.ForeignKey("masters.id", ondelete="SET NULL"), nullable=True)
)

# ------------------- Инициализация -------------------
def init_db():
    """
    Создаёт таблицы и начальные данные, если их нет
    """

    # Для SQLite async URL заменяется на sync URL,
    # чтобы SQLAlchemy мог создать таблицы через create_engine
    if DB_URL.startswith("sqlite+aiosqlite"):
        db_url_sync = DB_URL.replace("sqlite+aiosqlite", "sqlite")
    else:
        db_url_sync = DB_URL

    # Создаём синхронный engine для инициализации структуры БД
    engine = sqlalchemy.create_engine(db_url_sync, connect_args={"check_same_thread": False})

    # Создаём таблицы, если они ещё не существуют
    metadata.create_all(engine)

    async def seed_data():
        # --- Услуги ---
        # Проверяем, есть ли уже записи в таблице services
        count_services = await database.fetch_one("SELECT COUNT(*) as count FROM services")
        if not count_services or count_services["count"] == 0:
            # Если таблица пустая — добавляем базовый набор услуг
            initial_services = [
                {"name": "Стрижка", "price": 2000},
                {"name": "Подравнивание кончиков", "price": 1000},
                {"name": "Окрашивание", "price": 4000},
                {"name": "Укладка", "price": 1100},
                {"name": "Модельная стрижка", "price": 3500},
                {"name": "Химическая завивка", "price": 2500},
            ]
            for s in initial_services:
                await database.execute(services.insert().values(**s))

        # --- Мастера ---
        # Проверяем, есть ли мастера
        count_masters = await database.fetch_one("SELECT COUNT(*) as count FROM masters")
        if not count_masters or count_masters["count"] == 0:
            # Если мастеров нет — добавляем стартовый список
            initial_masters = [
                {"name": "Ирина", "specialty": "Мастер широкого профиля"},
                {"name": "Светалана", "specialty": "Мастер широкого профиля"},
                {"name": "Ольга", "specialty": "Мастер широкого профиля"}
            ]
            for m in initial_masters:
                await database.execute(masters.insert().values(**m))

        # --- Расписания мастеров ---
        # Проверяем, заполнена ли таблица расписаний
        count_schedules = await database.fetch_one("SELECT COUNT(*) as count FROM schedules")
        if not count_schedules or count_schedules["count"] == 0:
            # Для всех мастеров создаём график: Пн-Пт, 10:00-19:00
            master_rows = await database.fetch_all("SELECT id FROM masters")
            for master in master_rows:
                for day in range(0, 5):  # Пн-Пт
                    await database.execute(
                        schedules.insert().values(
                            master_id=master["id"],
                            day_of_week=day,
                            start_time="10:00",
                            end_time="19:00"
                        )
                    )

        # --- Пользователи ---
        # Проверяем, есть ли пользователи
        count_users = await database.fetch_one("SELECT COUNT(*) as count FROM users")
        if not count_users or count_users["count"] == 0:
            # Генерируем тестовых пользователей
            first_names = ["Алексей","Иван","Пётр","Дмитрий","Никита","Мария","Елена","Ольга","Светлана","Ирина"]
            last_names = ["Иванов","Петров","Сидоров","Кузнецов","Смирнова","Попова","Козлова","Лебедева","Морозова","Соколова"]
            for i in range(10):
                user_id = 1000000000 + i  # условный Telegram user_id
                await database.execute(users.insert().values(
                    id=user_id,
                    username=f"user{i+1}",
                    first_name=first_names[i],
                    last_name=last_names[i],
                    role="user"
                ))

        # --- Записи на текущий год ---
        # Проверяем, есть ли бронирования
        count_bookings = await database.fetch_one("SELECT COUNT(*) as count FROM bookings")
        if not count_bookings or count_bookings["count"] == 0:
            # Получаем пользователей, мастеров и услуги
            user_rows = await database.fetch_all("SELECT id FROM users")
            master_rows = await database.fetch_all("SELECT id FROM masters")
            service_rows = await database.fetch_all("SELECT name FROM services")

            current_year = datetime.now().year

            # Для каждого пользователя создаём по 3 записи
            for user in user_rows:
                user_id = user["id"]

                # Для каждого пользователя 3 записи за год
                for month in range(1, 4):
                    day = random.randint(1, 28)
                    date_str = f"{day:02d}.{month:02d}.{current_year}"
                    time_str = f"{random.randint(10,18):02d}:00"

                    # Выбираем мастера случайным образом
                    master = random.choice(master_rows)
                    master_id = master["id"]

                    # Пример бизнес-логики:
                    # если user_id чётный — только "Стрижка",
                    # иначе любая случайная услуга
                    if user_id % 2 == 0:  # например, мужчины
                        service = "Стрижка"
                    else:
                        service = random.choice([s["name"] for s in service_rows])

                    # Сохраняем запись
                    await database.execute(bookings.insert().values(
                        user_id=user_id,
                        service=service,
                        date=date_str,
                        time=time_str,
                        master_id=master_id
                    ))

    # Запускаем асинхронное заполнение начальными данными
    asyncio.get_event_loop().run_until_complete(seed_data())

# ------------------- Пользователи -------------------
async def add_user(user_id: int, username: Optional[str] = None, 
                   first_name: Optional[str] = None,
                   last_name: Optional[str] = None, 
                   role: str = "user"):
    # Добавляет нового пользователя в таблицу users
    query = users.insert().values(id=user_id, 
                                  username=username, 
                                  first_name=first_name, 
                                  last_name=last_name, 
                                  role=role)
    await database.execute(query)

async def get_user(user_id: int) -> Optional[Dict]:
    # Возвращает одного пользователя по его id
    row = await database.fetch_one(users.select().where(users.c.id == user_id))
    return dict(row) if row else None

async def get_all_users() -> List[Dict]:
    # Возвращает список всех пользователей
    rows = await database.fetch_all(users.select())
    return [dict(r) for r in rows]

# ------------------- Услуги -------------------
async def get_services() -> List[Dict]:
    # Возвращает список услуг с id, названием и ценой
    query = "SELECT id, name, price FROM services ORDER BY name"
    rows = await database.fetch_all(query)
    return [dict(r) for r in rows]

# ------------------- Работа с услугами из БД -------------------

async def get_services_list() -> List[str]:
    """
    Возвращает список названий услуг
    """
    rows = await get_services()
    return [r['name'] for r in rows]

async def get_service_by_name(name: str) -> Optional[Dict]:
    """
    Возвращает одну услугу по названию
    """
    row = await database.fetch_one(services.select().where(services.c.name == name))
    return dict(row) if row else None

async def get_service_with_price(name: str) -> Optional[Dict]:
    """
    Возвращает словарь услуги с ценой
    """
    row = await get_service_by_name(name)
    return dict(row) if row else None

async def get_services_text() -> str:
    """
    Возвращает текст со списком услуг и цен для пользователя
    """
    rows = await get_services()
    text = "**Список услуг и цен:**\n\n"
    for s in rows:
        text += f"● {s['name']}: {s['price']}₽\n"
    return text

# ------------------- Мастера -------------------
async def get_masters() -> List[Dict]:
    # Возвращает список всех мастеров
    rows = await database.fetch_all(masters.select())
    return [dict(r) for r in rows]

async def get_master_by_id(master_id: int) -> Optional[Dict]:
    # Возвращает мастера по его id
    row = await database.fetch_one(masters.select().where(masters.c.id == master_id))
    return dict(row) if row else None

# ------------------- Расписание -------------------
async def get_schedule(master_id: int, day_of_week: int) -> List[Dict]:
    # Возвращает расписание конкретного мастера на конкретный день недели
    rows = await database.fetch_all(
        schedules.select().where(
            (schedules.c.master_id == master_id) & (schedules.c.day_of_week == day_of_week)
        )
    )
    return [dict(r) for r in rows]

async def get_schedules() -> List[Dict]:
    # Возвращает общее расписание всех мастеров
    # с преобразованием номера дня недели в текст
    query = """
                SELECT 
                    s.*,
                    m.name as master_name,
                    CASE s.day_of_week
                        WHEN 0 THEN 'Понедельник'
                        WHEN 1 THEN 'Вторник'
                        WHEN 2 THEN 'Среда'
                        WHEN 3 THEN 'Четверг'
                        WHEN 4 THEN 'Пятница'
                        WHEN 5 THEN 'Суббота'
                        WHEN 6 THEN 'Воскресенье'
                    END as day_name
                FROM schedules s
                LEFT JOIN masters m ON s.master_id=m.id
                ORDER BY master_name, day_of_week 
            """
    rows = await database.fetch_all(query)
    return [dict(r) for r in rows]

# ------------------- Расписание мастеров -------------------
async def get_schedules_text() -> str:
    """
    Возвращает текст с расписанием
    """
    rows = await get_schedules()
    text = "**Расписание:**\n\n"
    for s in rows:
        text += f"● {s['master_name']}: {s['day_name']} {s['start_time']} — {s['end_time']}\n"
    return text

# ------------------- Бронирования -------------------
async def add_booking(user_id: int, service: str, date: str, time: str, master_id: Optional[int] = None):
    # Проверяем, свободно ли выбранное время у конкретного мастера
    query = bookings.select().where((bookings.c.date == date) & (bookings.c.time == time) & (bookings.c.master_id == master_id))
    row = await database.fetch_one(query)

    # Если запись уже существует — выбрасываем исключение
    if row:
        raise ValueError(f"Слот {date} в {time} уже занят!")

    # Добавляем новую запись
    await database.execute(bookings.insert().values(user_id=user_id, service=service, date=date, time=time, master_id=master_id))

async def get_bookings(user_id: int) -> List[Dict]:
    # Возвращает все бронирования конкретного пользователя
    query = (
        bookings
        .join(masters, bookings.c.master_id == masters.c.id)
        .select()
        .where(bookings.c.user_id == user_id)
        .order_by(
            func.substr(bookings.c.date, 7, 4).asc(),  # год
            func.substr(bookings.c.date, 4, 2).asc(),  # месяц
            func.substr(bookings.c.date, 1, 2).asc(),  # день
            bookings.c.time.asc()                      # время
        )
    )
    rows = await database.fetch_all(query)
    return [dict(r) for r in rows]

async def get_bookings_stat() -> List[Dict]:
    # Возвращает статистику по записям:
    # год, месяц, мастер, количество записей
    query = """
    SELECT substr(b.date, 7, 4) AS yyyy, substr(b.date, 4, 2) AS mm, m.name, COUNT(*) AS quantity
    FROM bookings b
    LEFT JOIN masters m ON b.master_id = m.id
    GROUP BY 
    substr(b.date, 7, 4), substr(b.date, 4, 2), m.name;
    """
    rows = await database.fetch_all(query)
    return [dict(r) for r in rows]

async def get_all_bookings() -> List[Dict]:
    # Возвращает список всех бронирований с данными пользователя и мастера
    query = """
    SELECT 
        b.id, b.service, b.date, b.time, b.master_id, m.name,
        u.id as user_id, u.username, u.first_name, u.last_name
    FROM bookings b
    LEFT JOIN users u ON b.user_id = u.id
    LEFT JOIN masters m ON b.master_id = m.id
    ORDER BY 
    substr(b.date, 7, 4) ASC, substr(b.date, 4, 2) ASC, substr(b.date, 1, 2) ASC, 
    b.time ASC;
    """
    rows = await database.fetch_all(query)
    return [dict(r) for r in rows]

async def get_booking_by_id(booking_id: int):
    # Возвращает одно бронирование по его id
    return await database.fetch_one(bookings.select().where(bookings.c.id == booking_id))

async def delete_booking(booking_id: int):
    # Удаляет бронирование по id
    await database.execute(bookings.delete().where(bookings.c.id == booking_id))

async def get_upcoming_bookings() -> List[Dict]:
    # Возвращает только будущие записи
    rows = await database.fetch_all(bookings.select())
    now = datetime.now()
    upcoming = []

    for r in rows:
        # Преобразуем строковые дату и время в объект datetime
        booking_time = datetime.strptime(f"{r['date']} {r['time']}", "%d.%m.%Y %H:%M")

        # Если запись ещё не наступила — добавляем в список
        if booking_time > now:
            upcoming.append(r)

    return upcoming

async def get_booked_times(date: str, master_id: Optional[int] = None) -> List[str]:
    # Возвращает список занятых временных слотов на конкретную дату
    query = bookings.select().where(bookings.c.date == date)

    # Если указан мастер — фильтруем только по нему
    if master_id:
        query = query.where(bookings.c.master_id == master_id)

    rows = await database.fetch_all(query)
    return [r["time"] for r in rows]

async def get_booked_dates() -> List[str]:
    # Возвращает список всех дат, на которые уже есть записи
    rows = await database.fetch_all("SELECT DISTINCT date FROM bookings")
    return [row["date"] for row in rows]