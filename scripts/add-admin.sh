#!/bin/bash

# Скрипт для добавления администратора

if [ -z "$1" ]; then
    echo "❌ Укажите ID пользователя: ./add-admin.sh <user_id>"
    exit 1
fi

USER_ID=$1

echo "👮 Добавление администратора (ID: $USER_ID)..."

source venv/bin/activate

python3 -c "
import os
from dotenv import load_dotenv
from bot.database import Database

load_dotenv()

db = Database()
db.init_db()

# Добавляем админа
try:
    success = db.add_admin($USER_ID, 'admin')
    if success:
        print(f'✅ Пользователь {success} добавлен в администраторы!')
    else:
        print('❌ Ошибка при добавлении администратора')
except Exception as e:
    print(f'❌ Ошибка: {e}')
"

echo ""
echo "📋 Текущие администраторы:"
python3 -c "
from bot.database import Database
db = Database()
try:
    admins = db.get_all_admins()
    if admins:
        for admin in admins:
            print(f'👮 ID: {admin.user_id}, Username: {admin.username}')
    else:
        print('ℹ️  Администраторы не найдены')
except Exception as e:
    print(f'❌ Ошибка при получении списка администраторов: {e}')
"