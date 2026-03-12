"""
Миграция: Referal может иметь много договоров

Изменения:
- Добавляет created_at и days_window в существующие Referal записи
- Создает таблицу ReferalDeal для связей many-to-many
- Мигрирует существующие связи referal-deal в новую таблицу
- Сохраняет информацию о выплатах для каждого договора отдельно

Использование:
    python migrations/migrate_to_many_deals.py
"""

from datetime import datetime, timedelta
import sys
import os

# Добавляем родительскую директорию в path для импортов
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from models import Referal, MacroDeal, ReferalDeal, User
from services import referal_service


def migrate():
    """Выполняет миграцию данных к новой структуре many-to-many"""
    
    with app.app_context():
        print("=" * 80)
        print("НАЧАЛО МИГРАЦИИ: Referal Many-to-Many Deals")
        print("=" * 80)
        
        # ===== ШАГ 0: Добавление новых колонок в существующие таблицы =====
        print("\n[0/5] Добавление новых колонок в существующие таблицы...")
        
        from sqlalchemy import text
        
        # Список колонок для добавления
        columns_to_add = [
            # Для таблицы referal
            ("referal", "created_at", "TIMESTAMP"),
            ("referal", "days_window", "INTEGER", "DEFAULT 45"),
            # Для таблицы macro_contact
            ("macro_contact", "first_interaction_date", "TIMESTAMP", None),
            ("macro_contact", "last_interaction_date", "TIMESTAMP", None),
            ("macro_contact", "date_modified", "TIMESTAMP", None),
            ("macro_contact", "last_deal_date", "DATE", None),
            # Для таблицы macro_deal  
            ("macro_deal", "payment_calculated", "BOOLEAN", "DEFAULT FALSE"),
            ("macro_deal", "withdrawal_amount", "INTEGER", "DEFAULT 0"),
        ]
        
        # Используем SQLAlchemy Inspector для проверки колонок (работает с любой БД)
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        
        for column_info in columns_to_add:
            table_name = column_info[0]
            column_name = column_info[1]
            column_type = column_info[2]
            column_default = column_info[3] if len(column_info) > 3 else None
            
            try:
                # Проверяем существует ли колонка через inspector (универсально для всех БД)
                existing_columns = [col['name'] for col in inspector.get_columns(table_name)]
                
                if column_name not in existing_columns:
                    print(f"  Добавляем колонку {table_name}.{column_name}...")
                    # PostgreSQL требует отдельных ALTER TABLE для каждой колонки
                    alter_query = f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"
                    if column_default:
                        alter_query += f" {column_default}"
                    db.session.execute(text(alter_query))
                    db.session.commit()
                    print(f"  ✅ Колонка {table_name}.{column_name} добавлена")
                else:
                    print(f"  ⏭️  Колонка {table_name}.{column_name} уже существует")
            except Exception as e:
                print(f"  ⚠️  Ошибка при добавлении {table_name}.{column_name}: {e}")
                db.session.rollback()
        
        # ===== ШАГ 1: Проверка и создание таблиц =====
        print("\n[1/5] Проверка структуры базы данных...")
        try:
            db.create_all()
            print("✅ Все таблицы созданы/проверены")
        except Exception as e:
            print(f"❌ Ошибка при создании таблиц: {e}")
            return False
        
        # ===== ШАГ 2: Обновление created_at для существующих рефералов =====
        print("\n[2/5] Обновление created_at для существующих рефералов...")
        
        # Используем raw SQL для безопасного запроса
        result = db.session.execute(text("SELECT id FROM referal WHERE created_at IS NULL"))
        referal_ids = [row[0] for row in result]
        
        print(f"Найдено рефералов без created_at: {len(referal_ids)}")
        
        updated_count = 0
        for referal_id in referal_ids:
            try:
                referal = Referal.query.get(referal_id)
                if not referal:
                    continue
                    
                # Пытаемся установить created_at на основе договора
                if referal.deals:
                    # Находим самый ранний договор
                    deals_with_date = [d for d in referal.deals if d.agreement_date]
                    if deals_with_date:
                        earliest_deal = min(deals_with_date, key=lambda d: d.agreement_date)
                        referal.created_at = datetime.combine(earliest_deal.agreement_date, datetime.min.time())
                        print(f"  Referal ID {referal.id}: установлен created_at по договору {earliest_deal.agreement_number}")
                    else:
                        # Если у договоров нет дат, ставим 60 дней назад
                        referal.created_at = datetime.utcnow() - timedelta(days=60)
                        print(f"  Referal ID {referal.id}: установлен created_at по умолчанию (60 дней назад)")
                else:
                    # Если нет договоров, ставим 60 дней назад
                    referal.created_at = datetime.utcnow() - timedelta(days=60)
                    print(f"  Referal ID {referal.id}: установлен created_at по умолчанию (нет договоров)")
                
                # Устанавливаем days_window
                if not referal.days_window or referal.days_window == 0:
                    referal.days_window = 45
                
                updated_count += 1
                
            except Exception as e:
                print(f"  ⚠️ Ошибка для referal ID {referal.id}: {e}")
        
        try:
            db.session.commit()
            print(f"✅ Обновлено {updated_count} рефералов с created_at и days_window")
        except Exception as e:
            db.session.rollback()
            print(f"❌ Ошибка при сохранении created_at: {e}")
            return False
        
        # ===== ШАГ 2.5: Обновление last_deal_date для контактов =====
        print("\n[2.5/5] Обновление last_deal_date для контактов...")
        
        from services.data_sync_service import _update_last_deal_dates_for_contacts
        try:
            _update_last_deal_dates_for_contacts()
            print(f"✅ Обновлены даты последних сделок для контактов")
        except Exception as e:
            print(f"⚠️ Предупреждение при обновлении last_deal_date: {e}")
        
        # ===== ШАГ 3: Миграция связей referal-deal в ReferalDeal =====
        print("\n[3/5] Миграция существующих связей referal-deal...")
        
        all_deals_with_referal = MacroDeal.query.filter(MacroDeal.referal_id != None).all()
        print(f"Найдено договоров с referal_id: {len(all_deals_with_referal)}")
        
        created_links = 0
        skipped_links = 0
        
        for deal in all_deals_with_referal:
            try:
                # Проверяем, нет ли уже связи
                existing_link = ReferalDeal.query.filter_by(
                    referal_id=deal.referal_id,
                    deal_id=deal.id
                ).first()
                
                if existing_link:
                    print(f"  ⏭️ Deal ID {deal.id} уже привязан к referal ID {deal.referal_id}")
                    skipped_links += 1
                    continue
                
                # Проверяем существование реферала
                referal = Referal.query.get(deal.referal_id)
                if not referal:
                    print(f"  ⚠️ Referal ID {deal.referal_id} не найден для deal ID {deal.id}")
                    continue
                
                # Рассчитываем дни от создания реферала
                days_diff = None
                is_within = True
                if deal.agreement_date and referal.created_at:
                    deal_datetime = datetime.combine(deal.agreement_date, datetime.min.time())
                    days_diff = (deal_datetime - referal.created_at).days
                    is_within = abs(days_diff) <= (referal.days_window or 45)
                
                # Рассчитываем сумму выплаты
                withdrawal_amount = referal_service.calculate_withdrawal_for_deal(deal)
                
                # Определяем, была ли выплата обработана (если баланс реферала уже обновлен)
                payment_processed = referal.balance_updated if hasattr(referal, 'balance_updated') else False
                
                # Определяем статус договора на основе текущего состояния
                deal_status = 'pending'
                if payment_processed:
                    deal_status = 'paid'
                elif referal.balance_pending_withdrawal if hasattr(referal, 'balance_pending_withdrawal') else False:
                    deal_status = 'sent_for_review'
                elif referal.status_id and referal.status_id > 0:
                    deal_status = 'approved'
                
                # Создаем связь
                link = ReferalDeal(
                    referal_id=deal.referal_id,
                    deal_id=deal.id,
                    linked_at=referal.created_at or datetime.utcnow(),
                    is_within_window=is_within,
                    days_from_referal_creation=days_diff,
                    withdrawal_amount=withdrawal_amount,
                    payment_processed=payment_processed,
                    deal_status=deal_status
                )
                
                db.session.add(link)
                created_links += 1
                
                print(f"  ✅ Создана связь: Referal {deal.referal_id} <-> Deal {deal.id} (Agreement: {deal.agreement_number}, Amount: {withdrawal_amount})")
                
            except Exception as e:
                print(f"  ❌ Ошибка для deal ID {deal.id}: {e}")
        
        try:
            db.session.commit()
            print(f"\n✅ Создано новых связей ReferalDeal: {created_links}")
            print(f"⏭️ Пропущено существующих связей: {skipped_links}")
        except Exception as e:
            db.session.rollback()
            print(f"❌ Ошибка при сохранении связей: {e}")
            return False
        
        # ===== ШАГ 4: Финальная проверка =====
        print("\n[4/5] Финальная проверка...")
        
        total_referals = Referal.query.count()
        total_deals = MacroDeal.query.count()
        total_links = ReferalDeal.query.count()
        referals_with_created_at = Referal.query.filter(Referal.created_at != None).count()
        
        print(f"\n{'=' * 80}")
        print("РЕЗУЛЬТАТЫ МИГРАЦИИ:")
        print(f"{'=' * 80}")
        print(f"  Всего рефералов: {total_referals}")
        print(f"  Рефералов с created_at: {referals_with_created_at}")
        print(f"  Всего договоров: {total_deals}")
        print(f"  Всего связей ReferalDeal: {total_links}")
        print(f"  Создано новых связей: {created_links}")
        print(f"{'=' * 80}")
        
        if referals_with_created_at == total_referals and created_links > 0:
            print("\n✅ МИГРАЦИЯ ЗАВЕРШЕНА УСПЕШНО!")
            return True
        else:
            print("\n⚠️ МИГРАЦИЯ ЗАВЕРШЕНА С ПРЕДУПРЕЖДЕНИЯМИ")
            return True


if __name__ == '__main__':
    print("\n" + "=" * 80)
    print("СКРИПТ МИГРАЦИИ: Множественные договора для рефералов")
    print("=" * 80)
    print("\nЭтот скрипт выполнит следующие действия:")
    print("1. Добавит поля created_at и days_window ко всем рефералам")
    print("2. Создаст таблицу ReferalDeal для связи многие-ко-многим")
    print("3. Мигрирует существующие связи referal-deal")
    print("4. Сохранит информацию о выплатах для каждого договора")
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
