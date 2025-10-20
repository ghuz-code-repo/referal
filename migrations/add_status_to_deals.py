"""
Миграция: Добавление статусов к договорам
Теперь статусы применяются к каждому договору отдельно, а не к рефералу в целом
"""

from datetime import datetime
import sys
import os

# Добавляем родительскую директорию в path для импортов
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from models import ReferalDeal
from sqlalchemy import text

def migrate():
    with app.app_context():
        print("=" * 80)
        print("МИГРАЦИЯ: Добавление status_id к ReferalDeal")
        print("=" * 80)
        
        # Шаг 1: Добавляем колонку status_id
        print("\n[1/3] Добавление колонки status_id...")
        try:
            db.session.execute(text("""
                ALTER TABLE referal_deal
                ADD COLUMN status_id INTEGER DEFAULT 0
            """))
            db.session.commit()
            print("✅ Колонка status_id добавлена")
        except Exception as e:
            if "duplicate column name" in str(e).lower() or "already exists" in str(e).lower():
                print("⚠️ Колонка status_id уже существует, пропускаем")
                db.session.rollback()
            else:
                print(f"❌ Ошибка при добавлении колонки: {e}")
                db.session.rollback()
                raise

        # Шаг 2: Проставляем статусы договорам на основе статусов рефералов
        print("\n[2/3] Миграция статусов с рефералов на договоры...")
        try:
            # Получаем все договоры с их рефералами
            deals = ReferalDeal.query.all()
            updated = 0
            
            for referal_deal in deals:
                if referal_deal.referal and referal_deal.referal.status_id:
                    # Копируем статус с реферала на договор
                    referal_deal.status_id = referal_deal.referal.status_id
                    updated += 1
            
            db.session.commit()
            print(f"✅ Обновлено статусов: {updated}")
        except Exception as e:
            print(f"❌ Ошибка при миграции статусов: {e}")
            db.session.rollback()
            raise
        
        # Шаг 3: Проверка
        print("\n[3/3] Финальная проверка...")
        try:
            total_deals = ReferalDeal.query.count()
            deals_with_status = ReferalDeal.query.filter(ReferalDeal.status_id != None).count()
            
            print(f"""
================================================================================
РЕЗУЛЬТАТЫ МИГРАЦИИ:
================================================================================
  Всего договоров: {total_deals}
  Договоров со статусом: {deals_with_status}
  Договоров без статуса: {total_deals - deals_with_status}
================================================================================
""")
            
            print("✅ МИГРАЦИЯ ЗАВЕРШЕНА УСПЕШНО!")
            
        except Exception as e:
            print(f"❌ Ошибка при проверке: {e}")
            raise

if __name__ == '__main__':
    migrate()
