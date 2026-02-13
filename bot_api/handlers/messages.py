"""
Обработчики сообщений (фото, текст)
"""
import logging
from pathlib import Path
from telegram import Update
from telegram.ext import ContextTypes

from shared.config import DATA_DIR, MAX_REFERENCE_IMAGES

logger = logging.getLogger(__name__)

# Директория для сохранения референсных изображений
REFS_DIR = DATA_DIR / "references"
REFS_DIR.mkdir(exist_ok=True)


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработка загруженных фото (референсные изображения)
    """
    user_id = update.effective_user.id
    
    # Инициализируем данные пользователя
    if "user_data" not in context.bot_data:
        context.bot_data["user_data"] = {}
    
    if user_id not in context.bot_data["user_data"]:
        context.bot_data["user_data"][user_id] = {
            "reference_images": [],
            "prompt": None,
            "settings": {
                "temperature": 1.0,
                "aspect_ratio": "16:9",
                "output_image_size": "1K",
                "seed": -1
            }
        }
    
    user_data = context.bot_data["user_data"][user_id]
    reference_images = user_data.get("reference_images", [])
    
    # Проверяем лимит
    if len(reference_images) >= MAX_REFERENCE_IMAGES:
        await update.message.reply_text(
            f"⚠️ Достигнут лимит референсных изображений ({MAX_REFERENCE_IMAGES})!\n\n"
            f"Используйте /clear для очистки."
        )
        return
    
    # Скачиваем фото
    photo = update.message.photo[-1]  # Берем самое большое разрешение
    file = await context.bot.get_file(photo.file_id)
    
    # Сохраняем локально
    filename = f"{user_id}_{photo.file_id}.jpg"
    file_path = REFS_DIR / filename
    await file.download_to_drive(file_path)
    
    # Добавляем в список референсов
    reference_images.append(str(file_path))
    user_data["reference_images"] = reference_images
    
    logger.info(f"User {user_id} uploaded reference image: {filename}")
    
    await update.message.reply_text(
        f"✅ Референсное изображение добавлено!\n\n"
        f"📊 Всего: {len(reference_images)}/{MAX_REFERENCE_IMAGES}\n\n"
        f"💡 Загрузите еще фото или установите промпт: /prompt ваш текст"
    )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработка текстовых сообщений (автоматическая установка промпта)
    """
    user_id = update.effective_user.id
    text = update.message.text
    
    # Инициализируем данные пользователя
    if "user_data" not in context.bot_data:
        context.bot_data["user_data"] = {}
    
    if user_id not in context.bot_data["user_data"]:
        context.bot_data["user_data"][user_id] = {
            "reference_images": [],
            "prompt": None,
            "settings": {
                "temperature": 1.0,
                "aspect_ratio": "16:9",
                "output_image_size": "1K",
                "seed": -1
            }
        }
    
    # Устанавливаем промпт
    context.bot_data["user_data"][user_id]["prompt"] = text
    
    logger.info(f"User {user_id} set prompt: {text[:50]}...")
    
    await update.message.reply_text(
        f"✅ Промпт установлен!\n\n"
        f"📝 {text}\n\n"
        f"💡 Загрузите референсные изображения и используйте /generate"
    )
