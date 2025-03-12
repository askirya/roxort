from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from database.db import get_session
from database.models import User, Transaction
from datetime import datetime
import aiohttp
from config import CRYPTO_BOT_TOKEN, MIN_WITHDRAWAL

router = Router()

class PaymentStates(StatesGroup):
    entering_deposit_amount = State()
    entering_withdrawal_amount = State()

def get_payment_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="💳 Пополнить"), KeyboardButton(text="💸 Вывести")],
            [KeyboardButton(text="❌ Отмена")]
        ],
        resize_keyboard=True
    )
    return keyboard

async def create_invoice(amount: float) -> dict:
    """Создает инвойс в CryptoBot"""
    url = f"https://pay.crypt.bot/api/createInvoice"
    headers = {"Crypto-Pay-API-Token": CRYPTO_BOT_TOKEN}
    params = {
        "asset": "USDT",
        "amount": str(amount),
        "description": "Пополнение баланса в ROXORT SMS",
        "paid_btn_name": "back",
        "paid_btn_url": "https://t.me/roxort_bot"
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=params) as response:
            return await response.json()

async def create_transfer(user_id: int, amount: float) -> dict:
    """Создает перевод в CryptoBot"""
    url = f"https://pay.crypt.bot/api/transfer"
    headers = {"Crypto-Pay-API-Token": CRYPTO_BOT_TOKEN}
    params = {
        "user_id": user_id,
        "asset": "USDT",
        "amount": str(amount),
        "spend_id": f"withdrawal_{datetime.utcnow().timestamp()}"
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=params) as response:
            return await response.json()

@router.message(lambda message: message.text in ["💰 Баланс", "💳 Пополнить", "💸 Вывести"])
async def show_payment_menu(message: types.Message):
    if message.text == "💰 Баланс":
        async with await get_session() as session:
            user = await session.get(User, message.from_user.id)
            if not user:
                await message.answer("❌ Вы не зарегистрированы!")
                return
            
            await message.answer(
                f"💰 Ваш текущий баланс: {user.balance} USDT\n\n"
                "Выберите действие:",
                reply_markup=get_payment_keyboard()
            )
    else:
        await process_payment_action(message)

async def process_payment_action(message: types.Message):
    if message.text == "💳 Пополнить":
        await message.answer(
            "Введите сумму пополнения в USDT (минимум 1 USDT):",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="❌ Отмена")]],
                resize_keyboard=True
            )
        )
        await PaymentStates.entering_deposit_amount.set()
    
    elif message.text == "💸 Вывести":
        async with await get_session() as session:
            user = await session.get(User, message.from_user.id)
            if user.balance < MIN_WITHDRAWAL:
                await message.answer(
                    f"❌ Минимальная сумма для вывода: {MIN_WITHDRAWAL} USDT\n"
                    f"На вашем балансе: {user.balance} USDT"
                )
                return
            
            await message.answer(
                f"Введите сумму вывода в USDT (минимум {MIN_WITHDRAWAL} USDT):",
                reply_markup=ReplyKeyboardMarkup(
                    keyboard=[[KeyboardButton(text="❌ Отмена")]],
                    resize_keyboard=True
                )
            )
            await PaymentStates.entering_withdrawal_amount.set()

@router.message(PaymentStates.entering_deposit_amount)
async def process_deposit_amount(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        from handlers.common import get_main_keyboard
        await message.answer("Операция отменена.", reply_markup=get_main_keyboard())
        return
    
    try:
        amount = float(message.text)
        if amount < 1:
            raise ValueError
    except:
        await message.answer("❌ Пожалуйста, введите корректную сумму (минимум 1 USDT)")
        return
    
    # Создаем инвойс через CryptoBot
    invoice = await create_invoice(amount)
    
    if invoice.get("ok"):
        pay_url = invoice["result"]["pay_url"]
        await message.answer(
            f"💳 Счет на оплату создан\n\n"
            f"Сумма: {amount} USDT\n"
            f"Нажмите на кнопку ниже для оплаты:",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="💰 Оплатить", url=pay_url)]
                ]
            )
        )
    else:
        await message.answer("❌ Произошла ошибка при создании счета. Попробуйте позже.")
    
    await state.clear()
    from handlers.common import get_main_keyboard
    await message.answer("Выберите действие:", reply_markup=get_main_keyboard())

@router.message(PaymentStates.entering_withdrawal_amount)
async def process_withdrawal_amount(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        from handlers.common import get_main_keyboard
        await message.answer("Операция отменена.", reply_markup=get_main_keyboard())
        return
    
    try:
        amount = float(message.text)
        if amount < MIN_WITHDRAWAL:
            raise ValueError
    except:
        await message.answer(f"❌ Пожалуйста, введите корректную сумму (минимум {MIN_WITHDRAWAL} USDT)")
        return
    
    async with await get_session() as session:
        user = await session.get(User, message.from_user.id)
        if amount > user.balance:
            await message.answer(
                "❌ Недостаточно средств на балансе!\n"
                f"Запрошено: {amount} USDT\n"
                f"Доступно: {user.balance} USDT"
            )
            return
        
        # Создаем перевод через CryptoBot
        transfer = await create_transfer(user.telegram_id, amount)
        
        if transfer.get("ok"):
            # Уменьшаем баланс пользователя
            user.balance -= amount
            await session.commit()
            
            await message.answer(
                "✅ Средства успешно выведены!\n\n"
                f"Сумма: {amount} USDT\n"
                f"Новый баланс: {user.balance} USDT"
            )
        else:
            await message.answer("❌ Произошла ошибка при выводе средств. Попробуйте позже.")
    
    await state.clear()
    from handlers.common import get_main_keyboard
    await message.answer("Выберите действие:", reply_markup=get_main_keyboard())

# Обработчик уведомлений от CryptoBot
@router.message(lambda message: message.get_command() == "/cryptobot_payment")
async def handle_payment_notification(message: types.Message):
    try:
        data = message.get_args().split("_")
        user_id = int(data[0])
        amount = float(data[1])
        
        async with await get_session() as session:
            user = await session.get(User, user_id)
            if user:
                user.balance += amount
                await session.commit()
                
                await message.bot.send_message(
                    user_id,
                    f"✅ Ваш баланс пополнен на {amount} USDT\n"
                    f"Текущий баланс: {user.balance} USDT"
                )
    except:
        # Логируем ошибку, но не отвечаем на сообщение
        pass 