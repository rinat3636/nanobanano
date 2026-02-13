"""
Утилиты для валидации входных данных
"""
import logging
from pathlib import Path
from typing import List, Tuple
from PIL import Image

from shared.config import MAX_IMAGE_SIZE_MB, MAX_REFERENCE_IMAGES

logger = logging.getLogger(__name__)

# Максимальная длина промпта
MAX_PROMPT_LENGTH = 1000


class ValidationError(Exception):
    """Ошибка валидации"""
    pass


def validate_prompt(prompt: str) -> Tuple[bool, str]:
    """
    Валидация промпта
    
    Args:
        prompt: Текст промпта
        
    Returns:
        (valid, error_message)
    """
    if not prompt or not prompt.strip():
        return False, "❌ Промпт не может быть пустым"
    
    if len(prompt) > MAX_PROMPT_LENGTH:
        return False, f"❌ Промпт слишком длинный! Максимум {MAX_PROMPT_LENGTH} символов (у вас {len(prompt)})"
    
    return True, ""


def validate_image_file(file_path: str) -> Tuple[bool, str]:
    """
    Валидация файла изображения
    
    Args:
        file_path: Путь к файлу
        
    Returns:
        (valid, error_message)
    """
    path = Path(file_path)
    
    # Проверка существования
    if not path.exists():
        return False, f"❌ Файл не найден: {file_path}"
    
    # Проверка размера
    file_size_mb = path.stat().st_size / (1024 * 1024)
    if file_size_mb > MAX_IMAGE_SIZE_MB:
        return False, f"❌ Изображение слишком большое! Максимум {MAX_IMAGE_SIZE_MB} MB (у вас {file_size_mb:.1f} MB)"
    
    # Проверка формата
    try:
        img = Image.open(path)
        img.verify()
    except Exception as e:
        return False, f"❌ Некорректный формат изображения: {str(e)}"
    
    return True, ""


def validate_reference_images(image_paths: List[str]) -> Tuple[bool, str]:
    """
    Валидация списка референсных изображений
    
    Args:
        image_paths: Список путей к изображениям
        
    Returns:
        (valid, error_message)
    """
    if not image_paths:
        return False, "❌ Необходимо загрузить хотя бы одно референсное изображение"
    
    if len(image_paths) > MAX_REFERENCE_IMAGES:
        return False, f"❌ Слишком много изображений! Максимум {MAX_REFERENCE_IMAGES} (у вас {len(image_paths)})"
    
    # Валидация каждого изображения
    for i, img_path in enumerate(image_paths, 1):
        valid, error = validate_image_file(img_path)
        if not valid:
            return False, f"Изображение #{i}: {error}"
    
    return True, ""


def validate_generation_settings(settings: dict) -> Tuple[bool, str]:
    """
    Валидация настроек генерации
    
    Args:
        settings: Словарь с настройками
        
    Returns:
        (valid, error_message)
    """
    # Температура
    temperature = settings.get("temperature", 1.0)
    if not isinstance(temperature, (int, float)):
        return False, "❌ Температура должна быть числом"
    
    if not (0.0 <= temperature <= 2.0):
        return False, "❌ Температура должна быть от 0.0 до 2.0"
    
    # Соотношение сторон
    aspect_ratio = settings.get("aspect_ratio", "16:9")
    valid_ratios = ["1:1", "16:9", "9:16", "4:3", "3:4"]
    if aspect_ratio not in valid_ratios:
        return False, f"❌ Некорректное соотношение сторон. Доступны: {', '.join(valid_ratios)}"
    
    # Размер изображения
    output_size = settings.get("output_image_size", "1K")
    valid_sizes = ["1K", "2K", "4K"]
    if output_size not in valid_sizes:
        return False, f"❌ Некорректный размер изображения. Доступны: {', '.join(valid_sizes)}"
    
    # Seed
    seed = settings.get("seed", -1)
    if not isinstance(seed, int):
        return False, "❌ Seed должен быть целым числом"
    
    if seed != -1 and (seed < 0 or seed > 2**32 - 1):
        return False, "❌ Seed должен быть от 0 до 4294967295 или -1 (случайный)"
    
    return True, ""


def sanitize_prompt(prompt: str) -> str:
    """
    Очистка промпта от опасных символов
    
    Args:
        prompt: Исходный промпт
        
    Returns:
        Очищенный промпт
    """
    # Удаляем управляющие символы
    sanitized = "".join(char for char in prompt if char.isprintable() or char.isspace())
    
    # Удаляем множественные пробелы
    sanitized = " ".join(sanitized.split())
    
    # Обрезаем до максимальной длины
    if len(sanitized) > MAX_PROMPT_LENGTH:
        sanitized = sanitized[:MAX_PROMPT_LENGTH]
    
    return sanitized.strip()
