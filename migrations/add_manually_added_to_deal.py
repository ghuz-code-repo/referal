"""
Миграция: Добавление поля manually_added в ReferalDeal

При ручном добавлении договора админом он должен отображаться в списке
независимо от статуса сделки и суммы оплаты.
"""

import sys
import os

# Добавляем родительскую директорию в path для импортов
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app_with_auth_connector import app, db
from sqlalchemy import text, inspect

def migrate():
    with app.app_context():
        print("=" * 80)
        print("МИГРАЦИЯ: Добавление manually_added в referal_deal")
        print("=" * 80)
        
        # Шаг 1: Добавляем колонку manually_added
        print("\n[1/2] Добавление колонки manually_added...")
        try:
            inspector = inspect(db.engine)
            existing_columns = [col['name'] for col in inspector.get_columns('referal_deal')]
            
            if 'manually_added' not in existing_columns:
                db.session.execute(text("""
                    ALTER TABLE referal_deal
                    ADD COLUMN manually_added BOOLEAN DEFAULT FALSE
                """))
                db.session.commit()
                print("✅ Колонка manually_added добавлена")
            else:
                print("⚠️ Колонка manually_added уже существует, пропускаем")
        except Exception as e:
            error_str = str(e).lower()
            if "already exists" in error_str or "duplicate" in error_str:
                print("⚠️ Колонка manually_added уже существует, пропускаем")
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
            
            if 'manually_added' in columns:
                print("""
================================================================================
РЕЗУЛЬТАТЫ МИГРАЦИИ:
================================================================================
  ✅ Колонка manually_added успешно добавлена в referal_deal
  
  Договоры с manually_added=True будут отображаться в списке
  независимо от статуса сделки и суммы оплаты.
================================================================================
""")
            else:
                print("❌ Колонка manually_added НЕ найдена после миграции!")
        except Exception as e:
            print(f"❌ Ошибка при проверке: {e}")


if __name__ == '__main__':
    migrate()
