from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from database.db import get_session
from database.models import User, PhoneListing, Transaction
from datetime import datetime
from sqlalchemy import select, and_

router = Router()

class BuyPhoneStates(StatesGroup):
    choosing_service = State()
    choosing_duration = State()
    viewing_listings = State()
    confirming_purchase = State()

def get_filter_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔍 Поиск по сервису"), KeyboardButton(text="⏰ Поиск по времени")],
            [KeyboardButton(text="💰 Сначала дешевые"), KeyboardButton(text="💰 Сначала дорогие")],
            [KeyboardButton(text="🔄 Сначала новые"), KeyboardButton(text="❌ Отмена")]
        ],
        resize_keyboard=True
    )
    return keyboard

def get_listing_keyboard(listing_id: int):
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Купить", callback_data=f"buy_{listing_id}"),
                InlineKeyboardButton(text="➡️ Следующий", callback_data="next_listing")
            ]
        ]
    )
    return keyboard

@router.message(F.text == "🛒 Купить номер")
async def start_buying(message: types.Message, state: FSMContext):
    async with await get_session() as session:
        user = await session.get(User, message.from_user.id)
        if not user:
            await message.answer(
                "❌ Вы не зарегистрированы!\n"
                "Пожалуйста, пройдите регистрацию сначала."
            )
            return

    await message.answer(
        "🔍 Выберите способ поиска номера:",
        reply_markup=get_filter_keyboard()
    )

@router.message(F.text == "🔍 Поиск по сервису")
async def search_by_service(message: types.Message, state: FSMContext):
    from handlers.selling import get_services_keyboard
    await state.set_state(BuyPhoneStates.choosing_service)
    await message.answer(
        "📱 Выберите сервис:",
        reply_markup=get_services_keyboard()
    )

@router.message(BuyPhoneStates.choosing_service)
async def process_service_choice(message: types.Message, state: FSMContext):
    from handlers.selling import available_services
    
    if message.text == "❌ Отмена":
        await state.clear()
        from handlers.common import get_main_keyboard
        await message.answer("Операция отменена.", reply_markup=get_main_keyboard())
        return

    if message.text not in available_services:
        await message.answer("❌ Пожалуйста, выберите сервис из списка.")
        return

    async with await get_session() as session:
        query = select(PhoneListing).where(
            and_(
                PhoneListing.service == message.text,
                PhoneListing.is_active == True
            )
        ).order_by(PhoneListing.created_at.desc())
        
        result = await session.execute(query)
        listings = result.scalars().all()

        if not listings:
            await message.answer(
                "😕 К сожалению, сейчас нет доступных номеров для этого сервиса.\n"
                "Попробуйте позже или выберите другой сервис."
            )
            return

        await state.update_data(current_listing_index=0, listings=[listing.id for listing in listings])
        await show_listing(message, state, listings[0])

async def show_listing(message: types.Message, state: FSMContext, listing: PhoneListing):
    async with await get_session() as session:
        seller = await session.get(User, listing.seller_id)
        
        await message.answer(
            f"📱 Номер для {listing.service}\n\n"
            f"⏰ Длительность: {listing.duration} час(ов)\n"
            f"💰 Цена: {listing.price} USDT\n"
            f"👤 Продавец: {seller.username or 'Аноним'}\n"
            f"⭐️ Рейтинг продавца: {seller.rating}\n"
            f"📅 Размещено: {listing.created_at.strftime('%d.%m.%Y %H:%M')}",
            reply_markup=get_listing_keyboard(listing.id)
        )

@router.callback_query(lambda c: c.data.startswith('buy_'))
async def process_buy(callback: types.CallbackQuery, state: FSMContext):
    listing_id = int(callback.data.split('_')[1])
    
    async with await get_session() as session:
        listing = await session.get(PhoneListing, listing_id)
        buyer = await session.get(User, callback.from_user.id)
        
        if not listing or not listing.is_active:
            await callback.message.answer("❌ Это предложение уже недоступно.")
            return
        
        if buyer.balance < listing.price:
            await callback.message.answer(
                "❌ Недостаточно средств на балансе!\n"
                f"Необходимо: {listing.price} USDT\n"
                f"На балансе: {buyer.balance} USDT\n\n"
                "Пополните баланс и попробуйте снова."
            )
            return
        
        # Создаем транзакцию
        transaction = Transaction(
            buyer_id=buyer.id,
            seller_id=listing.seller_id,
            listing_id=listing_id,
            amount=listing.price,
            status="pending"
        )
        
        # Обновляем статус объявления
        listing.is_active = False
        
        # Блокируем средства покупателя
        buyer.balance -= listing.price
        
        session.add(transaction)
        await session.commit()
        
        await callback.message.answer(
            "✅ Покупка успешно совершена!\n\n"
            f"📱 Сервис: {listing.service}\n"
            f"⏰ Длительность: {listing.duration} час(ов)\n"
            f"💰 Сумма: {listing.price} USDT\n\n"
            "⚠️ Если продавец не предоставит доступ или будет мешать использованию номера, "
            "вы можете открыть спор, нажав кнопку в своем профиле."
        )

@router.callback_query(lambda c: c.data == 'next_listing')
async def show_next_listing(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    current_index = data.get('current_listing_index', 0)
    listings = data.get('listings', [])
    
    if current_index + 1 >= len(listings):
        await callback.answer("Это последнее предложение в списке.")
        return
    
    current_index += 1
    await state.update_data(current_listing_index=current_index)
    
    async with await get_session() as session:
        listing = await session.get(PhoneListing, listings[current_index])
        if listing:
            await show_listing(callback.message, state, listing)

@router.message(F.text == "💰 Сначала дешевые")
async def sort_by_price_asc(message: types.Message, state: FSMContext):
    async with await get_session() as session:
        query = select(PhoneListing).where(
            PhoneListing.is_active == True
        ).order_by(PhoneListing.price.asc())
        
        await process_sorted_listings(message, state, session, query)

@router.message(F.text == "💰 Сначала дорогие")
async def sort_by_price_desc(message: types.Message, state: FSMContext):
    async with await get_session() as session:
        query = select(PhoneListing).where(
            PhoneListing.is_active == True
        ).order_by(PhoneListing.price.desc())
        
        await process_sorted_listings(message, state, session, query)

@router.message(F.text == "🔄 Сначала новые")
async def sort_by_date(message: types.Message, state: FSMContext):
    async with await get_session() as session:
        query = select(PhoneListing).where(
            PhoneListing.is_active == True
        ).order_by(PhoneListing.created_at.desc())
        
        await process_sorted_listings(message, state, session, query)

async def process_sorted_listings(message: types.Message, state: FSMContext, session, query):
    result = await session.execute(query)
    listings = result.scalars().all()
    
    if not listings:
        await message.answer("😕 Сейчас нет доступных предложений.")
        return
    
    await state.update_data(current_listing_index=0, listings=[listing.id for listing in listings])
    await show_listing(message, state, listings[0]) 