"""
Задачи обработки генераций
"""
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict
import uuid

from shared.database import AsyncSessionLocal, Generation
from shared.config import GENERATION_COST, DATA_DIR
from bot_api.services.balance_service import BalanceService
from worker.gemini_client import GeminiClient

logger = logging.getLogger(__name__)

# Директория для сохранения изображений
IMAGES_DIR = DATA_DIR / "images"
IMAGES_DIR.mkdir(exist_ok=True)


async def process_generation(job_data: Dict, gemini_client: GeminiClient):
    """
    Обработка задачи генерации изображения
    """
    generation_id = job_data.get("generation_id")
    user_id = job_data.get("user_id")
    prompt = job_data.get("prompt")
    reference_images = job_data.get("reference_images", [])
    settings = job_data.get("settings", {})
    
    logger.info(f"Processing generation {generation_id} for user {user_id}")
    
    async with AsyncSessionLocal() as session:
        try:
            # Получаем генерацию из БД
            generation = await session.get(Generation, uuid.UUID(generation_id))
            
            if not generation:
                logger.error(f"Generation not found: {generation_id}")
                return
            
            # Обновляем статус на "processing"
            generation.status = "processing"
            generation.started_at = datetime.now()
            await session.commit()
            
            # Уведомляем пользователя о начале
            try:
                from bot_api.bot import send_message
                await send_message(
                    user_id,
                    "🎨 Генерация началась...\n"
                    "Это может занять до 10 минут."
                )
            except Exception as e:
                logger.error(f"Error sending start notification: {e}")
            
            # Генерация через Gemini
            image_data, error, seed = await gemini_client.generate_image(
                prompt=prompt,
                reference_images=reference_images,
                settings=settings
            )
            
            if error:
                # Ошибка генерации - возвращаем кредиты
                await handle_generation_error(
                    session=session,
                    generation=generation,
                    user_id=user_id,
                    error=error
                )
            else:
                # Успешная генерация - списываем кредиты
                await handle_generation_success(
                    session=session,
                    generation=generation,
                    user_id=user_id,
                    image_data=image_data,
                    seed=seed
                )
        
        except Exception as e:
            logger.error(f"Critical error processing generation {generation_id}: {e}", exc_info=True)
            
            # Возвращаем кредиты при критической ошибке
            try:
                await BalanceService.release_credits(session, user_id, GENERATION_COST)
                
                generation = await session.get(Generation, uuid.UUID(generation_id))
                if generation:
                    generation.status = "failed"
                    generation.error = str(e)
                    generation.completed_at = datetime.now()
                    await session.commit()
                
                from bot_api.bot import send_message
                await send_message(
                    user_id,
                    f"❌ Критическая ошибка генерации:\n{str(e)}\n\n"
                    f"Кредиты возвращены на баланс."
                )
            except Exception as cleanup_error:
                logger.error(f"Error during cleanup: {cleanup_error}")


async def handle_generation_error(
    session,
    generation: Generation,
    user_id: int,
    error: str
):
    """
    Обработка ошибки генерации
    """
    logger.warning(f"Generation {generation.id} failed: {error}")
    
    # Возвращаем кредиты
    await BalanceService.release_credits(session, user_id, GENERATION_COST)
    
    # Обновляем статус генерации
    generation.status = "failed"
    generation.error = error
    generation.completed_at = datetime.now()
    await session.commit()
    
    # Формируем сообщение об ошибке
    error_messages = {
        "SAFETY": "⚠️ Запрос заблокирован фильтром безопасности.\n\nПопробуйте изменить промпт.",
        "NO_IMAGE": "⚠️ Модель не смогла сгенерировать изображение.\n\nПопробуйте:\n- Упростить промпт\n- Использовать другие референсы\n- Изменить настройки",
        "TIMEOUT": "⏱ Превышено время ожидания генерации.\n\nПопробуйте позже.",
        "NO_REFERENCE_IMAGES": "❌ Не удалось загрузить референсные изображения.\n\nПроверьте качество загруженных фото."
    }
    
    error_msg = error_messages.get(error, f"❌ Ошибка: {error}")
    
    # Отправляем уведомление пользователю
    try:
        from bot_api.bot import send_message
        await send_message(
            user_id,
            f"{error_msg}\n\n💰 Кредиты возвращены на баланс."
        )
    except Exception as e:
        logger.error(f"Error sending error notification: {e}")


async def handle_generation_success(
    session,
    generation: Generation,
    user_id: int,
    image_data: bytes,
    seed: int
):
    """
    Обработка успешной генерации
    """
    logger.info(f"Generation {generation.id} completed successfully")
    
    # Списываем кредиты
    await BalanceService.commit_credits(
        session=session,
        user_id=user_id,
        amount=GENERATION_COST,
        reference_id=generation.id
    )
    
    # Сохраняем изображение
    image_filename = f"{generation.id}.png"
    image_path = IMAGES_DIR / image_filename
    
    with open(image_path, "wb") as f:
        f.write(image_data)
    
    # Обновляем генерацию
    generation.status = "completed"
    generation.image_url = str(image_path)
    generation.seed = seed
    generation.completed_at = datetime.now()
    await session.commit()
    
    # Получаем баланс
    balance_info = await BalanceService.get_balance(session, user_id)
    
    # Активируем реферала (если это первая генерация)
    try:
        from bot_api.services.referral_service_v2 import ReferralServiceV2
        await ReferralServiceV2.activate_referral(session, user_id)
    except Exception as e:
        logger.error(f"Error activating referral: {e}")
    
    # Отправляем результат пользователю (ВСЕГДА КАК ФАЙЛ)
    try:
        from bot_api.bot import send_document
        await send_document(
            user_id,
            image_path,
            caption=(
                f"✅ Изображение сгенерировано!\n\n"
                f"🎲 Seed: {seed}\n"
                f"💰 Списано: {GENERATION_COST} кредитов\n"
                f"💳 Остаток: {balance_info['credits_available']} кредитов"
            ),
            filename=f"nano_banana_{generation.id}.png"
        )
    except Exception as e:
        logger.error(f"Error sending result to user: {e}")
