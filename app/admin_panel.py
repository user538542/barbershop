# app/admin_panel.py

from fastapi import APIRouter, Form
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi import Depends, HTTPException, status
import secrets

from app import db
from app.utils import logger
import io
import csv
from datetime import datetime, timedelta
from collections import Counter, defaultdict
import calendar
from dateutil.relativedelta import relativedelta

router = APIRouter()

# -------------------- HTML-каркас (шаблон) --------------------
BASE_HTML = """
<html>
<head>
<style>
body {{
    font-family: Arial, sans-serif;
    background: #f9f9f9;
    margin: 20px;
}}
h1, h2, h3 {{
    color: #333;
}}
a {{
    text-decoration: none;
    color: #0066cc;
    margin-right: 10px;
}}
table {{
    border-collapse: collapse;
    margin-top: 15px;
}}
table, th, td {{
    border: 1px solid #ccc;
}}
th, td {{
    padding: 8px 12px;
    text-align: left;
}}
th {{
    background: #eee;
}}
tr:nth-child(even) {{
    background: #f2f2f2;
}}
input, select, button {{
    padding: 5px 8px;
    margin: 5px 0;
    border: 1px solid #ccc;
    border-radius: 4px;
}}
button {{
    background-color: #4CAF50;
    color: white;
    cursor: pointer;
}}
button:hover {{
    background-color: #45a049;
}}
form {{
    margin-bottom: 15px;
}}
</style>
</head>
<body>
{content}
</body>
</html>
"""

def render_page(content: str) -> HTMLResponse:
    """Возвращает HTMLResponse с базовой стилизацией"""
    return HTMLResponse(BASE_HTML.format(content=content))

# -------------------- Авторизация --------------------
security = HTTPBasic()

def check_admin(credentials: HTTPBasicCredentials = Depends(security)):

    correct_username = secrets.compare_digest(credentials.username, "admin")
    correct_password = secrets.compare_digest(credentials.password, "12345")

    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный логин или пароль",
            headers={"WWW-Authenticate": "Basic"},
        )

    return credentials.username
# -------------------- Главная страница --------------------
@router.get("/admin", response_class=HTMLResponse)
async def admin_page(
        service_filter: str = "",
        user_filter: str = "",
        master_filter: str = "",
        date_filter: str = "",
        admin: str = Depends(check_admin)  
):

    bookings = await db.get_all_bookings()

    filtered = []

    for b in bookings:

        if service_filter and service_filter.lower() not in b["service"].lower():
            continue

        first_name = b.get("first_name") or ""
        last_name = b.get("last_name") or ""  # если NULL, заменяем на пустую строку

        # Формируем полное имя: если есть username — добавляем, иначе только имя
        name = f"{first_name} {last_name}".strip()
        username = b.get("username") or ""
        client = f"{name} (@{username})" if username else name

        if user_filter and user_filter.lower() not in client.lower():
            continue

        master = b.get("name") or ""

        if master_filter and master_filter.lower() not in master.lower():
            continue

        if date_filter and date_filter != b["date"]:
            continue

        filtered.append(b)

    html = f"""
    <h1>Административная панель</h1>

    <a href="/admin/services">🛠 Услуги</a> |
    <a href="/admin/masters">👨‍🔧 Мастера</a> |
    <a href="/admin/schedules">📅 Расписание</a> |
    <a href="/admin/load">📊 Загрузка мастеров</a> |
    <a href="/admin/calendar">📅 Календарь</a> |
    <a href="/admin/export">⬇️ CSV</a>

    <h3>Фильтры</h3>

    <form method="get">

    Услуга
    <input name="service_filter" value="{service_filter}">

    Клиент
    <input name="user_filter" value="{user_filter}">

    Мастер
    <input name="master_filter" value="{master_filter}">

    Дата
    <input name="date_filter" value="{date_filter}">

    <button>Применить</button>
    <a href="/admin"><button type="button">Сброс</button></a>
    
    </form>

    <br>

    <table border="1">

    <tr>
        <th>ID</th>
        <th>Клиент</th>
        <th>Услуга</th>
        <th>Мастер</th>
        <th>Дата</th>
        <th>Время</th>
        <th>Действия</th>
    </tr>
    """

    for b in filtered:

        first_name = b.get('first_name') or ""   # если None, заменяем на пустую строку
        last_name = b.get('last_name') or ""     # если None, заменяем на пустую строку
        name = f"{first_name} {last_name}".strip()
        username = b.get("username") or ""
        client = f"{name} (@{username})" if username else name
        master = b.get("name") or "-"

        html += f"""
        <tr>
        <td>{b['id']}</td>
        <td>{client}</td>
        <td>{b['service']}</td>
        <td>{master}</td>
        <td>{b['date']}</td>
        <td>{b['time']}</td>

        <td>
        <form method="post" action="/admin/delete">
        <input type="hidden" name="booking_id" value="{b['id']}">
        <button>Удалить</button>
        </form>
        </td>
        </tr>
        """

    html += "</table>"

    return render_page(html)

