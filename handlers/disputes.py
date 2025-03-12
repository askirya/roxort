from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from database.db import get_session
from database.models import User, Transaction, Dispute
from datetime import datetime
from sqlalchemy import select, and_
from config import ADMIN_IDS

router = Router()

class DisputeStates(StatesGroup):
    entering_description = State()
    admin_reviewing = State()
    waiting_for_response = State()

def get_dispute_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📝 Открыть спор")],
            [KeyboardButton(text="📋 Мои споры")],
            [KeyboardButton(text="❌ Отмена")]
        ],
        resize_keyboard=True
    )
    return keyboard

def get_admin_dispute_keyboard(dispute_id: int):
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Вернуть средства покупателю", 
                                   callback_data=f"resolve_buyer_{dispute_id}"),
                InlineKeyboardButton(text="💰 Передать средства продавцу", 
                                   callback_data=f"resolve_seller_{dispute_id}")
            ],
            [
                InlineKeyboardButton(text="❌ Закрыть спор", 
                                   callback_data=f"close_dispute_{dispute_id}")
            ]
        ]
    )
    return keyboard

@router.message(F.text == "⚠️ Споры")
async def show_dispute_menu(message: types.Message):
    async with await get_session() as session:
        user = await session.get(User, message.from_user.id)
        if not user:
            await message.answer("❌ Вы не зарегистрированы!")
            return
        
        await message.answer(
            "🔍 Выберите действие:",
            reply_markup=get_dispute_keyboard()
        )

@router.message(F.text == "📝 Открыть спор")
async def start_dispute(message: types.Message, state: FSMContext):
    async with await get_session() as session:
        # Получаем активные транзакции пользователя
        query = select(Transaction).where(
            and_(
                Transaction.buyer_id == message.from_user.id,
                Transaction.status == "pending"
            )
        )
        result = await session.execute(query)
        transactions = result.scalars().all()
        
        if not transactions:
            await message.answer(
                "❌ У вас нет активных сделок, по которым можно открыть спор."
            )
            return
        
        # Создаем клавиатуру с транзакциями
        keyboard = []
        for tx in transactions:
            listing = await session.get(PhoneListing, tx.listing_id)
            keyboard.append([
                KeyboardButton(text=f"📱 {listing.service} - {tx.amount} USDT (ID: {tx.id})")
            ])
        keyboard.append([KeyboardButton(text="❌ Отмена")])
        
        await state.set_state(DisputeStates.entering_description)
        await message.answer(
            "📝 Выберите сделку, по которой хотите открыть спор:",
            reply_markup=ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
        )

