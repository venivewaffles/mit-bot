#!/bin/bash

echo "📊 Статус системы:"

echo ""
echo "🐳 Docker контейнеры:"
docker-compose ps

echo ""
echo "🤖 Процесс бота:"
if pgrep -f "python3 -m bot.main" > /dev/null; then
    echo "✅ Бот запущен (PID: $(pgrep -f 'python3 -m bot.main'))"
    echo "📊 Активность в логах:"
    tail -5 bot.log
else
    echo "❌ Бот не запущен"
fi

echo ""
echo "🗃️ База данных:"
docker exec telegram_bot_postgres psql -U bot_user -d telegram_bot_db -c "SELECT count(*) as users_count FROM users;" 2>/dev/null || echo "Не удалось подключиться к БД"