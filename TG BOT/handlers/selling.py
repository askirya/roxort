from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from database.db import get_session
from database.models import User, PhoneListing
from config import RENTAL_PERIODS

router = Router()

class SellPhoneStates(StatesGroup):
    choosing_duration = State()
    choosing_service = State()
    entering_price = State()

available_services = [
    "Telegram",
    "WhatsApp",
    "Instagram",
    "Facebook",
    "VK",
    "Gmail",
    "Uber",
    "Airbnb"
]

def get_duration_keyboard():
    keyboard = []
    for duration in RENTAL_PERIODS:
        keyboard.append([KeyboardButton(text=f"⏰ {duration} час(ов)")])
    keyboard.append([KeyboardButton(text="❌ Отмена")])
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def get_services_keyboard():
    keyboard = []
    for i in range(0, len(available_services), 2):
        row = [KeyboardButton(text=available_services[i])]
        if i + 1 < len(available_services):
            row.append(KeyboardButton(text=available_services[i + 1]))
        keyboard.append(row)
    keyboard.append([KeyboardButton(text="❌ Отмена")])
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

@router.message(F.text == "📱 Продать номер")
async def start_selling(message: types.Message, state: FSMContext):
    async with await get_session() as session:
        user = await session.get(User, message.from_user.id)
        if not user:
            await message.answer(
                "❌ Вы не зарегистрированы!\n"
                "Пожалуйста, пройдите регистрацию сначала."
            )
            return

    await state.set_state(SellPhoneStates.choosing_duration)
    await message.answer(
        "⏰ Выберите длительность аренды номера:",
        reply_markup=get_duration_keyboard()
    )

@router.message(SellPhoneStates.choosing_duration)
async def process_duration(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        from handlers.common import get_main_keyboard
        await message.answer("Операция отменена.", reply_markup=get_main_keyboard())
        return

    duration = message.text.split()[1]
    try:
        duration = int(duration)
        if duration not in RENTAL_PERIODS:
            raise ValueError
    except:
        await message.answer("❌ Пожалуйста, выберите длительность из предложенных вариантов.")
        return

    await state.update_data(duration=duration)
    await state.set_state(SellPhoneStates.choosing_service)
    
    await message.answer(
        "📱 Выберите сервис, для которого вы хотите сдать номер:",
        reply_markup=get_services_keyboard()
    )

@router.message(SellPhoneStates.choosing_service)
async def process_service(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        from handlers.common import get_main_keyboard
        await message.answer("Операция отменена.", reply_markup=get_main_keyboard())
        return

    if message.text not in available_services:
        await message.answer("❌ Пожалуйста, выберите сервис из списка.")
        return

    await state.update_data(service=message.text)
    await state.set_state(SellPhoneStates.entering_price)
    
    await message.answer(
        "💰 Введите цену аренды в USDT (например: 5.00):",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="❌ Отмена")]],
            resize_keyboard=True
        )
    )

@router.message(SellPhoneStates.entering_price)
async def process_price(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        from handlers.common import get_main_keyboard
        await message.answer("Операция отменена.", reply_markup=get_main_keyboard())
        return

    try:
        price = float(message.text)
        if price <= 0:
            raise ValueError
    except:
        await message.answer("❌ Пожалуйста, введите корректную цену (например: 5.00)")
        return

    data = await state.get_data()
    
    # Создаем объявление в базе данных
    async with await get_session() as session:
        user = await session.get(User, message.from_user.id)
        new_listing = PhoneListing(
            seller_id=user.id,
            service=data['service'],
            duration=data['duration'],
            price=price,
            is_active=True
        )
        session.add(new_listing)
        await session.commit()

    await state.clear()
    from handlers.common import get_main_keyboard
    
    await message.answer(
        "✅ Объявление успешно создано!\n\n"
        f"📱 Сервис: {data['service']}\n"
        f"⏰ Длительность: {data['duration']} час(ов)\n"
        f"💰 Цена: {price} USDT\n\n"
        "Ваш номер теперь доступен для покупки другим пользователям.",
        reply_markup=get_main_keyboard()
    ) 