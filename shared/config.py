"""
Конфигурация приложения
"""
import os
from pathlib import Path
from typing import List

# Базовые пути
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_WEBHOOK_URL = os.getenv("TELEGRAM_WEBHOOK_URL", "")  # https://your-domain.com/webhook/telegram
TELEGRAM_WEBHOOK_SECRET = os.getenv("TELEGRAM_WEBHOOK_SECRET", "")

# Gemini API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_TIMEOUT = int(os.getenv("GEMINI_TIMEOUT", "600"))
GEMINI_MODEL = "gemini-3.0-pro-image"

# PostgreSQL
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://localhost/nano_banana")
# Railway автоматически предоставляет DATABASE_URL

# Redis
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
# Railway автоматически предоставляет REDIS_URL

# ЮКасса
YOOKASSA_SHOP_ID = os.getenv("YOOKASSA_SHOP_ID", "")
YOOKASSA_SECRET_KEY = os.getenv("YOOKASSA_SECRET_KEY", "")
YOOKASSA_WEBHOOK_SECRET = os.getenv("YOOKASSA_WEBHOOK_SECRET", "")
YOOKASSA_WEBHOOK_URL = os.getenv("YOOKASSA_WEBHOOK_URL", "")  # https://your-domain.com/webhook/yookassa

# Монетизация
GENERATION_COST = 10  # кредитов за генерацию
CREDIT_TO_RUB = 1  # 1 кредит = 1 рубль

# Пакеты пополнения
TOPUP_PACKAGES = [
    {"rub": 100, "credits": 100, "label": "100₽ → 100 кредитов"},
    {"rub": 200, "credits": 200, "label": "200₽ → 200 кредитов"},
    {"rub": 300, "credits": 300, "label": "300₽ → 300 кредитов"},
]

# Лимиты
MAX_REFERENCE_IMAGES = 5
MAX_IMAGE_SIZE_MB = 4
MAX_CONCURRENT_GENERATIONS = 1  # ЖЁСТКИЙ ЛИМИТ: 1 активная генерация на пользователя
MAX_QUEUE_SIZE = 100  # Глобальный лимит очереди
GENERATION_TIMEOUT = 600  # 10 минут - таймаут для зависших генераций

# TTL изображений
IMAGE_TTL_DAYS = 30  # Удалять изображения старше 30 дней
CLEANUP_INTERVAL = 3600  # Запускать cleanup каждый час (секунды)

# Rate limiting
RATE_LIMIT_GENERATIONS_PER_HOUR = 10  # Максимум генераций в час на пользователя
RATE_LIMIT_TOPUP_PER_HOUR = 5  # Максимум попыток пополнения в час

# Реферальные лимиты (анти-абуз)
REFERRAL_REWARD_CAP_PER_DAY = 10  # Максимум рефералов с наградой в сутки
REFERRAL_ACTIVATION_REQUIRED = True  # Реферер получает награду только после активации реферала

# Поддержка
SUPPORT_USERNAME = "Bashirov1111"
SUPPORT_URL = f"https://t.me/{SUPPORT_USERNAME}"

# Администраторы (список Telegram ID)
ADMIN_IDS_STR = os.getenv("ADMIN_IDS", "")  # Через запятую: "123456789,987654321"
ADMIN_IDS: List[int] = [int(id.strip()) for id in ADMIN_IDS_STR.split(",") if id.strip()]

# Валидация ADMIN_IDS
if not ADMIN_IDS:
    import sys
    print("⚠️ WARNING: ADMIN_IDS is empty! Admin panel will be inaccessible.")
    print("🔧 Set ADMIN_IDS environment variable: ADMIN_IDS='123456789,987654321'")
    if os.getenv("REQUIRE_ADMIN_IDS", "false").lower() == "true":
        print("❌ REQUIRE_ADMIN_IDS=true, exiting...")
        sys.exit(1)

# API Server
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("PORT", "8080"))  # Railway использует PORT

# Логирование
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# S3 (опционально, для хранения изображений)
S3_BUCKET = os.getenv("S3_BUCKET", "")
S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY", "")
S3_SECRET_KEY = os.getenv("S3_SECRET_KEY", "")
S3_ENDPOINT = os.getenv("S3_ENDPOINT", "")

# Создание директорий
DATA_DIR.mkdir(exist_ok=True)
(DATA_DIR / "images").mkdir(exist_ok=True)
(DATA_DIR / "logs").mkdir(exist_ok=True)
