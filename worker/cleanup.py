"""
Cleanup сервис для удаления старых изображений и данных
"""
import asyncio
import logging
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import AsyncSessionLocal, Generation
from shared.config import IMAGE_TTL_DAYS, CLEANUP_INTERVAL, DATA_DIR

logger = logging.getLogger(__name__)

# Директория изображений
IMAGES_DIR = DATA_DIR / "images"
REFS_DIR = DATA_DIR / "references"


class CleanupService:
    """
    Сервис очистки старых данных
    """
    
    def __init__(self, interval: int = CLEANUP_INTERVAL):
        """
        Args:
            interval: Интервал запуска cleanup в секундах
        """
        self.interval = interval
        self.running = False
    
    async def start(self):
        """Запуск cleanup сервиса"""
        self.running = True
        logger.info("🧹 Cleanup service started")
        
        while self.running:
            try:
                await self.run_cleanup()
                await asyncio.sleep(self.interval)
            
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}", exc_info=True)
                await asyncio.sleep(self.interval)
    
    def stop(self):
        """Остановка cleanup сервиса"""
        self.running = False
        logger.info("🧹 Cleanup service stopped")
    
    async def run_cleanup(self):
        """
        Запуск всех cleanup задач
        """
        logger.info("🧹 Starting cleanup...")
        
        # 1. Очистка старых изображений
        deleted_images = await self.cleanup_old_images()
        
        # 2. Очистка старых референсов
        deleted_refs = await self.cleanup_old_references()
        
        # 3. Очистка старых генераций из БД (опционально)
        # deleted_generations = await self.cleanup_old_generations()
        
        logger.info(
            f"🧹 Cleanup completed: "
            f"images={deleted_images}, refs={deleted_refs}"
        )
    
    async def cleanup_old_images(self) -> int:
        """
        Удалить изображения старше IMAGE_TTL_DAYS
        """
        try:
            deleted_count = 0
            ttl_threshold = datetime.now() - timedelta(days=IMAGE_TTL_DAYS)
            
            async with AsyncSessionLocal() as session:
                # Находим старые генерации с изображениями
                result = await session.execute(
                    select(Generation).where(
                        Generation.status == "completed",
                        Generation.completed_at < ttl_threshold,
                        Generation.image_url.isnot(None)
                    )
                )
                old_generations = result.scalars().all()
                
                for generation in old_generations:
                    try:
                        image_path = Path(generation.image_url)
                        
                        if image_path.exists():
                            image_path.unlink()
                            deleted_count += 1
                            logger.debug(f"Deleted old image: {image_path}")
                        
                        # Обнуляем image_url в БД
                        generation.image_url = None
                    
                    except Exception as e:
                        logger.error(f"Error deleting image {generation.image_url}: {e}")
                
                await session.commit()
            
            logger.info(f"🧹 Deleted {deleted_count} old images")
            return deleted_count
        
        except Exception as e:
            logger.error(f"Error in cleanup_old_images: {e}", exc_info=True)
            return 0
    
    async def cleanup_old_references(self) -> int:
        """
        Удалить старые референсные изображения (старше 7 дней)
        """
        try:
            deleted_count = 0
            ttl_threshold = datetime.now() - timedelta(days=7)
            
            if not REFS_DIR.exists():
                return 0
            
            for ref_file in REFS_DIR.iterdir():
                if not ref_file.is_file():
                    continue
                
                # Проверяем время модификации файла
                file_mtime = datetime.fromtimestamp(ref_file.stat().st_mtime)
                
                if file_mtime < ttl_threshold:
                    try:
                        ref_file.unlink()
                        deleted_count += 1
                        logger.debug(f"Deleted old reference: {ref_file}")
                    except Exception as e:
                        logger.error(f"Error deleting reference {ref_file}: {e}")
            
            logger.info(f"🧹 Deleted {deleted_count} old references")
            return deleted_count
        
        except Exception as e:
            logger.error(f"Error in cleanup_old_references: {e}", exc_info=True)
            return 0
    
    async def cleanup_old_generations(self, days: int = 90) -> int:
        """
        Удалить записи генераций старше N дней (опционально)
        
        Args:
            days: Количество дней для хранения записей
        """
        try:
            ttl_threshold = datetime.now() - timedelta(days=days)
            
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(Generation).where(
                        Generation.created_at < ttl_threshold
                    )
                )
                old_generations = result.scalars().all()
                
                for generation in old_generations:
                    await session.delete(generation)
                
                await session.commit()
                
                deleted_count = len(old_generations)
                logger.info(f"🧹 Deleted {deleted_count} old generation records")
                return deleted_count
        
        except Exception as e:
            logger.error(f"Error in cleanup_old_generations: {e}", exc_info=True)
            return 0


async def run_cleanup():
    """
    Запуск cleanup сервиса как отдельной задачи
    """
    cleanup = CleanupService()
    await cleanup.start()