# -------------------- Удаление записи --------------------
@router.post("/admin/delete")
async def delete_booking(booking_id: int = Form(...)):
    await db.delete_booking(booking_id)

    return render_page("<a href='/admin'>Назад</a>")

# -------------------- CSV экспорт --------------------
@router.get("/admin/export")
async def export_csv():

    bookings = await db.get_all_bookings()

    output = io.StringIO()

    # 👇 добавляем BOM
    output.write('\ufeff')

    writer = csv.writer(output, delimiter=';')  # лучше ; для Excel

    writer.writerow(["ID","Клиент","Услуга","Мастер","Дата","Время"])

    for b in bookings:

        name = f"{b.get('first_name','')} {b.get('last_name','')}".strip()
        username = b.get("username") or ""
        client = f"{name} (@{username})" if username else name

        writer.writerow([
            b["id"],
            client,
            b["service"],
            b.get("name"),
            b["date"],
            b["time"]
        ])

    output.seek(0)

    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=bookings.csv"}
    )

# =========================================================
# МАСТЕРА
# =========================================================

@router.get("/admin/masters", response_class=HTMLResponse)
async def masters_page(admin: str = Depends(check_admin)):
    masters = await db.get_masters()

    html = """
    <h2>Мастера</h2>

    <a href="/admin">Назад</a>

    <h3>Добавить</h3>

    <form method="post" action="/admin/masters/add">
    Имя <input name="name">
    Специализация <input name="specialty">
    <button>Добавить</button>
    </form>

    <table border="1">

    <tr>
    <th>ID</th>
    <th>Имя</th>
    <th>Специализация</th>
    <th></th>
    </tr>
    """

    for m in masters:

        html += f"""
        <tr>

        <td>{m['id']}</td>
        <td>{m['name']}</td>
        <td>{m['specialty']}</td>

        <td>

        <form method="post" action="/admin/masters/delete">
        <input type="hidden" name="id" value="{m['id']}">
        <button>Удалить</button>
        </form>

        </td>

        </tr>
        """

    html += "</table>"

    return render_page(html)

@router.post("/admin/masters/add")
async def add_master(name: str = Form(...), specialty: str = Form("")):

    await db.database.execute(
        "INSERT INTO masters(name,specialty) VALUES(:name,:specialty)",
        {"name": name, "specialty": specialty}
    )
    return render_page("<a href='/admin/masters'>Назад</a>")

@router.post("/admin/masters/delete")
async def delete_master(id: int = Form(...)):

    await db.database.execute(
        "DELETE FROM masters WHERE id=:id",
        {"id": id}
    )
    return render_page("<a href='/admin/masters'>Назад</a>")

# =========================================================
# РАСПИСАНИЕ
# =========================================================

