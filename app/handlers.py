# app/handlers.py

# Импортируем классы для работы с датой:
# datetime — дата и время,
# date — только дата,
# timedelta — интервал времени
from datetime import datetime, date, timedelta

# Импортируем основные сущности aiogram:
# Router — роутер обработчиков,
# F — удобный фильтр по полям объекта,
# types — типы Telegram-объектов
from aiogram import Router, F, types

# Импортируем фильтр для обработки команд, например /start
from aiogram.filters import Command

# Импортируем типы входящих объектов и клавиатур
from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

# Контекст FSM нужен для хранения состояния пользователя
# между шагами записи
from aiogram.fsm.context import FSMContext

# State и StatesGroup нужны для описания шагов сценария записи
from aiogram.fsm.state import State, StatesGroup

# Импортируем модуль работы с базой данных
from app import db

# Импортируем готовые клавиатуры и функции генерации клавиатур
from app.keyboards import MAIN_MENU, services_kb, time_kb

# Импортируем логгер и функцию логирования действий пользователя
from app.utils import logger, log_user_action

# Импортируем календарь для выбора даты
from aiogram_calendar import SimpleCalendar, SimpleCalendarCallback

# Импортируем текст FAQ
from app.faq import get_faq_text

# Импортируем функции получения текстов услуг и расписания
from app.db import get_services_list, get_services_text, get_schedules_text

# Создаём роутер, к которому будут подключены все обработчики
router = Router()

# ---------------- FSM ----------------
# Описываем состояния конечного автомата записи:
# 1) выбор услуги
# 2) выбор мастера
# 3) выбор даты
# 4) выбор времени
# 5) подтверждение записи
class BookingStates(StatesGroup):
    choosing_service = State()
    choosing_master = State()
    choosing_date = State()
    choosing_time = State()
    confirming = State()

@router.message(Command("start"))
async def start_cmd(message: Message):
    # Получаем объект текущего Telegram-пользователя
    tg_user = message.from_user

    # Логируем запуск команды /start
    logger.info(f"/start | user={tg_user.id}")

    # Проверяем, есть ли пользователь в базе
    user = await db.get_user(tg_user.id)

    if not user:
        # Если пользователя нет в базе, добавляем его
        await db.add_user(
            user_id=tg_user.id,
            username=tg_user.username,
            first_name=tg_user.first_name,
            last_name=tg_user.last_name
        )

        # Логируем действие регистрации нового пользователя
        log_user_action(tg_user.id, "Зарегистрирован новый пользователь")

        # Берём имя и фамилию из Telegram-профиля
        first_name = tg_user.first_name
        last_name = tg_user.last_name
    else:
        # Если пользователь уже есть в базе,
        # получаем имя и фамилию из БД
        first_name = user.get("first_name")
        last_name = user.get("last_name")

    # Формируем полное имя, при этом защищаемся от None
    full_name = f"{first_name or ''} {last_name or ''}".strip()

    # Отправляем приветственное сообщение с главным меню
    await message.answer(
        f"Привет, {full_name}! Я бот парикмахерской ✂️",
        reply_markup=MAIN_MENU
    )

# ------------------------ Главное меню ------------------------
@router.message(lambda message: message.text == "🏠 Главное меню")
async def go_home(message: Message, state: FSMContext):
    # Очищаем текущее состояние FSM,
    # чтобы пользователь полностью вышел из сценария записи
    await state.clear()

    # Возвращаем пользователя в главное меню
    await message.answer(
        "Вы вернулись в главное меню.",
        reply_markup=MAIN_MENU
    )

# ------------------------ Список услуг ------------------------
@router.message(Command("services"))    
@router.message(F.text == "Услуги")
async def services_cmd(message: Message):
    # Получаем готовый текст со списком услуг и цен
    text = await get_services_text()

    # Отправляем его пользователю
    await message.answer(text, parse_mode="Markdown")

# ------------------------ Расписание ------------------------
@router.message(Command("schedule"))
@router.message(F.text == "Расписание")
async def schedules_cmd(message: Message):
    # Получаем текст с расписанием мастеров
    text = await get_schedules_text()

    # Отправляем пользователю
    await message.answer(text, parse_mode="Markdown")

# ------------------------ Контакты ------------------------
@router.message(Command("contacts"))
@router.message(F.text == "Контакты")
async def contacts_handler(message: Message):
    # Отправляем геолокацию заведения в формате venue:
    # пользователь увидит карту, название и адрес
    await message.bot.send_venue(
        chat_id=message.chat.id,
        latitude=54.18058,
        longitude=37.60427,
        title="Парикмахерская",
        address="пр. Ленина, 77, Тула, 300012"
    )

    # Формируем текст с контактной информацией
    text = (
        "📍 <b>Наш адрес:</b>\n"
        "пр. Ленина, 77, Тула, 300012\n\n"
        "📞 <b>Телефон:</b>\n"
        "+7(487)236-2774"
    )

    # Отправляем текст с адресом и телефоном
    await message.answer(text, parse_mode="HTML")

