"""
Health check endpoints
"""
import logging
from fastapi import APIRouter, Response
from sqlalchemy import text

from shared.database import AsyncSessionLocal
from shared.redis_client import redis_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/")
async def health_check():
    """Базовый health check"""
    return {
        "status": "healthy",
        "service": "Nano Banana Pro Bot API"
    }


@router.get("/db")
async def health_check_db(response: Response):
    """
    Health check для PostgreSQL
    """
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(text("SELECT 1"))
            result.scalar()
        
        return {
            "status": "healthy",
            "service": "postgresql"
        }
    
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        response.status_code = 503
        return {
            "status": "unhealthy",
            "service": "postgresql",
            "error": str(e)
        }


@router.get("/redis")
async def health_check_redis(response: Response):
    """
    Health check для Redis
    """
    try:
        await redis_client.ping()
        
        return {
            "status": "healthy",
            "service": "redis"
        }
    
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        response.status_code = 503
        return {
            "status": "unhealthy",
            "service": "redis",
            "error": str(e)
        }


@router.get("/all")
async def health_check_all(response: Response):
    """
    Полный health check всех сервисов
    """
    results = {
        "status": "healthy",
        "services": {}
    }
    
    # PostgreSQL
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        results["services"]["postgresql"] = "healthy"
    except Exception as e:
        results["services"]["postgresql"] = f"unhealthy: {str(e)}"
        results["status"] = "unhealthy"
    
    # Redis
    try:
        await redis_client.ping()
        results["services"]["redis"] = "healthy"
    except Exception as e:
        results["services"]["redis"] = f"unhealthy: {str(e)}"
        results["status"] = "unhealthy"
    
    # Устанавливаем код ответа
    if results["status"] == "unhealthy":
        response.status_code = 503
    
    return results
