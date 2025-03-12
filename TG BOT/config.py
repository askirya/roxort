from dotenv import load_dotenv
import os

load_dotenv()

# Токен бота
BOT_TOKEN = "8129643535:AAEN6aiJ6R-dE-BXA76CgewnpEVbSys597o"

# ID администраторов
ADMIN_IDS = [1396514552]  # @ASKIRYK

# Настройки базы данных
DATABASE_URL = os.getenv('DATABASE_URL', "sqlite+aiosqlite:///database.db")

# Настройки времени аренды (в часах)
RENTAL_PERIODS = [1, 4, 12, 24]

# Комиссия платформы (5%)
PLATFORM_FEE = 0.05

# Минимальные суммы для операций
MIN_DEPOSIT = 1  # Минимальная сумма пополнения в USDT
MIN_WITHDRAWAL = 10  # Минимальная сумма вывода в USDT

# Настройки CryptoBot
CRYPTO_BOT_TOKEN = os.getenv('CRYPTO_BOT_TOKEN', "")
CRYPTO_BOT_WEBHOOK_URL = os.getenv('CRYPTO_BOT_WEBHOOK_URL', "") 