# ------------------------ Мои записи ------------------------
@router.message(F.text == "Мои записи")
async def mybookings_cmd(message: Message):
    # Логируем нажатие кнопки "Мои записи"
    logger.info(f"'Мои записи' pressed | user={message.from_user.id}")

    # Получаем все записи текущего пользователя
    bookings = await db.get_bookings(message.from_user.id)

    # Если записей нет — сообщаем об этом и завершаем обработку
    if not bookings:
        await message.answer("У вас пока нет записей.")
        return

    # Если записи есть — отправляем каждую отдельным сообщением
    for b in bookings:
        # Формируем текст карточки записи
        text = f"**{b['service']} ✂️**\n📅 Дата: {b['date']}\n⏰ Время: {b['time']}\n💇 Мастер: {b['name']}"

        # Добавляем inline-кнопку для отмены записи
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отменить запись", callback_data=f"cancel:{b['id']}")]
        ])

        # Отправляем информацию о записи
        await message.answer(text, reply_markup=kb, parse_mode="Markdown")

# ------------------------ Отмена записи ------------------------
@router.callback_query(F.data.startswith("cancel:"))
async def cancel_booking(callback: CallbackQuery):
    # Из callback_data извлекаем id записи
    booking_id = int(callback.data.split(":")[1])

    # Получаем запись из базы
    booking = await db.get_booking_by_id(booking_id)

    # Если запись не найдена — сообщаем пользователю
    if not booking:
        await callback.message.answer("❌ Запись не найдена.")
        await callback.answer()
        return

    # Удаляем запись из базы
    await db.delete_booking(booking_id)

    # Уведомляем пользователя об успешной отмене
    await callback.message.answer(
        f"✅ Ваша запись на {booking['service']} {booking['date']} в {booking['time']} отменена."
    )

    # Логируем отмену записи
    logger.info(f"Пользователь {callback.from_user.id} отменил запись id={booking_id}")

    # Закрываем "часики" на кнопке callback
    await callback.answer()

# ------------------------ Начало записи ------------------------
@router.message(F.text == "Записаться")
async def book_cmd(message: Message, state: FSMContext):
    # Логируем старт сценария записи
    logger.info(f"Начало записи | user={message.from_user.id}")

    # Генерируем клавиатуру со списком услуг
    kb = await services_kb()

    # Просим пользователя выбрать услугу
    await message.answer("Выберите услугу:", reply_markup=kb)

    # Переводим пользователя в состояние выбора услуги
    await state.set_state(BookingStates.choosing_service)

# ------------------------ Выбор услуги ------------------------
@router.message(BookingStates.choosing_service)
async def choose_service(message: Message, state: FSMContext):

    # Получаем актуальный список услуг из базы
    services = await get_services_list()

    # Проверяем, существует ли выбранная услуга
    if message.text not in services:
        await message.answer("Такой услуги нет, выберите из списка.")
        return

    # Сохраняем выбранную услугу в FSM
    await state.update_data(service=message.text)

    # ---------- выбор мастера ----------
    # Получаем список всех мастеров
    masters = await db.get_masters()

    # Формируем клавиатуру со списком мастеров
    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=m["name"])] for m in masters],
        resize_keyboard=True
    )

    # Просим пользователя выбрать мастера
    await message.answer("Выберите мастера:", reply_markup=kb)

    # Переходим к следующему состоянию
    await state.set_state(BookingStates.choosing_master)

# ------------------------ Выбор мастера ------------------------
@router.message(BookingStates.choosing_master)
async def choose_master(message: Message, state: FSMContext):
    # Получаем всех мастеров из базы
    masters = await db.get_masters()

    # Формируем список имён для проверки пользовательского ввода
    master_names = [m["name"] for m in masters]

    # Проверяем, что пользователь выбрал мастера из списка
    if message.text not in master_names:
        await message.answer("Выберите мастера из списка.")
        return

    # Ищем id выбранного мастера
    master_id = None
    for m in masters:
        if m["name"] == message.text:
            master_id = m["id"]

    # Сохраняем имя и id мастера в FSM
    await state.update_data(master=message.text, master_id=master_id)

    # Отправляем календарь для выбора даты
    await message.answer(
        "Выберите дату:",
        reply_markup=await SimpleCalendar().start_calendar()
    )

    # Обязательно переводим пользователя в состояние выбора даты
    await state.set_state(BookingStates.choosing_date)