@router.message(DisputeStates.entering_description)
async def process_dispute_description(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        from handlers.common import get_main_keyboard
        await message.answer("Операция отменена.", reply_markup=get_main_keyboard())
        return
    
    try:
        tx_id = int(message.text.split("ID: ")[1].strip(")"))
    except:
        await message.answer("❌ Пожалуйста, выберите сделку из списка.")
        return
    
    async with await get_session() as session:
        transaction = await session.get(Transaction, tx_id)
        if not transaction:
            await message.answer("❌ Сделка не найдена.")
            return
        
        # Создаем новый спор
        dispute = Dispute(
            transaction_id=tx_id,
            initiator_id=message.from_user.id,
            description=message.text,
            status="open"
        )
        session.add(dispute)
        
        # Обновляем статус транзакции
        transaction.status = "disputed"
        
        await session.commit()
        
        # Уведомляем администраторов
        for admin_id in ADMIN_IDS:
            try:
                await message.bot.send_message(
                    admin_id,
                    f"⚠️ Открыт новый спор!\n\n"
                    f"ID транзакции: {tx_id}\n"
                    f"Покупатель: {message.from_user.username or message.from_user.id}\n"
                    f"Описание: {message.text}",
                    reply_markup=get_admin_dispute_keyboard(dispute.id)
                )
            except:
                continue
        
        await state.clear()
        from handlers.common import get_main_keyboard
        
        await message.answer(
            "✅ Спор успешно открыт!\n"
            "Администратор рассмотрит вашу заявку в ближайшее время.",
            reply_markup=get_main_keyboard()
        )

@router.message(F.text == "📋 Мои споры")
async def show_my_disputes(message: types.Message):
    async with await get_session() as session:
        # Получаем все споры пользователя
        query = select(Dispute).where(
            Dispute.initiator_id == message.from_user.id
        ).order_by(Dispute.created_at.desc())
        
        result = await session.execute(query)
        disputes = result.scalars().all()
        
        if not disputes:
            await message.answer("У вас нет открытых споров.")
            return
        
        for dispute in disputes:
            transaction = await session.get(Transaction, dispute.transaction_id)
            listing = await session.get(PhoneListing, transaction.listing_id)
            
            status_emoji = {
                "open": "🔴",
                "resolved": "✅",
                "closed": "⚫️"
            }
            
            await message.answer(
                f"{status_emoji.get(dispute.status, '❓')} Спор #{dispute.id}\n\n"
                f"📱 Сервис: {listing.service}\n"
                f"💰 Сумма: {transaction.amount} USDT\n"
                f"📅 Создан: {dispute.created_at.strftime('%d.%m.%Y %H:%M')}\n"
                f"📝 Статус: {dispute.status}\n"
                f"ℹ️ Описание: {dispute.description}"
            )

@router.callback_query(lambda c: c.data.startswith('resolve_'))
async def resolve_dispute(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ У вас нет прав администратора!")
        return
    
    action, dispute_id = callback.data.split('_')[1:]
    dispute_id = int(dispute_id)
    
    async with await get_session() as session:
        dispute = await session.get(Dispute, dispute_id)
        if not dispute or dispute.status != "open":
            await callback.answer("❌ Спор уже закрыт или не существует!")
            return
        
        transaction = await session.get(Transaction, dispute.transaction_id)
        buyer = await session.get(User, transaction.buyer_id)
        seller = await session.get(User, transaction.seller_id)
        
        if action == "buyer":
            # Возвращаем средства покупателю
            buyer.balance += transaction.amount
            transaction.status = "refunded"
            dispute.status = "resolved"
            
            await callback.message.edit_text(
                f"✅ Спор #{dispute_id} разрешен в пользу покупателя\n"
                f"💰 Сумма {transaction.amount} USDT возвращена покупателю."
            )
            
            # Уведомляем покупателя
            await callback.bot.send_message(
                buyer.telegram_id,
                f"✅ Ваш спор #{dispute_id} разрешен!\n"
                f"💰 Сумма {transaction.amount} USDT возвращена на ваш баланс."
            )
            
        elif action == "seller":
            # Передаем средства продавцу
            seller.balance += transaction.amount
            transaction.status = "completed"
            dispute.status = "resolved"
            
            await callback.message.edit_text(
                f"✅ Спор #{dispute_id} разрешен в пользу продавца\n"
                f"💰 Сумма {transaction.amount} USDT передана продавцу."
            )
            
            # Уведомляем продавца
            await callback.bot.send_message(
                seller.telegram_id,
                f"✅ Спор по сделке разрешен в вашу пользу!\n"
                f"💰 Сумма {transaction.amount} USDT зачислена на ваш баланс."
            )
        
        await session.commit()

@router.callback_query(lambda c: c.data.startswith('close_dispute_'))
async def close_dispute(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ У вас нет прав администратора!")
        return
    
    dispute_id = int(callback.data.split('_')[2])
    
    async with await get_session() as session:
        dispute = await session.get(Dispute, dispute_id)
        if not dispute or dispute.status != "open":
            await callback.answer("❌ Спор уже закрыт или не существует!")
            return
        
        dispute.status = "closed"
        await session.commit()
        
        await callback.message.edit_text(
            f"⚫️ Спор #{dispute_id} закрыт администратором."
        ) 