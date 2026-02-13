"""
Worker для обработки задач генерации изображений
"""
import asyncio
import logging
import sys
from pathlib import Path
from datetime import datetime

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from shared.database import AsyncSessionLocal, init_db
from shared.redis_client import generation_queue, close_redis
from shared.config import LOG_LEVEL, LOG_FORMAT, DATA_DIR
from worker.gemini_client import GeminiClient
from worker.tasks import process_generation
from worker.watchdog import Watchdog
from worker.cleanup import CleanupService

# Настройка логирования
logging.basicConfig(
    level=LOG_LEVEL,
    format=LOG_FORMAT,
    handlers=[
        logging.FileHandler(DATA_DIR / "logs" / "worker.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class Worker:
    """Worker для обработки задач из очереди"""
    
    def __init__(self):
        self.running = False
        self.gemini_client = GeminiClient()
        self.watchdog = Watchdog(check_interval=60)
        self.cleanup_service = CleanupService()
    
    async def start(self):
        """Запуск worker"""
        self.running = True
        logger.info("🚀 Worker started")
        
        # Инициализация БД
        await init_db()
        logger.info("✅ Database initialized")
        
        # Запуск watchdog и cleanup в фоне
        asyncio.create_task(self.watchdog.start())
        asyncio.create_task(self.cleanup_service.start())
        logger.info("✅ Watchdog and Cleanup services started")
        
        # Основной цикл обработки
        while self.running:
            try:
                # Получаем задачу из очереди (блокирующая операция с таймаутом)
                job_data = await generation_queue.dequeue(timeout=5)
                
                if job_data:
                    logger.info(f"📥 Received job: {job_data.get('job_id')}")
                    
                    # Обрабатываем задачу
                    await process_generation(
                        job_data=job_data,
                        gemini_client=self.gemini_client
                    )
                
            except KeyboardInterrupt:
                logger.info("Received interrupt signal, shutting down...")
                self.running = False
                break
            
            except Exception as e:
                logger.error(f"Error in worker loop: {e}", exc_info=True)
                await asyncio.sleep(1)
        
        # Cleanup
        await self.cleanup()
    
    async def cleanup(self):
        """Очистка ресурсов"""
        logger.info("🧹 Cleaning up...")
        
        # Останавливаем watchdog и cleanup
        self.watchdog.stop()
        self.cleanup_service.stop()
        
        await close_redis()
        logger.info("✅ Worker stopped")
    
    def stop(self):
        """Остановка worker"""
        self.running = False


async def main():
    """Главная функция"""
    worker = Worker()
    
    try:
        await worker.start()
    except KeyboardInterrupt:
        logger.info("Shutting down worker...")
        worker.stop()


if __name__ == "__main__":
    asyncio.run(main())
