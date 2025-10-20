"""
Миграция: Создание связей referal-deal через contact_id

Эта миграция находит договоры, которые можно связать с рефералами через contact_id
(referal.contact_id = macro_deal.contacts_buy_id) и создает записи в referal_deal.
Также проставляет status_id для этих договоров.
"""

from datetime import datetime, timedelta
import sys
import os

# Добавляем родительскую директорию в path для импортов
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from models import Referal, MacroDeal, ReferalDeal
from sqlalchemy import text

def migrate():
    with app.app_context():
        print("=" * 80)
        print("МИГРАЦИЯ: Создание связей referal-deal через contact_id")
        print("=" * 80)
        
        # Шаг 1: Находим рефералы с contact_id
        print("\n[1/4] Поиск рефералов с contact_id...")
        referals_with_contact = Referal.query.filter(Referal.contact_id != None).all()
        print(f"✅ Найдено рефералов с contact_id: {len(referals_with_contact)}")
        
        # Шаг 2: Для каждого реферала ищем договоры через contact_id
        print("\n[2/4] Поиск договоров через contact_id...")
        
        total_found = 0
        total_created = 0
        total_skipped = 0
        
        for referal in referals_with_contact:
            # Ищем договоры, где contacts_buy_id совпадает с contact_id реферала
            deals = MacroDeal.query.filter(
                MacroDeal.contacts_buy_id == referal.contact_id
            ).all()
            
            if not deals:
                continue
                
            print(f"\n  Referal ID {referal.id} (contact {referal.contact_id}): найдено {len(deals)} договоров")
            total_found += len(deals)
            
            for deal in deals:
                try:
                    # Проверяем, нет ли уже связи
                    existing_link = ReferalDeal.query.filter_by(
                        referal_id=referal.id,
                        deal_id=deal.id
                    ).first()
                    
                    if existing_link:
                        print(f"    ⏭️  Deal {deal.id} ({deal.agreement_number}) - уже связан")
                        total_skipped += 1
                        continue
                    
                    # Рассчитываем дни от создания реферала
                    days_diff = None
                    is_within = True
                    if deal.agreement_date and referal.created_at:
                        deal_datetime = datetime.combine(deal.agreement_date, datetime.min.time())
                        days_diff = (deal_datetime - referal.created_at).days
                        is_within = abs(days_diff) <= (referal.days_window or 45)
                    
                    # Рассчитываем сумму выплаты (базовая логика)
                    withdrawal_amount = 0
                    if deal.withdrawal_amount:
                        withdrawal_amount = deal.withdrawal_amount
                    elif is_within:
                        # Упрощенный расчет: 0.5% от суммы договора
                        if deal.agreement_price:
                            withdrawal_amount = int(deal.agreement_price * 0.005)
                    
                    # Определяем статус договора на основе статуса реферала
                    deal_status = 'pending'
                    if referal.balance_updated:
                        deal_status = 'paid'
                    elif referal.balance_pending_withdrawal:
                        deal_status = 'sent_for_review'
                    elif referal.status_id and referal.status_id > 0:
                        deal_status = 'approved'
                    
                    # Создаем связь
                    link = ReferalDeal(
                        referal_id=referal.id,
                        deal_id=deal.id,
                        linked_at=referal.created_at or datetime.utcnow(),
                        is_within_window=is_within,
                        days_from_referal_creation=days_diff,
                        withdrawal_amount=withdrawal_amount,
                        payment_processed=referal.balance_updated if hasattr(referal, 'balance_updated') else False,
                        deal_status=deal_status,
                        status_id=referal.status_id  # Копируем статус с реферала
                    )
                    
                    db.session.add(link)
                    total_created += 1
                    
                    print(f"    ✅ Deal {deal.id} ({deal.agreement_number}): amount={withdrawal_amount}, status={referal.status_id}")
                    
                except Exception as e:
                    print(f"    ❌ Ошибка для deal {deal.id}: {e}")
                    db.session.rollback()
                    continue
        
        # Сохраняем все изменения
        print("\n[3/4] Сохранение изменений...")
        try:
            db.session.commit()
            print("✅ Изменения сохранены")
        except Exception as e:
            print(f"❌ Ошибка при сохранении: {e}")
            db.session.rollback()
            raise
        
        # Шаг 4: Финальная проверка
        print("\n[4/4] Финальная проверка...")
        try:
            total_links = ReferalDeal.query.count()
            deals_with_status = ReferalDeal.query.filter(ReferalDeal.status_id != None).count()
            
            # Статистика по рефералам
            referals_with_deals = db.session.query(Referal.id).join(
                ReferalDeal, Referal.id == ReferalDeal.referal_id
            ).distinct().count()
            
            print(f"""
================================================================================
РЕЗУЛЬТАТЫ МИГРАЦИИ:
================================================================================
  Найдено договоров через contact_id: {total_found}
  Создано новых связей: {total_created}
  Пропущено (уже существуют): {total_skipped}
  
  ИТОГО:
  Всего связей в referal_deal: {total_links}
  Связей со статусом: {deals_with_status}
  Рефералов с договорами: {referals_with_deals}
================================================================================
""")
            
            print("✅ МИГРАЦИЯ ЗАВЕРШЕНА УСПЕШНО!")
            
        except Exception as e:
            print(f"❌ Ошибка при проверке: {e}")
            raise

if __name__ == '__main__':
    migrate()
