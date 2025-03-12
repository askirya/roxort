from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
import random
from database.db import get_session
from database.models import User

router = Router()

class RegistrationStates(StatesGroup):
    waiting_for_phone = State()
    waiting_for_code = State()

verification_codes = {}

def get_phone_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Отправить номер телефона", request_contact=True)]],
        resize_keyboard=True
    )

@router.message(F.contact)
async def process_phone_number(message: types.Message, state: FSMContext):
    phone = message.contact.phone_number
    user_id = message.from_user.id
    
    # Генерируем код подтверждения
    verification_code = str(random.randint(1000, 9999))
    verification_codes[user_id] = {
        'code': verification_code,
        'phone': phone
    }
    
    await state.set_state(RegistrationStates.waiting_for_code)
    
    await message.answer(
        "📲 На ваш номер телефона отправлен код подтверждения.\n"
        "Пожалуйста, введите его:",
        reply_markup=ReplyKeyboardRemove()
    )
    
    # В реальном проекте здесь будет отправка SMS
    # Пока выводим код в сообщении для тестирования
    await message.answer(f"Тестовый режим! Ваш код: {verification_code}")

@router.message(RegistrationStates.waiting_for_code)
async def process_verification_code(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    
    if user_id not in verification_codes:
        await message.answer("❌ Ошибка! Начните регистрацию заново.")
        await state.clear()
        return
    
    if message.text == verification_codes[user_id]['code']:
        phone = verification_codes[user_id]['phone']
        
        # Сохраняем пользователя в базу данных
        async with await get_session() as session:
            new_user = User(
                telegram_id=user_id,
                username=message.from_user.username,
                phone_number=phone
            )
            session.add(new_user)
            await session.commit()
        
        del verification_codes[user_id]
        await state.clear()
        
        from handlers.common import get_main_keyboard
        
        await message.answer(
            "✅ Регистрация успешно завершена!\n"
            "Теперь вы можете использовать все функции бота.",
            reply_markup=get_main_keyboard()
        )
    else:
        await message.answer("❌ Неверный код! Попробуйте еще раз.")

@router.message(F.text == "🔄 Начать регистрацию")
async def start_registration(message: types.Message):
    await message.answer(
        "📝 Для регистрации необходимо подтвердить номер телефона.\n"
        "Нажмите на кнопку ниже, чтобы отправить свой номер:",
        reply_markup=get_phone_keyboard()
    ) 