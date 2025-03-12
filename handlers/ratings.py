from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from database.db import get_session
from database.models import User, Transaction, Review
from datetime import datetime, timedelta
from sqlalchemy import select, and_, or_

router = Router()

class ReviewStates(StatesGroup):
    choosing_transaction = State()
    entering_rating = State()
    entering_comment = State()

def get_rating_keyboard():
    keyboard = []
    for i in range(1, 6):
        stars = "⭐️" * i
        keyboard.append([KeyboardButton(text=f"{stars}")])
    keyboard.append([KeyboardButton(text="❌ Отмена")])
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

@router.message(F.text == "⭐️ Отзывы")
async def show_rating_menu(message: types.Message, state: FSMContext):
    async with await get_session() as session:
        user = await session.get(User, message.from_user.id)
        if not user:
            await message.answer("❌ Вы не зарегистрированы!")
            return

        # Получаем завершенные транзакции за последние 7 дней
        week_ago = datetime.utcnow() - timedelta(days=7)
        query = select(Transaction).where(
            and_(
                or_(
                    Transaction.buyer_id == user.id,
                    Transaction.seller_id == user.id
                ),
                Transaction.status == "completed",
                Transaction.completed_at >= week_ago
            )
        )
        result = await session.execute(query)
        transactions = result.scalars().all()

        if not transactions:
            await message.answer(
                "У вас нет завершенных сделок за последние 7 дней, "
                "по которым можно оставить отзыв."
            )
            return

        keyboard = []
        for tx in transactions:
            # Проверяем, не оставлен ли уже отзыв
            review_exists = await session.execute(
                select(Review).where(
                    and_(
                        Review.transaction_id == tx.id,
                        Review.reviewer_id == user.id
                    )
                )
            )
            if not await review_exists.first():
                if tx.buyer_id == user.id:
                    role = "продавцу"
                    other_user = await session.get(User, tx.seller_id)
                else:
                    role = "покупателю"
                    other_user = await session.get(User, tx.buyer_id)
                
                keyboard.append([
                    KeyboardButton(
                        text=f"📝 Оставить отзыв {role} {other_user.username or 'Аноним'} "
                        f"(ID: {tx.id})"
                    )
                ])

        if not keyboard:
            await message.answer("У вас нет сделок, по которым можно оставить отзыв.")
            return

        keyboard.append([KeyboardButton(text="👤 Мои отзывы")])
        keyboard.append([KeyboardButton(text="❌ Отмена")])

        await state.set_state(ReviewStates.choosing_transaction)
        await message.answer(
            "Выберите сделку, по которой хотите оставить отзыв:",
            reply_markup=ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
        )

@router.message(ReviewStates.choosing_transaction)
async def process_transaction_choice(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        from handlers.common import get_main_keyboard
        await message.answer("Операция отменена.", reply_markup=get_main_keyboard())
        return

    if message.text == "👤 Мои отзывы":
        await show_my_reviews(message)
        await state.clear()
        return

    try:
        tx_id = int(message.text.split("ID: ")[1].strip(")"))
    except:
        await message.answer("❌ Пожалуйста, выберите сделку из списка.")
        return

    await state.update_data(transaction_id=tx_id)
    await state.set_state(ReviewStates.entering_rating)
    await message.answer(
        "Оцените пользователя от 1 до 5 звезд:",
        reply_markup=get_rating_keyboard()
    )

@router.message(ReviewStates.entering_rating)
async def process_rating(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        from handlers.common import get_main_keyboard
        await message.answer("Операция отменена.", reply_markup=get_main_keyboard())
        return

    rating = len(message.text.strip())  # Считаем количество звезд
    if rating < 1 or rating > 5:
        await message.answer("❌ Пожалуйста, выберите оценку от 1 до 5 звезд.")
        return

    await state.update_data(rating=rating)
    await state.set_state(ReviewStates.entering_comment)
    await message.answer(
        "Напишите комментарий к отзыву:",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="❌ Отмена")]],
            resize_keyboard=True
        )
    )

@router.message(ReviewStates.entering_comment)
async def process_comment(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        from handlers.common import get_main_keyboard
        await message.answer("Операция отменена.", reply_markup=get_main_keyboard())
        return

    data = await state.get_data()
    tx_id = data['transaction_id']
    rating = data['rating']

    async with await get_session() as session:
        transaction = await session.get(Transaction, tx_id)
        if not transaction:
            await message.answer("❌ Сделка не найдена.")
            await state.clear()
            return

        # Определяем, кто кому оставляет отзыв
        if transaction.buyer_id == message.from_user.id:
            reviewer_id = transaction.buyer_id
            reviewed_id = transaction.seller_id
        else:
            reviewer_id = transaction.seller_id
            reviewed_id = transaction.buyer_id

        # Создаем отзыв
        review = Review(
            transaction_id=tx_id,
            reviewer_id=reviewer_id,
            reviewed_id=reviewed_id,
            rating=rating,
            comment=message.text,
            created_at=datetime.utcnow()
        )
        session.add(review)

        # Обновляем рейтинг пользователя
        reviewed_user = await session.get(User, reviewed_id)
        reviews_query = select(Review).where(Review.reviewed_id == reviewed_id)
        reviews_result = await session.execute(reviews_query)
        reviews = reviews_result.scalars().all()

        total_rating = sum(r.rating for r in reviews) + rating
        new_rating = total_rating / (len(reviews) + 1)
        reviewed_user.rating = round(new_rating, 1)

        await session.commit()

        await message.answer(
            "✅ Отзыв успешно оставлен!\n"
            f"Оценка: {'⭐️' * rating}\n"
            f"Комментарий: {message.text}",
            reply_markup=get_main_keyboard()
        )

    await state.clear()

@router.message(F.text == "👤 Мои отзывы")
async def show_my_reviews(message: types.Message):
    async with await get_session() as session:
        # Получаем отзывы о пользователе
        reviews_query = select(Review).where(Review.reviewed_id == message.from_user.id)
        reviews_result = await session.execute(reviews_query)
        reviews = reviews_result.scalars().all()

        if not reviews:
            await message.answer("У вас пока нет отзывов.")
            return

        for review in reviews:
            reviewer = await session.get(User, review.reviewer_id)
            transaction = await session.get(Transaction, review.transaction_id)
            
            await message.answer(
                f"⭐️ Отзыв от {reviewer.username or 'Аноним'}\n\n"
                f"Оценка: {'⭐️' * review.rating}\n"
                f"Комментарий: {review.comment}\n"
                f"Дата: {review.created_at.strftime('%d.%m.%Y %H:%M')}\n"
                f"Сумма сделки: {transaction.amount} USDT"
            ) 