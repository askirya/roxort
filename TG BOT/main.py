import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from config import BOT_TOKEN
from database.db import init_db
from handlers import registration, common, selling, buying, disputes

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Регистрация роутеров
dp.include_router(registration.router)
dp.include_router(common.router)
dp.include_router(selling.router)
dp.include_router(buying.router)
dp.include_router(disputes.router)

# Создание основной клавиатуры
def get_main_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👤 Профиль"), KeyboardButton(text="💰 Баланс")],
            [KeyboardButton(text="📱 Продать номер"), KeyboardButton(text="🛒 Купить номер")],
            [KeyboardButton(text="💸 Вывести средства")]
        ],
        resize_keyboard=True
    )
    return keyboard

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_registered = await common.check_user_registered(message.from_user.id)
    
    if user_registered:
        await message.answer(
            "👋 Добро пожаловать в ROXORT SMS!\n\n"
            "Здесь вы можете купить или продать доступ к номеру телефона "
            "для регистрации в различных сервисах.\n\n"
            "Выберите действие в меню ниже:",
            reply_markup=common.get_main_keyboard()
        )
    else:
        await message.answer(
            "👋 Добро пожаловать в ROXORT SMS!\n\n"
            "Для использования бота необходимо пройти регистрацию.",
            reply_markup=common.get_start_keyboard()
        )

@dp.message(lambda message: message.text == "👤 Профиль")
async def show_profile(message: types.Message):
    # TODO: Добавить логику получения информации о профиле
    await message.answer(
        "📊 Ваш профиль:\n"
        "ID: {}\n"
        "Рейтинг: ⭐️ 5.0\n"
        "Продано номеров: 0\n"
        "Куплено номеров: 0\n"
        "Дата регистрации: {}"
        .format(message.from_user.id, message.date.strftime("%d.%m.%Y"))
    )

@dp.message(lambda message: message.text == "💰 Баланс")
async def show_balance(message: types.Message):
    # TODO: Добавить логику получения баланса
    await message.answer("💰 Ваш текущий баланс: 0 USDT")

async def main():
    # Инициализация базы данных
    await init_db()
    
    # Запуск бота
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main()) 