"""
Миграция: Добавление поля rejection_reason в ReferalDeal

При отказе в выплате необходимо указывать причину отказа.
"""

import sys
import os

# Добавляем родительскую директорию в path для импортов
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from sqlalchemy import text, inspect

def migrate():
    with app.app_context():
        print("=" * 80)
        print("МИГРАЦИЯ: Добавление rejection_reason в referal_deal")
        print("=" * 80)
        
        # Шаг 1: Добавляем колонку rejection_reason
        print("\n[1/2] Добавление колонки rejection_reason...")
        try:
            # Проверяем существование колонки через inspector (универсально для всех БД)
            inspector = inspect(db.engine)
            existing_columns = [col['name'] for col in inspector.get_columns('referal_deal')]
            
            if 'rejection_reason' not in existing_columns:
                db.session.execute(text("""
                    ALTER TABLE referal_deal
                    ADD COLUMN rejection_reason TEXT
                """))
                db.session.commit()
                print("✅ Колонка rejection_reason добавлена")
            else:
                print("⚠️ Колонка rejection_reason уже существует, пропускаем")
        except Exception as e:
            # PostgreSQL использует другой текст ошибки
            error_str = str(e).lower()
            if "already exists" in error_str or "duplicate" in error_str or "column" in error_str and "rejection_reason" in error_str:
                print("⚠️ Колонка rejection_reason уже существует, пропускаем")
                db.session.rollback()
            else:
                print(f"❌ Ошибка при добавлении колонки: {e}")
                db.session.rollback()
                raise

        # Шаг 2: Проверка
        print("\n[2/2] Финальная проверка...")
        try:
            inspector = inspect(db.engine)
            columns = [col['name'] for col in inspector.get_columns('referal_deal')]
            
            if 'rejection_reason' in columns:
                print(f"""
================================================================================
РЕЗУЛЬТАТЫ МИГРАЦИИ:
================================================================================
  ✅ Колонка rejection_reason успешно добавлена в referal_deal
  
  Теперь при отказе (status_id = 500) будет обязательно указывать причину.
================================================================================
""")
                print("✅ МИГРАЦИЯ ЗАВЕРШЕНА УСПЕШНО!")
                return True
            else:
                print("❌ Колонка rejection_reason не найдена после миграции")
                return False
            
        except Exception as e:
            print(f"❌ Ошибка при проверке: {e}")
            raise

if __name__ == '__main__':
    print("\n" + "=" * 80)
    print("СКРИПТ МИГРАЦИИ: Добавление rejection_reason в ReferalDeal")
    print("=" * 80)
    print("\nЭтот скрипт добавит поле rejection_reason в таблицу referal_deal")
    print("для хранения причины отказа при установке status_id = 500")
    print("\n" + "=" * 80)
    
    response = input("\nПродолжить миграцию? (yes/no): ").lower().strip()
    
    if response == 'yes' or response == 'y':
        success = migrate()
        if success:
            print("\n✅ Миграция успешно завершена!")
            sys.exit(0)
        else:
            print("\n❌ Миграция завершилась с ошибками")
            sys.exit(1)
    else:
        print("\n❌ Миграция отменена пользователем")
        sys.exit(0)