# ------------------------ Выбор даты календаря ------------------------
@router.callback_query(SimpleCalendarCallback.filter(), BookingStates.choosing_date)
async def process_calendar(callback: CallbackQuery, callback_data: SimpleCalendarCallback, state: FSMContext):
    """
    Обработка календаря SimpleCalendar:
    - prev/next автоматически обновляются
    - выбор даты — проверяем на прошлое и max_date
    """
    # Текущая дата
    today = date.today()

    # Ограничиваем запись максимум на 60 дней вперёд
    max_date = today + timedelta(days=60)

    # process_selection обрабатывает кнопки календаря:
    # переключение месяцев и выбор даты
    selected, selected_date = await SimpleCalendar().process_selection(callback, callback_data)

    # Если дата действительно выбрана пользователем
    if selected:
        # selected_date может быть datetime, приводим к типу date
        selected_date = selected_date.date()

        # Проверка на прошлую дату
        if selected_date < today:
            await callback.answer("Нельзя выбрать прошлую дату!", show_alert=True)

            # Показываем календарь заново
            await callback.message.edit_text(
                "Выберите дату:",
                reply_markup=await SimpleCalendar().start_calendar()
            )
            return

        # Проверка на слишком далёкую дату
        if selected_date > max_date:
            await callback.answer("Нельзя выбрать дату позже чем через 2 месяца!", show_alert=True)

            # Показываем календарь заново
            await callback.message.edit_text(
                "Выберите дату:",
                reply_markup=await SimpleCalendar().start_calendar()
            )
            return

        # Сохраняем дату в FSM в строковом формате
        await state.update_data(date=selected_date.strftime("%d.%m.%Y"))

        # Получаем уже сохранённые данные пользователя
        data = await state.get_data()

        # Достаём id мастера
        master_id = data.get("master_id")

        # Формируем клавиатуру свободного времени
        kb = await time_kb(selected_date, master_id)

        # Если свободных слотов нет — просим выбрать другой день
        if not kb.inline_keyboard:
            await callback.message.answer("Все слоты на эту дату заняты. Выберите другой день.")
            
            # Показываем календарь заново
            await callback.message.edit_text(
                "Выберите дату:",
                reply_markup=await SimpleCalendar().start_calendar()
            )
            return

        # Показываем доступное время
        await callback.message.answer(
            "Теперь выберите время:",
            reply_markup=kb
        )

        # Переходим в состояние выбора времени
        await state.set_state(BookingStates.choosing_time)

    # Закрываем callback
    await callback.answer()

# ------------------------ Выбор времени ------------------------
@router.callback_query(BookingStates.choosing_time)
async def choose_time(callback: CallbackQuery, state: FSMContext):
    # Если по какой-то причине нажали на заблокированный слот
    if callback.data == "disabled":
        await callback.answer("Этот слот занят, выберите другой.", show_alert=True)
        return

    # Сохраняем выбранное время
    time_selected = callback.data
    await state.update_data(time=time_selected)

    # Получаем все накопленные данные FSM
    data = await state.get_data()
    service = data.get("service")
    master = data.get("master")
    date_selected = data.get("date")

    # Формируем клавиатуру подтверждения
    confirm_kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Да"), KeyboardButton(text="Нет")]],
        resize_keyboard=True,
        one_time_keyboard=True
    )

    # Показываем пользователю итоговые выбранные данные
    await callback.message.answer(
        f"Вы выбрали:\n"
        f"✂️ Услуга: {service}\n"
        f"👨‍🔧 Мастер: {master}\n"
        f"📅 Дата: {date_selected}\n"
        f"⏰ Время: {time_selected}\n\n"
        f"Подтвердите запись:",
        reply_markup=confirm_kb
    )

    # Переходим в состояние подтверждения
    await state.set_state(BookingStates.confirming)

    # Закрываем callback
    await callback.answer()

# ------------------------ Подтверждение записи ------------------------
@router.message(BookingStates.confirming)
async def confirming_booking(message: Message, state: FSMContext):
    # Разрешаем только ответы "Да" или "Нет"
    if message.text.lower() not in ["да", "нет"]:
        await message.answer("Напишите 'Да' или 'Нет'")
        return

    # Получаем данные из FSM
    data = await state.get_data()

    # Если пользователь подтвердил запись
    if message.text.lower() == "да":
        try:
            # Пытаемся добавить бронирование в базу
            await db.add_booking(
                user_id=message.from_user.id,
                service=data["service"],
                date=data["date"],
                time=data["time"],
                master_id=data["master_id"]
            )
        except ValueError as e:
            # Если слот уже занят — выводим ошибку
            await message.answer(str(e))
            await state.clear()
            return

        # Подтверждаем успешную запись
        await message.answer(
            f"✅ Запись подтверждена!\n"
            f"{data['service']} у мастера {data['master']}\n"
            f"{data['date']} {data['time']}",
            reply_markup=MAIN_MENU
        )
    else:
        # Если пользователь отказался — отменяем сценарий
        await message.answer("❌ Запись отменена", reply_markup=MAIN_MENU)

    # В любом случае очищаем состояние FSM
    await state.clear()

# ------------------------ FAQ ------------------------
@router.message(Command("faq"))
@router.message(F.text == "FAQ")
async def faq_cmd(message: Message):
    text = get_faq_text()
    await message.answer(text, parse_mode="Markdown")

# ------------------------ DEBUG ------------------------
@router.message()
async def debug_all_messages(message: Message):
    # Логируем все остальные сообщения,
    # которые не попали ни под один обработчик выше
    logger.info(f"MESSAGE | user={message.from_user.id} | text={message.text}")