@router.get("/admin/schedules", response_class=HTMLResponse)
async def schedules_page(admin: str = Depends(check_admin)):

    schedules = await db.database.fetch_all(
        """
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
    )

    masters = await db.get_masters()

    master_options = ""
    for m in masters:
        master_options += f"<option value='{m['id']}'>{m['name']}</option>"

    html = f"""
    <h2>Расписание</h2>

    <a href="/admin">Назад</a>

    <h3>Добавить</h3>

    <form method="post" action="/admin/schedules/add">

    Мастер
    <select name="master_id" required>
        <option value="">--Выберите мастера--</option>
        {master_options}
    </select>

    День недели (0=Пн, 6=Вс)
    <input name="day" type="number" min="0" max="6" required>

    Начало
    <input name="start" type="time" required>

    Конец
    <input name="end" type="time" required>

    <button>Добавить</button>

    </form>

    <table border="1">

    <tr>
        <th>ID</th>
        <th>Мастер</th>
        <th>День</th>
        <th>Начало</th>
        <th>Конец</th>
        <th></th>
    </tr>
    """

    for s in schedules:

        html += f"""
        <tr>

        <td>{s['id']}</td>
        <td>{s['master_name']}</td>
        <td>{s['day_name']}</td>
        <td>{s['start_time']}</td>
        <td>{s['end_time']}</td>

        <td>
        <form method="post" action="/admin/schedules/delete">
        <input type="hidden" name="id" value="{s['id']}">
        <button>Удалить</button>
        </form>
        </td>

        </tr>
        """

    html += "</table>"

    return render_page(html)

# -------------------- Добавление расписания --------------------
@router.post("/admin/schedules/add")
async def add_schedule(
    master_id: int = Form(...),
    day: int = Form(...),
    start: str = Form(...),
    end: str = Form(...)
):
    await db.database.execute(
        """
        INSERT INTO schedules(master_id, day_of_week, start_time, end_time)
        VALUES(:master_id, :day, :start, :end)
        """,
        {"master_id": master_id, "day": day, "start": start, "end": end}
    )
    return render_page("<a href='/admin/schedules'>Назад</a>")
# -------------------- Удаление расписания --------------------
@router.post("/admin/schedules/delete")
async def delete_schedule(id: int = Form(...)):
    """Удаляет запись расписания по ID"""
    await db.database.execute(
        "DELETE FROM schedules WHERE id=:id",
        {"id": id}
    )
    # После удаления возвращаемся на страницу расписания
    return render_page("<a href='/admin/schedules'>Назад</a>")
# =========================================================
# ГРАФИК ЗАГРУЗКИ МАСТЕРОВ
# =========================================================

@router.get("/admin/load", response_class=HTMLResponse)
async def master_load():

    bookings = await db.get_bookings_stat()

    html = """
    <h2>Загрузка мастеров</h2>

    <a href="/admin">Назад</a>

    <table border="1">

    <tr>
    <th>Год</th>
    <th>Месяц</th>
    <th>Мастер</th>
    <th>Записей</th>
    </tr>
    """

    for b in bookings:

        html += f"""
        <tr>

        <td>{b['yyyy']}</td>
        <td>{b['mm']}</td>
        <td>{b['name']}</td>
        <td>{b['quantity']}</td>

        </tr>
        """

    html += "</table>"

    return render_page(html)

# =========================================================
# ВИЗУАЛЬНЫЙ КАЛЕНДАРЬ
# =========================================================
async def render_calendar_for_month(bookings, year, month):
    """Возвращает HTML таблицу календаря для заданного месяца"""
    cal = defaultdict(list)
    for b in bookings:
        date_obj = datetime.strptime(b["date"], "%d.%m.%Y")
        if date_obj.year == year and date_obj.month == month:
            master_name = b.get("name") or "Не назначен"
            cal[b["date"]].append(f"{b['time']} {b['service']} 💇 {master_name}")

    month_days = calendar.monthcalendar(year, month)
    html = f"<h2>Календарь {month}.{year}</h2><table border='1' cellspacing='0' cellpadding='5'>"
    html += "<tr><th>Понедельник</th><th>Вторник</th><th>Среда</th><th>Четверг</th><th>Пятница</th><th>Суббота</th><th>Воскресенье</th></tr>"
    for week in month_days:
        html += "<tr>"
        for day in week:
            if day == 0:
                html += "<td></td>"
                continue
            date_str = f"{day:02}.{month:02}.{year}"
            items = "<br>".join(cal.get(date_str, []))
            html += f"<td><b>{day}</b><br>{items}</td>"
        html += "</tr>"

    html += "</table><br>"
    return html


@router.get("/admin/calendar", response_class=HTMLResponse)
async def schedules_page(admin: str = Depends(check_admin)):

    bookings = await db.get_all_bookings()

    # Текущий месяц
    today = datetime.now()
    html = '<a href="/admin">Назад</a><br><br>'

    # Список всех месяцев, в которых есть записи
    months_with_bookings = set()
    for b in bookings:
        date_obj = datetime.strptime(b["date"], "%d.%m.%Y")
        months_with_bookings.add((date_obj.year, date_obj.month))

    # Предыдущий месяц
    prev_month = today - relativedelta(months=1)
    if (prev_month.year, prev_month.month) in months_with_bookings:
        html += await render_calendar_for_month(bookings, prev_month.year, prev_month.month)

    # Текущий месяц
    html += await render_calendar_for_month(bookings, today.year, today.month)

    # Следующий месяц
    next_month = today + relativedelta(months=1)
    if (next_month.year, next_month.month) in months_with_bookings:
        html += await render_calendar_for_month(bookings, next_month.year, next_month.month)

    return render_page(html)

# =========================================================
# УСЛУГИ (ВОЗВРАЩЕНЫ)
# =========================================================

@router.get("/admin/services", response_class=HTMLResponse)
async def admin_services():

    services = await db.get_services()

    html = """

    <h2>Услуги</h2>

    <a href="/admin">Назад</a>

    <h3>Добавить</h3>

    <form method="post" action="/admin/services/add">

    Название
    <input name="name">

    Цена
    <input name="price">

    <button>Добавить</button>

    </form>

    <table border="1">

    <tr>
    <th>ID</th>
    <th>Название</th>
    <th>Цена</th>
    <th></th>
    </tr>
    """

    for s in services:

        html += f"""
        <tr>

        <td>{s['id']}</td>
        <td>{s['name']}</td>
        <td>{s['price']}₽</td>

        <td>

        <form method="post" action="/admin/services/delete">
        <input type="hidden" name="service_id" value="{s['id']}">
        <button>Удалить</button>
        </form>

        </td>

        </tr>
        """

    html += "</table>"

    return render_page(html)

@router.post("/admin/services/add")
async def add_service(name: str = Form(...), price: int = Form(...)):

    await db.database.execute(
        "INSERT INTO services(name,price) VALUES(:n,:p)",
        {"n": name, "p": price}
    )

    return render_page("<a href='/admin/services'>Назад</a>")

@router.post("/admin/services/delete")
async def delete_service(service_id: int = Form(...)):

    await db.database.execute(
        "DELETE FROM services WHERE id=:id",
        {"id": service_id}
    )
    return render_page("<a href='/admin/services'>Назад</a>")