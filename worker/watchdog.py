"""
Watchdog для мониторинга и очистки зависших генераций
"""
import asyncio
import logging
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import AsyncSessionLocal, Generation
from shared.config import GENERATION_TIMEOUT
from bot_api.services.balance_service import BalanceService

logger = logging.getLogger(__name__)


class Watchdog:
    """
    Watchdog для мониторинга зависших генераций
    Проверяет генерации в статусе 'processing' и завершает их при таймауте
    """
    
    def __init__(self, check_interval: int = 60):
        """
        Args:
            check_interval: Интервал проверки в секундах (по умолчанию 60)
        """
        self.check_interval = check_interval
        self.running = False
    
    async def start(self):
        """Запуск watchdog"""
        self.running = True
        logger.info("🐕 Watchdog started")
        
        while self.running:
            try:
                await self.check_stuck_generations()
                await asyncio.sleep(self.check_interval)
            
            except Exception as e:
                logger.error(f"Error in watchdog loop: {e}", exc_info=True)
                await asyncio.sleep(self.check_interval)
    
    def stop(self):
        """Остановка watchdog"""
        self.running = False
        logger.info("🐕 Watchdog stopped")
    
    async def check_stuck_generations(self):
        """
        Проверить и очистить зависшие генерации
        """
        async with AsyncSessionLocal() as session:
            try:
                # Находим генерации в статусе 'processing' старше GENERATION_TIMEOUT
                timeout_threshold = datetime.now() - timedelta(seconds=GENERATION_TIMEOUT)
                
                result = await session.execute(
                    select(Generation).where(
                        Generation.status == "processing",
                        Generation.started_at < timeout_threshold
                    )
                )
                stuck_generations = result.scalars().all()
                
                if not stuck_generations:
                    return
                
                logger.warning(f"Found {len(stuck_generations)} stuck generations")
                
                # Обрабатываем каждую зависшую генерацию
                for generation in stuck_generations:
                    await self.handle_stuck_generation(session, generation)
                
                await session.commit()
                
            except Exception as e:
                await session.rollback()
                logger.error(f"Error checking stuck generations: {e}", exc_info=True)
    
    async def handle_stuck_generation(self, session: AsyncSession, generation: Generation):
        """
        Обработать зависшую генерацию
        """
        try:
            logger.warning(
                f"Handling stuck generation: {generation.id} "
                f"(user={generation.user_id}, started={generation.started_at})"
            )
            
            # Обновляем статус на 'failed'
            generation.status = "failed"
            generation.error = f"TIMEOUT: Generation exceeded {GENERATION_TIMEOUT}s limit"
            generation.completed_at = datetime.now()
            
            # Возвращаем кредиты пользователю
            await BalanceService.release_credits(
                session=session,
                user_id=generation.user_id,
                amount=generation.cost
            )
            
            logger.info(
                f"Released {generation.cost} credits for stuck generation {generation.id}"
            )
            
            # Уведомляем пользователя
            try:
                from bot_api.bot import send_message
                await send_message(
                    generation.user_id,
                    f"⏱ Генерация превысила лимит времени ({GENERATION_TIMEOUT // 60} минут)\n\n"
                    f"Статус: Отменена\n"
                    f"💰 Кредиты возвращены: {generation.cost}\n\n"
                    f"Попробуйте:\n"
                    f"• Упростить промпт\n"
                    f"• Использовать меньше референсов\n"
                    f"• Попробовать позже"
                )
            except Exception as e:
                logger.error(f"Error sending notification for stuck generation: {e}")
        
        except Exception as e:
            logger.error(f"Error handling stuck generation {generation.id}: {e}", exc_info=True)


async def run_watchdog():
    """
    Запуск watchdog как отдельной задачи
    """
    watchdog = Watchdog(check_interval=60)
    await watchdog.start()
