from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from database.db import get_session
from database.models import User
from datetime import datetime
from handlers.common import get_main_keyboard

router = Router()

class RegistrationStates(StatesGroup):
    waiting_for_phone = State()

@router.message(lambda message: message.text == "🔄 Начать регистрацию")
async def start_registration(message: types.Message):
    keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Поделиться номером", request_contact=True)]],
        resize_keyboard=True
    )
    await message.answer(
        "Для регистрации поделитесь своим номером телефона:",
        reply_markup=keyboard
    )

@router.message(F.contact)
async def process_phone_number(message: types.Message, state: FSMContext):
    phone_number = message.contact.phone_number
    
    async with await get_session() as session:
        # Проверяем, не зарегистрирован ли уже этот номер
        existing_user = await session.get(User, message.from_user.id)
        if existing_user:
            await message.answer(
                "✅ Вы уже зарегистрированы!",
                reply_markup=get_main_keyboard(message.from_user.id)
            )
            return
        
        # Создаем нового пользователя
        new_user = User(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            phone_number=phone_number,
            balance=0.0,
            rating=5.0,
            registered_at=datetime.utcnow()
        )
        session.add(new_user)
        await session.commit()
        
        await message.answer(
            "✅ Регистрация успешно завершена!\n"
            "Теперь вы можете покупать и продавать номера.",
            reply_markup=get_main_keyboard(message.from_user.id)
        ) 