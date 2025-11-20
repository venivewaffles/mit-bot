#!/bin/bash
set -e

echo "🐘 Инициализация PostgreSQL..."

# Выводим сообщение в консоль контейнера (не в SQL!)
echo "✅ База данных '$POSTGRES_DB' готова к работе!"

# Выполняем только SQL команды
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    -- Создаем расширение для UUID если нужно
    CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
    
    -- Создаем дополнительную схему если нужно
    -- CREATE SCHEMA IF NOT EXISTS bot_schema;
    
    -- Даем права если нужно
    -- GRANT ALL ON SCHEMA bot_schema TO $POSTGRES_USER;
EOSQL

echo "✅ Инициализация базы данных завершена!"