"""
FastAPI приложение для Bot API
Обрабатывает Telegram webhook и ЮКасса webhook
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from shared.database import init_db, close_db
from shared.redis_client import close_redis
from shared.config import LOG_LEVEL, LOG_FORMAT, DATA_DIR
from bot_api.webhooks.telegram import router as telegram_router
from bot_api.webhooks.yookassa import router as yookassa_router
from bot_api.health import router as health_router
from bot_api.bot import setup_bot, shutdown_bot

# Настройка логирования
logging.basicConfig(
    level=LOG_LEVEL,
    format=LOG_FORMAT,
    handlers=[
        logging.FileHandler(DATA_DIR / "logs" / "bot_api.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifecycle manager для FastAPI
    """
    # Startup
    logger.info("🚀 Starting Bot API...")
    
    # Инициализация БД
    await init_db()
    logger.info("✅ Database initialized")
    
    # Настройка бота
    await setup_bot()
    logger.info("✅ Bot configured")
    
    yield
    
    # Shutdown
    logger.info("🛑 Shutting down Bot API...")
    await shutdown_bot()
    await close_db()
    await close_redis()
    logger.info("✅ Bot API stopped")


# Создание FastAPI приложения
app = FastAPI(
    title="Nano Banana Pro Bot API",
    description="Telegram bot API with payment integration",
    version="2.0.0",
    lifespan=lifespan
)


# Подключение роутеров
app.include_router(health_router)
app.include_router(telegram_router)
app.include_router(yookassa_router)


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "ok",
        "service": "Nano Banana Pro Bot API",
        "version": "2.0.0"
    }


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy"}


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Глобальный обработчик ошибок
    """
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )


if __name__ == "__main__":
    import uvicorn
    from shared.config import API_HOST, API_PORT
    
    uvicorn.run(
        "bot_api.main:app",
        host=API_HOST,
        port=API_PORT,
        reload=False,
        log_level=LOG_LEVEL.lower()
    )
