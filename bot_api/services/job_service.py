"""
Сервис управления задачами генерации
"""
import logging
import uuid
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import Generation
from shared.redis_client import generation_queue, cache
from shared.config import (
    GENERATION_COST,
    MAX_CONCURRENT_GENERATIONS,
    MAX_QUEUE_SIZE,
    RATE_LIMIT_GENERATIONS_PER_HOUR
)
from bot_api.services.balance_service import BalanceService

logger = logging.getLogger(__name__)


class JobService:
    """Сервис управления задачами генерации"""
    
    @staticmethod
    async def create_generation_job(
        session: AsyncSession,
        user_id: int,
        prompt: str,
        reference_images: List[str],
        settings: dict
    ) -> tuple[bool, str, Optional[str]]:
        """
        Создать задачу генерации
        
        Returns:
            (success, message, generation_id)
        """
        try:
            # 1. Проверяем глобальный лимит очереди
            queue_size = await generation_queue.size()
            if queue_size >= MAX_QUEUE_SIZE:
                return False, (
                    f"⚠️ Очередь переполнена!\n\n"
                    f"В очереди: {queue_size}/{MAX_QUEUE_SIZE} задач\n"
                    f"Попробуйте позже."
                ), None
            
            # 2. Проверяем лимит параллельных генераций (ЖЁСТКИЙ: 1 на пользователя)
            active_count = await JobService.get_active_generations_count(session, user_id)
            if active_count >= MAX_CONCURRENT_GENERATIONS:
                return False, (
                    f"⚠️ У вас уже есть активная генерация!\n\n"
                    f"Дождитесь её завершения перед запуском новой."
                ), None
            
            # 3. Проверяем rate limit (генераций в час) - ТОЛЬКО ПРОВЕРКА
            rate_limit_ok, rate_message = await JobService.check_rate_limit(user_id, increment=False)
            if not rate_limit_ok:
                return False, rate_message, None
            
            # 4. Проверяем баланс
            can_generate, message = await BalanceService.can_generate(session, user_id)
            if not can_generate:
                return False, message, None
            
            # 5. Резервируем кредиты
            reserved = await BalanceService.reserve_credits(session, user_id, GENERATION_COST)
            if not reserved:
                return False, "❌ Не удалось зарезервировать кредиты", None
            
            # 6. Создаем запись генерации
            generation = Generation(
                user_id=user_id,
                prompt=prompt,
                settings=settings,
                status="pending",
                cost=GENERATION_COST
            )
            session.add(generation)
            await session.flush()
            
            generation_id = str(generation.id)
            
            # 7. Ставим задачу в очередь Redis
            job_data = {
                "job_id": generation_id,
                "generation_id": generation_id,
                "user_id": user_id,
                "prompt": prompt,
                "reference_images": reference_images,
                "settings": settings
            }
            
            await generation_queue.enqueue(job_data)
            
            generation.job_id = generation_id
            await session.commit()
            
            # 8. Увеличиваем rate limit ТОЛЬКО ПОСЛЕ успешного reserve + создания job
            await JobService.increment_rate_limit(user_id)
            
            logger.info(
                f"Created generation job for user {user_id}: "
                f"generation_id={generation_id}, prompt='{prompt[:50]}...'"
            )
            
            return True, "✅ Генерация поставлена в очередь!", generation_id
            
        except Exception as e:
            await session.rollback()
            logger.error(f"Error creating generation job for user {user_id}: {e}")
            
            # Возвращаем кредиты при ошибке
            try:
                await BalanceService.release_credits(session, user_id, GENERATION_COST)
            except:
                pass
            
            return False, f"❌ Ошибка создания задачи: {str(e)}", None
    
    @staticmethod
    async def get_active_generations_count(session: AsyncSession, user_id: int) -> int:
        """
        Получить количество активных генераций пользователя
        """
        result = await session.execute(
            select(Generation).where(
                Generation.user_id == user_id,
                Generation.status.in_(["pending", "processing"])
            )
        )
        generations = result.scalars().all()
        return len(generations)
    
    @staticmethod
    async def get_generation(session: AsyncSession, generation_id: str) -> Optional[Generation]:
        """
        Получить генерацию по ID
        """
        result = await session.execute(
            select(Generation).where(Generation.id == uuid.UUID(generation_id))
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def update_generation_status(
        session: AsyncSession,
        generation_id: str,
        status: str,
        **kwargs
    ):
        """
        Обновить статус генерации
        """
        generation = await JobService.get_generation(session, generation_id)
        
        if not generation:
            logger.error(f"Generation not found: {generation_id}")
            return
        
        generation.status = status
        
        # Обновляем дополнительные поля
        for key, value in kwargs.items():
            if hasattr(generation, key):
                setattr(generation, key, value)
        
        await session.commit()
        
        logger.info(f"Updated generation {generation_id}: status={status}")
    
    @staticmethod
    async def get_user_generations(
        session: AsyncSession,
        user_id: int,
        limit: int = 10
    ) -> List[Generation]:
        """
        Получить последние генерации пользователя
        """
        result = await session.execute(
            select(Generation)
            .where(Generation.user_id == user_id)
            .order_by(Generation.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()
    
    @staticmethod
    async def get_queue_size() -> int:
        """
        Получить размер очереди генераций
        """
        return await generation_queue.size()
    
    @staticmethod
    async def check_rate_limit(user_id: int, increment: bool = False) -> tuple[bool, str]:
        """
        Проверить rate limit для пользователя
        
        Args:
            user_id: ID пользователя
            increment: Увеличивать счётчик (только после успешного reserve)
        
        Returns:
            (is_allowed, message)
        """
        cache_key = f"rate_limit:generation:{user_id}"
        
        # Получаем текущий счётчик
        count = await cache.get(cache_key)
        
        if count is None:
            count = 0
        else:
            count = int(count)
        
        if count >= RATE_LIMIT_GENERATIONS_PER_HOUR:
            return False, (
                f"⚠️ Превышен лимит генераций!\n\n"
                f"Максимум: {RATE_LIMIT_GENERATIONS_PER_HOUR} генераций в час\n"
                f"Попробуйте позже."
            )
        
        # Увеличиваем счётчик ТОЛЬКО если increment=True
        if increment:
            await cache.set(cache_key, count + 1, ttl=3600)  # TTL 1 час
        
        return True, "OK"
    
    @staticmethod
    async def increment_rate_limit(user_id: int):
        """
        Увеличить rate limit счётчик
        Вызывается ТОЛЬКО после успешного reserve + создания job
        """
        cache_key = f"rate_limit:generation:{user_id}"
        
        count = await cache.get(cache_key)
        if count is None:
            count = 0
        else:
            count = int(count)
        
        await cache.set(cache_key, count + 1, ttl=3600)  # TTL 1 час
        logger.info(f"Incremented rate limit for user {user_id}: {count + 1}/{RATE_LIMIT_GENERATIONS_PER_HOUR}")
