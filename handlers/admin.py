from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from database.db import get_session
from database.models import User, Transaction, Dispute, PhoneListing, Review
from datetime import datetime, timedelta
from sqlalchemy import select, and_, or_, func
from config import ADMIN_IDS

router = Router()

class AdminStates(StatesGroup):
    waiting_for_user_id = State()
    entering_balance = State()
    entering_announcement = State()

def get_admin_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📊 Статистика"), KeyboardButton(text="👥 Пользователи")],
            [KeyboardButton(text="💰 Управление балансами"), KeyboardButton(text="⚠️ Активные споры")],
            [KeyboardButton(text="📢 Сделать объявление"), KeyboardButton(text="🔒 Заблокировать пользователя")],
            [KeyboardButton(text="❌ Выйти из панели админа")]
        ],
        resize_keyboard=True
    )
    return keyboard

async def check_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

@router.message(lambda message: message.text == "🔑 Панель администратора")
async def show_admin_panel(message: types.Message):
    if not await check_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав администратора!")
        return
    
    await message.answer(
        "👋 Добро пожаловать в панель администратора!\n"
        "Выберите действие:",
        reply_markup=get_admin_keyboard()
    )

@router.message(lambda message: message.text == "📊 Статистика")
async def show_statistics(message: types.Message):
    if not await check_admin(message.from_user.id):
        return
    
    async with await get_session() as session:
        # Общая статистика
        users_count = await session.scalar(select(func.count(User.id)))
        active_listings = await session.scalar(
            select(func.count(PhoneListing.id)).where(PhoneListing.is_active == True)
        )
        
        # Статистика за последние 24 часа
        day_ago = datetime.utcnow() - timedelta(days=1)
        new_users = await session.scalar(
            select(func.count(User.id)).where(User.registered_at >= day_ago)
        )
        new_transactions = await session.scalar(
            select(func.count(Transaction.id)).where(Transaction.created_at >= day_ago)
        )
        
        # Финансовая статистика
        total_volume = await session.scalar(
            select(func.sum(Transaction.amount)).where(Transaction.status == "completed")
        )
        platform_earnings = total_volume * (5 / 100) if total_volume else 0
        
        await message.answer(
            "📊 Статистика платформы\n\n"
            f"👥 Всего пользователей: {users_count}\n"
            f"📱 Активных объявлений: {active_listings}\n"
            f"🆕 Новых пользователей за 24ч: {new_users}\n"
            f"💰 Новых сделок за 24ч: {new_transactions}\n"
            f"💵 Общий объем сделок: {total_volume:.2f} USDT\n"
            f"📈 Заработок платформы: {platform_earnings:.2f} USDT"
        )

@router.message(lambda message: message.text == "👥 Пользователи")
async def show_users(message: types.Message):
    if not await check_admin(message.from_user.id):
        return
    
    async with await get_session() as session:
        query = select(User).order_by(User.registered_at.desc()).limit(10)
        result = await session.execute(query)
        users = result.scalars().all()
        
        response = "👥 Последние 10 пользователей:\n\n"
        for user in users:
            response += (
                f"ID: {user.telegram_id}\n"
                f"Username: @{user.username or 'Нет'}\n"
                f"Баланс: {user.balance} USDT\n"
                f"Рейтинг: ⭐️ {user.rating}\n"
                f"Регистрация: {user.registered_at.strftime('%d.%m.%Y %H:%M')}\n"
                "➖➖➖➖➖➖➖➖➖➖\n"
            )
        
        await message.answer(response)

@router.message(lambda message: message.text == "💰 Управление балансами")
async def manage_balance_start(message: types.Message, state: FSMContext):
    if not await check_admin(message.from_user.id):
        return
    
    await state.set_state(AdminStates.waiting_for_user_id)
    await message.answer(
        "Введите ID пользователя для управления балансом:",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="❌ Отмена")]],
            resize_keyboard=True
        )
    )

