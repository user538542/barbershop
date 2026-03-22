# app/fsm_states.py
from aiogram.fsm.state import StatesGroup, State

class BookingStates(StatesGroup):
    """
    FSM состояния для процесса записи на услугу.
    """
    choosing_service = State()  # Выбор услуги
    choosing_date = State()     # Ввод даты
    choosing_time = State()     # Ввод времени
    confirming = State()        # Подтверждение записи