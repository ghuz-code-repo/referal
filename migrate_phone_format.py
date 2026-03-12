#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Миграция телефонов к единому формату +998 XX XXX XX XX
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app import app, db
from models import ReferalData
from utils import format_phone_number

def migrate_phone_formats():
    """Обновляет все телефоны к единому формату с пробелами"""
    
    with app.app_context():
        print("=" * 80)
        print("МИГРАЦИЯ ТЕЛЕФОНОВ К ЕДИНОМУ ФОРМАТУ")
        print("=" * 80)
        
        # Получаем всех рефералов с телефонами
        all_referal_data = ReferalData.query.filter(
            ReferalData.phone_number.isnot(None),
            ReferalData.phone_number != ''
        ).all()
        
        print(f"\nВсего рефералов с телефонами: {len(all_referal_data)}\n")
        
        updated_count = 0
        skipped_count = 0
        error_count = 0
        
        for referal_data in all_referal_data:
            old_phone = referal_data.phone_number
            
            # Форматируем телефон
            new_phone = format_phone_number(old_phone)
            
            if not new_phone:
                print(f"❌ ОШИБКА: Не удалось отформатировать '{old_phone}' (ID: {referal_data.id})")
                error_count += 1
                continue
            
            # Если формат уже правильный - пропускаем
            if old_phone == new_phone:
                skipped_count += 1
                continue
            
            # Обновляем
            print(f"✅ Обновляем:")
            print(f"   ID: {referal_data.id}")
            print(f"   Имя: {referal_data.full_name}")
            print(f"   Было: '{old_phone}'")
            print(f"   Стало: '{new_phone}'")
            print()
            
            referal_data.phone_number = new_phone
            updated_count += 1
        
        # Сохраняем изменения
        if updated_count > 0:
            try:
                db.session.commit()
                print("\n" + "=" * 80)
                print("✅ ИЗМЕНЕНИЯ СОХРАНЕНЫ В БАЗУ ДАННЫХ")
                print("=" * 80)
            except Exception as e:
                db.session.rollback()
                print("\n" + "=" * 80)
                print(f"❌ ОШИБКА ПРИ СОХРАНЕНИИ: {e}")
                print("=" * 80)
                return
        
        # Итоговая статистика
        print(f"\nИТОГОВАЯ СТАТИСТИКА:")
        print(f"  Всего обработано: {len(all_referal_data)}")
        print(f"  Обновлено: {updated_count}")
        print(f"  Уже в правильном формате: {skipped_count}")
        print(f"  Ошибок: {error_count}")
        
        # Проверяем результат
        if updated_count > 0:
            print("\n" + "=" * 80)
            print("ПРОВЕРКА РЕЗУЛЬТАТА")
            print("=" * 80)
            
            # Показываем примеры обновленных телефонов
            updated_phones = ReferalData.query.filter(
                ReferalData.phone_number.like('+998 %')
            ).limit(10).all()
            
            print(f"\nПримеры телефонов в новом формате (первые 10):")
            for rd in updated_phones:
                print(f"  {rd.full_name}: {rd.phone_number}")
            
            # Показываем телефоны в старом формате (если остались)
            old_format_phones = ReferalData.query.filter(
                ReferalData.phone_number.like('+998%'),
                ~ReferalData.phone_number.like('+998 %')
            ).limit(10).all()
            
            if old_format_phones:
                print(f"\n⚠️ Телефоны в старом формате (еще остались):")
                for rd in old_format_phones:
                    print(f"  {rd.full_name}: {rd.phone_number}")
            else:
                print(f"\n✅ Все телефоны в новом формате!")


if __name__ == '__main__':
    try:
        migrate_phone_formats()
        print("\n" + "=" * 80)
        print("МИГРАЦИЯ ЗАВЕРШЕНА")
        print("=" * 80)
    except Exception as e:
        print(f"\n❌ КРИТИЧЕСКАЯ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
