# app/keyboards.py

# Импортируем типы клавиатур и кнопок из aiogram
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

# Импортируем функцию получения списка услуг из базы данных
from app.db import get_services_list 

# Импортируем модуль db целиком, так как ниже используются и другие функции из app.db
from app import db

# ------------------------ Главное меню ------------------------

# Отдельная кнопка возврата в главное меню
HOME_BTN = KeyboardButton(text="🏠 Главное меню")

# Основные кнопки меню, которые пользователь видит внизу чата
MAIN_MENU = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Записаться")],
        [KeyboardButton(text="Мои записи")],
        [KeyboardButton(text="Расписание"), KeyboardButton(text="Услуги")],
        [KeyboardButton(text="Контакты"), KeyboardButton(text="FAQ")]
    ],
    resize_keyboard=True
)

# ------------------------ Подтверждение записи ------------------------

# Клавиатура подтверждения действия
# Используется, например, когда нужно спросить пользователя:
# "Подтвердить запись?"
CONFIRM_KB = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Да"), KeyboardButton(text="Нет")],
        [HOME_BTN]
    ],
    resize_keyboard=True
)

# ------------------------ Админ панель (Inline) ------------------------

# Inline-клавиатура для администратора
# В отличие от ReplyKeyboard, эти кнопки прикрепляются прямо к сообщению
ADMIN_KB = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="Все записи", callback_data="adm_show_bookings")],
        [InlineKeyboardButton(text="Список пользователей", callback_data="adm_show_users")]
    ]
)

# ------------------------ Кнопки для выбора времени ------------------------

async def time_kb(date_selected, master_id=None) -> InlineKeyboardMarkup:
    # Функция формирует inline-клавиатуру со свободными временными слотами
    # для выбранного мастера на указанную дату

    # Если мастер не выбран, возвращаем пустую inline-клавиатуру
    if not master_id:
        return InlineKeyboardMarkup(inline_keyboard=[])

    # Получаем номер дня недели:
    # 0 = понедельник, 6 = воскресенье
    day_of_week = date_selected.weekday()

    # Получаем расписание выбранного мастера на конкретный день недели
    schedule = await db.get_schedule(master_id, day_of_week)

    # Если расписания нет, значит мастер в этот день не работает
    # Возвращаем пустую клавиатуру
    if not schedule:
        return InlineKeyboardMarkup(inline_keyboard=[])

    # Берём начало и конец рабочего времени из первой записи расписания
    start = schedule[0]["start_time"]
    end = schedule[0]["end_time"]

    # Из строкового времени "10:00" берём только часы
    start_hour = int(start.split(":")[0])
    end_hour = int(end.split(":")[0])

    # Генерируем список временных слотов по часам
    # Например: ["10:00", "11:00", ..., "19:00"]
    slots = [f"{h:02d}:00" for h in range(start_hour, end_hour + 1)]

    # Получаем из БД уже занятые слоты на выбранную дату и мастера
    booked_slots = await db.get_booked_times(
        date_selected.strftime("%d.%m.%Y"),
        master_id
    )

    # Оставляем только свободные слоты
    available_slots = [s for s in slots if s not in booked_slots]

    # Сюда будем собирать готовую структуру клавиатуры
    inline_keyboard = []

    # Временная строка кнопок
    row = []

    # Проходим по всем свободным слотам
    for i, slot in enumerate(available_slots, 1):

        # Добавляем кнопку со временем
        row.append(
            InlineKeyboardButton(
                text=slot,
                callback_data=slot
            )
        )

        # Каждые 3 кнопки переносим в новую строку
        if i % 3 == 0:
            inline_keyboard.append(row)
            row = []

    # Если после цикла остались кнопки, добавляем последнюю строку
    if row:
        inline_keyboard.append(row)

    # Возвращаем готовую inline-клавиатуру
    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)

# ------------------------ Выбор услуг (динамическая клавиатура) ------------------------

async def services_kb() -> ReplyKeyboardMarkup:
    """
    Асинхронная клавиатура с услугами из БД.
    """

    # Получаем список услуг из базы данных
    services = await get_services_list()  # берём из БД

    # Если услуг нет, показываем заглушку
    if not services:
        services = ["Нет доступных услуг"]  # на случай пустой БД

    # Для каждой услуги создаём отдельную кнопку в своей строке
    keyboard = [[KeyboardButton(text=s)] for s in services]

    # Добавляем кнопку возврата в главное меню
    keyboard.append([KeyboardButton(text="🏠 Главное меню")])

    # Формируем объект клавиатуры
    kb = ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True
    )

    # Возвращаем готовую клавиатуру
    return kb