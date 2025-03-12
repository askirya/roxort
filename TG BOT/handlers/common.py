from aiogram import Router, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from database.db import get_session
from database.models import User, Transaction, Review
from sqlalchemy import select, or_
from config import ADMIN_IDS

router = Router()

def get_main_keyboard(user_id: int = None):
    base_buttons = [
        [KeyboardButton(text="👤 Профиль"), KeyboardButton(text="💰 Баланс")],
        [KeyboardButton(text="📱 Продать номер"), KeyboardButton(text="🛒 Купить номер")],
        [KeyboardButton(text="💸 Вывести средства"), KeyboardButton(text="⚠️ Споры")],
        [KeyboardButton(text="⭐️ Отзывы")]
    ]
    
    if user_id in ADMIN_IDS:
        base_buttons.append([KeyboardButton(text="🔑 Панель администратора")])
    
    return ReplyKeyboardMarkup(keyboard=base_buttons, resize_keyboard=True)

def get_start_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🔄 Начать регистрацию")]],
        resize_keyboard=True
    )
    return keyboard

async def check_user_registered(user_id: int) -> bool:
    async with await get_session() as session:
        user = await session.get(User, user_id)
        return user is not None

@router.message(lambda message: message.text == "👤 Профиль")
async def show_profile(message: types.Message):
    async with await get_session() as session:
        user = await session.get(User, message.from_user.id)
        if not user:
            await message.answer(
                "❌ Вы не зарегистрированы!\n"
                "Пожалуйста, пройдите регистрацию:",
                reply_markup=get_start_keyboard()
            )
            return
        
        # Получаем статистику пользователя
        tx_query = select(Transaction).where(
            or_(
                Transaction.buyer_id == user.id,
                Transaction.seller_id == user.id
            )
        )
        tx_result = await session.execute(tx_query)
        transactions = tx_result.scalars().all()
        
        sold_count = len([tx for tx in transactions if tx.seller_id == user.id and tx.status == "completed"])
        bought_count = len([tx for tx in transactions if tx.buyer_id == user.id and tx.status == "completed"])
        
        # Получаем количество отзывов
        reviews_query = select(Review).where(Review.reviewed_id == user.id)
        reviews_result = await session.execute(reviews_query)
        reviews_count = len(reviews_result.scalars().all())
        
        await message.answer(
            f"📊 Ваш профиль:\n"
            f"ID: {user.telegram_id}\n"
            f"Телефон: {user.phone_number}\n"
            f"Рейтинг: {'⭐️' * round(user.rating)} ({user.rating:.1f})\n"
            f"Количество отзывов: {reviews_count}\n"
            f"Баланс: {user.balance} USDT\n"
            f"Продано номеров: {sold_count}\n"
            f"Куплено номеров: {bought_count}\n"
            f"Дата регистрации: {user.registered_at.strftime('%d.%m.%Y')}",
            reply_markup=get_main_keyboard(message.from_user.id)
        )

@router.message(lambda message: message.text == "💰 Баланс")
async def show_balance(message: types.Message):
    async with await get_session() as session:
        user = await session.get(User, message.from_user.id)
        if not user:
            await message.answer(
                "❌ Вы не зарегистрированы!\n"
                "Пожалуйста, пройдите регистрацию:",
                reply_markup=get_start_keyboard()
            )
            return
        
        await message.answer(
            f"💰 Ваш текущий баланс: {user.balance} USDT",
            reply_markup=get_main_keyboard(message.from_user.id)
        ) 