"""
Gemini API клиент для генерации изображений
"""
import logging
import asyncio
from typing import List, Optional, Tuple
from pathlib import Path
import base64
from io import BytesIO

from google import genai
from google.genai.types import GenerateImageConfig, ImageGenerationModel
from PIL import Image

from shared.config import GEMINI_API_KEY, GEMINI_MODEL, GEMINI_TIMEOUT
from worker.gemini_error_handler import get_error_handler, GeminiAPIError

logger = logging.getLogger(__name__)


class GeminiClient:
    """Клиент для работы с Gemini API"""
    
    def __init__(self, on_error_callback=None):
        self.client = genai.Client(api_key=GEMINI_API_KEY)
        self.model = GEMINI_MODEL
        self.error_handler = get_error_handler(
            max_retries=3,
            retry_delay=5,
            on_error_callback=on_error_callback
        )
        logger.info(f"Gemini client initialized with model: {self.model}")
    
    async def generate_image(
        self,
        prompt: str,
        reference_images: List[str],
        settings: dict
    ) -> Tuple[Optional[bytes], Optional[str], Optional[int]]:
        """
        Генерация изображения через Gemini API
        
        Args:
            prompt: Текстовый промпт
            reference_images: Список путей к референсным изображениям
            settings: Настройки генерации
        
        Returns:
            (image_data, error, seed)
        """
        try:
            logger.info(f"Starting generation with prompt: '{prompt[:100]}...'")
            
            # Подготовка референсных изображений
            reference_parts = []
            for img_path in reference_images:
                try:
                    img_data = await self._load_image(img_path)
                    reference_parts.append(img_data)
                except Exception as e:
                    logger.error(f"Error loading reference image {img_path}: {e}")
            
            if not reference_parts:
                return None, "NO_REFERENCE_IMAGES", None
            
            # Подготовка конфигурации
            config = GenerateImageConfig(
                number_of_images=1,
                temperature=settings.get("temperature", 1.0),
                aspect_ratio=settings.get("aspect_ratio", "16:9"),
                output_image_size=settings.get("output_image_size", "1K"),
                seed=settings.get("seed", -1) if settings.get("seed", -1) != -1 else None
            )
            
            # Формируем запрос
            contents = reference_parts + [prompt]
            
            # Генерация с retry логикой
            async def _generate():
                loop = asyncio.get_event_loop()
                return await asyncio.wait_for(
                    loop.run_in_executor(
                        None,
                        lambda: self.client.models.generate_images(
                            model=self.model,
                            prompt=contents,
                            config=config
                        )
                    ),
                    timeout=GEMINI_TIMEOUT
                )
            
            response = await self.error_handler.execute_with_retry(_generate)
            
            # Обработка ответа
            if not response or not response.generated_images:
                # Проверяем причину блокировки
                if hasattr(response, 'prompt_feedback'):
                    feedback = response.prompt_feedback
                    if hasattr(feedback, 'block_reason'):
                        return None, f"SAFETY: {feedback.block_reason}", None
                
                return None, "NO_IMAGE", None
            
            # Получаем первое изображение
            generated_image = response.generated_images[0]
            
            # Извлекаем seed
            seed = None
            if hasattr(generated_image, 'generation_seed'):
                seed = generated_image.generation_seed
            
            # Конвертируем изображение в bytes
            image_data = await self._image_to_bytes(generated_image.image)
            
            logger.info(f"Generation completed successfully. Seed: {seed}")
            
            return image_data, None, seed
            
        except asyncio.TimeoutError:
            logger.error(f"Generation timeout after {GEMINI_TIMEOUT}s")
            return None, "TIMEOUT", None
        
        except Exception as e:
            logger.error(f"Error during generation: {e}", exc_info=True)
            return None, str(e), None
    
    async def _load_image(self, image_path: str) -> bytes:
        """
        Загрузка изображения
        """
        path = Path(image_path)
        
        if not path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")
        
        # Открываем и оптимизируем изображение
        img = Image.open(path)
        
        # Конвертируем в RGB если нужно
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        # Оптимизируем размер (макс 2048x2048)
        max_size = 2048
        if img.width > max_size or img.height > max_size:
            img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
        
        # Конвертируем в bytes
        buffer = BytesIO()
        img.save(buffer, format='PNG', optimize=True)
        return buffer.getvalue()
    
    async def _image_to_bytes(self, image: Image.Image) -> bytes:
        """
        Конвертация PIL Image в bytes
        """
        buffer = BytesIO()
        image.save(buffer, format='PNG')
        return buffer.getvalue()
