# ⚡ Быстрый деплой на Railway - Шпаргалка

## 🎯 За 10 минут

### 1. Создать проект
```
railway.app → New Project → Empty Project
```

### 2. Добавить БД
```
+ New → Database → PostgreSQL
+ New → Database → Redis
```

### 3. Добавить Bot API
```
+ New → GitHub Repo → nano-banana-pro
```

**Settings:**
- Service Name: `Bot API`
- Start Command: `python -m bot_api.main`
- Watch Paths: `/bot_api/**,/shared/**`
- Generate Domain: ✅

**Variables:**
```bash
TELEGRAM_BOT_TOKEN=...
TELEGRAM_WEBHOOK_URL=https://YOUR_DOMAIN.railway.app/webhook/telegram
GEMINI_API_KEY=...
DATABASE_URL=${{Postgres.DATABASE_URL}}
REDIS_URL=${{Redis.REDIS_URL}}
YOOKASSA_SHOP_ID=...
YOOKASSA_SECRET_KEY=...
ADMIN_IDS=123456789,987654321
PORT=${{PORT}}
```

### 4. Добавить Worker
```
+ New → GitHub Repo → nano-banana-pro (тот же!)
```

**Settings:**
- Service Name: `Worker`
- Start Command: `python -m worker.main`
- Watch Paths: `/worker/**,/shared/**`
- Generate Domain: ❌

**Variables:** Скопировать из Bot API

### 5. Настроить webhooks

**Telegram:**
```bash
curl -X POST "https://api.telegram.org/bot<TOKEN>/setWebhook" \
  -d "url=https://YOUR_DOMAIN.railway.app/webhook/telegram"
```

**ЮКасса:**
- Личный кабинет → HTTP-уведомления
- URL: `https://YOUR_DOMAIN.railway.app/webhook/yookassa`
- События: `payment.succeeded`

### 6. Проверить
```bash
# Health check
curl https://YOUR_DOMAIN.railway.app/health/all

# Telegram
/start в боте
```

## ✅ Готово!

Полная инструкция: [RAILWAY_DEPLOY_V3.md](./RAILWAY_DEPLOY_V3.md)
