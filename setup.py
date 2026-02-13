"""
Nano Banana Pro - Telegram Bot for AI Image Generation
"""

from setuptools import setup, find_packages

setup(
    name="nano-banana-pro",
    version="2.6.0",
    description="Telegram bot for AI image generation with Gemini 3 Pro Image",
    author="Bashirov",
    python_requires=">=3.11",
    packages=find_packages(),
    install_requires=[
        "fastapi>=0.104.0",
        "uvicorn[standard]>=0.24.0",
        "python-telegram-bot>=20.7",
        "google-generativeai>=0.3.0",
        "yookassa>=2.4.0",
        "sqlalchemy>=2.0.0",
        "asyncpg>=0.29.0",
        "redis>=5.0.0",
        "pillow>=10.0.0",
        "python-dotenv>=1.0.0",
        "pydantic>=2.0.0",
        "pydantic-settings>=2.0.0",
    ],
    entry_points={
        "console_scripts": [
            "nano-banana-bot=bot_api.main:main",
            "nano-banana-worker=worker.main:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3.11",
    ],
)
