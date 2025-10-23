"""
Скрипт миграции: Добавление полей недвижимости в MacroDeal

Добавляет поля:
- rooms (комнатность)
- entrance (подъезд)
- floor (этаж квартиры)
- max_floor (этажность дома)

Безопасно для существующих данных - все поля nullable=True
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask
from models import db

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('SQLALCHEMY_DATABASE_URI')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

def migrate():
    with app.app_context():
        print("🔄 Начинаем миграцию: добавление полей недвижимости...")
        
        try:
            # Добавляем новые колонки в таблицу macro_deal
            with db.engine.connect() as conn:
                # Проверяем существование колонок перед добавлением
                result = conn.execute(db.text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name='macro_deal' AND column_name IN ('rooms', 'entrance', 'floor', 'max_floor')
                """))
                existing_columns = [row[0] for row in result]
                
                if 'rooms' not in existing_columns:
                    print("  ➕ Добавляем колонку 'rooms'...")
                    conn.execute(db.text("ALTER TABLE macro_deal ADD COLUMN rooms INTEGER"))
                    conn.commit()
                else:
                    print("  ✓ Колонка 'rooms' уже существует")
                
                if 'entrance' not in existing_columns:
                    print("  ➕ Добавляем колонку 'entrance'...")
                    conn.execute(db.text("ALTER TABLE macro_deal ADD COLUMN entrance VARCHAR(50)"))
                    conn.commit()
                else:
                    print("  ✓ Колонка 'entrance' уже существует")
                
                if 'floor' not in existing_columns:
                    print("  ➕ Добавляем колонку 'floor'...")
                    conn.execute(db.text("ALTER TABLE macro_deal ADD COLUMN floor INTEGER"))
                    conn.commit()
                else:
                    print("  ✓ Колонка 'floor' уже существует")
                
                if 'max_floor' not in existing_columns:
                    print("  ➕ Добавляем колонку 'max_floor'...")
                    conn.execute(db.text("ALTER TABLE macro_deal ADD COLUMN max_floor INTEGER"))
                    conn.commit()
                else:
                    print("  ✓ Колонка 'max_floor' уже существует")
            
            print("\n✅ Миграция завершена успешно!")
            print("\n📋 Следующие шаги:")
            print("   1. Перезапустите сервис: docker compose restart")
            print("   2. Запустите синхронизацию данных для заполнения новых полей")
            print("   3. Обновите docx шаблоны с новыми метками: {rooms}, {entrance}, {floor}, {max_floor}")
            
        except Exception as e:
            print(f"\n❌ Ошибка миграции: {e}")
            raise

if __name__ == '__main__':
    migrate()