@router.message(AdminStates.waiting_for_user_id)
async def process_user_id(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer(
            "Операция отменена.",
            reply_markup=get_admin_keyboard()
        )
        return
    
    try:
        user_id = int(message.text)
        async with await get_session() as session:
            user = await session.get(User, user_id)
            if not user:
                await message.answer("❌ Пользователь не найден!")
                return
            
            await state.update_data(user_id=user_id)
            await state.set_state(AdminStates.entering_balance)
            
            await message.answer(
                f"Текущий баланс пользователя: {user.balance} USDT\n"
                "Введите новый баланс:"
            )
    except:
        await message.answer("❌ Введите корректный ID пользователя!")

@router.message(AdminStates.entering_balance)
async def process_new_balance(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer(
            "Операция отменена.",
            reply_markup=get_admin_keyboard()
        )
        return
    
    try:
        new_balance = float(message.text)
        data = await state.get_data()
        user_id = data['user_id']
        
        async with await get_session() as session:
            user = await session.get(User, user_id)
            old_balance = user.balance
            user.balance = new_balance
            await session.commit()
            
            await message.answer(
                f"✅ Баланс пользователя обновлен!\n"
                f"Старый баланс: {old_balance} USDT\n"
                f"Новый баланс: {new_balance} USDT",
                reply_markup=get_admin_keyboard()
            )
            
            # Уведомляем пользователя
            await message.bot.send_message(
                user.telegram_id,
                f"💰 Ваш баланс был изменен администратором\n"
                f"Новый баланс: {new_balance} USDT"
            )
    except:
        await message.answer("❌ Введите корректную сумму!")
    
    await state.clear()

@router.message(lambda message: message.text == "⚠️ Активные споры")
async def show_active_disputes(message: types.Message):
    if not await check_admin(message.from_user.id):
        return
    
    async with await get_session() as session:
        query = select(Dispute).where(Dispute.status == "open")
        result = await session.execute(query)
        disputes = result.scalars().all()
        
        if not disputes:
            await message.answer("✅ Активных споров нет!")
            return
        
        for dispute in disputes:
            transaction = await session.get(Transaction, dispute.transaction_id)
            buyer = await session.get(User, transaction.buyer_id)
            seller = await session.get(User, transaction.seller_id)
            
            await message.answer(
                f"⚠️ Спор #{dispute.id}\n\n"
                f"Покупатель: @{buyer.username or buyer.telegram_id}\n"
                f"Продавец: @{seller.username or seller.telegram_id}\n"
                f"Сумма: {transaction.amount} USDT\n"
                f"Описание: {dispute.description}\n"
                f"Создан: {dispute.created_at.strftime('%d.%m.%Y %H:%M')}",
                reply_markup=get_admin_dispute_keyboard(dispute.id)
            )

@router.message(lambda message: message.text == "📢 Сделать объявление")
async def start_announcement(message: types.Message, state: FSMContext):
    if not await check_admin(message.from_user.id):
        return
    
    await state.set_state(AdminStates.entering_announcement)
    await message.answer(
        "Введите текст объявления для всех пользователей:",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="❌ Отмена")]],
            resize_keyboard=True
        )
    )

@router.message(AdminStates.entering_announcement)
async def process_announcement(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer(
            "Операция отменена.",
            reply_markup=get_admin_keyboard()
        )
        return
    
    async with await get_session() as session:
        query = select(User)
        result = await session.execute(query)
        users = result.scalars().all()
        
        sent_count = 0
        for user in users:
            try:
                await message.bot.send_message(
                    user.telegram_id,
                    f"📢 Объявление от администрации:\n\n{message.text}"
                )
                sent_count += 1
            except:
                continue
        
        await message.answer(
            f"✅ Объявление отправлено {sent_count} пользователям!",
            reply_markup=get_admin_keyboard()
        )
    
    await state.clear()

@router.message(lambda message: message.text == "🔒 Заблокировать пользователя")
async def block_user_start(message: types.Message, state: FSMContext):
    if not await check_admin(message.from_user.id):
        return
    
    # TODO: Реализовать систему блокировки пользователей
    await message.answer(
        "🚧 Функция в разработке",
        reply_markup=get_admin_keyboard()
    )

@router.message(lambda message: message.text == "❌ Выйти из панели админа")
async def exit_admin_panel(message: types.Message):
    if not await check_admin(message.from_user.id):
        return
    
    from handlers.common import get_main_keyboard
    await message.answer(
        "👋 Вы вышли из панели администратора",
        reply_markup=get_main_keyboard()
    ) 