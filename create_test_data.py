#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для создания тестовых рефералов и исправления ролей пользователей
"""
import sqlite3
from datetime import datetime, date
import random

def create_test_data():
    """Создает тестовые данные для системы рефералов"""
    conn = sqlite3.connect('instance/referal_program.db')
    cursor = conn.cursor()
    
    try:
        # 1. Обновляем роль пользователя prodgaraj на admin
        print("1. Обновление роли пользователя prodgaraj...")
        cursor.execute('UPDATE user SET role = ? WHERE login = ?', ('admin', 'prodgaraj'))
        
        # 2. Проверяем, что у нас есть статусы
        cursor.execute('SELECT COUNT(*) FROM status')
        status_count = cursor.fetchone()[0]
        print(f"   Статусов в системе: {status_count}")
        
        if status_count == 0:
            # Добавляем статусы
            statuses = [
                ('Новый', False, True),
                ('В работе', False, False),
                ('Встреча назначена', False, False),
                ('Встреча состоялась', False, False),
                ('Заключен договор', False, False),
                ('Выплата одобрена', False, False),
                ('Выплачено', True, False),
                ('Отклонено', True, False)
            ]
            cursor.executemany('INSERT INTO status (name, is_final, is_start) VALUES (?, ?, ?)', statuses)
            print("   Добавлены базовые статусы")
        
        # 3. Создаем тестовые макро-контакты
        print("2. Создание тестовых макро-контактов...")
        test_contacts = [
            (1001, 'Иванов Иван Иванович', '+998901234567', 'AA1234567', 'ГУВД г. Ташкента', '1990-01-15', 'г. Ташкент, ул. Навои, д. 10', 'ivanov@example.com', 'DOG-2025-001'),
            (1002, 'Петров Петр Петрович', '+998901234568', 'BB2345678', 'ГУВД г. Ташкента', '1985-05-20', 'г. Ташкент, ул. Амира Тимура, д. 25', 'petrov@example.com', 'DOG-2025-002'),
            (1003, 'Сидоров Сидор Сидорович', '+998901234569', 'CC3456789', 'ГУВД г. Самарканда', '1992-03-10', 'г. Самарканд, ул. Регистан, д. 5', 'sidorov@example.com', 'DOG-2025-003'),
            (1004, 'Козлов Александр Михайлович', '+998901234570', 'DD4567890', 'ГУВД г. Ташкента', '1988-07-08', 'г. Ташкент, ул. Бунёдкор, д. 15', 'kozlov@example.com', 'DOG-2025-004'),
            (1005, 'Морозова Елена Викторовна', '+998901234571', 'EE5678901', 'ГУВД г. Ташкента', '1993-12-02', 'г. Ташкент, ул. Мирабад, д. 30', 'morozova@example.com', 'DOG-2025-005')
        ]
        
        for contact in test_contacts:
            cursor.execute('''
                INSERT OR IGNORE INTO macro_contact 
                (contacts_id, full_name, phone_number, passport_number, passport_giver, passport_date, passport_address, email, agreement_number)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', contact)
        
        print(f"   Добавлено {len(test_contacts)} тестовых контактов")
        
        # 4. Создаем тестовые рефералы
        print("3. Создание тестовых рефералов...")
        
        # Получаем ID пользователей
        cursor.execute('SELECT id, login FROM user')
        users = cursor.fetchall()
        print(f"   Найдено пользователей: {len(users)}")
        
        if len(users) == 0:
            print("   ОШИБКА: Нет пользователей в системе!")
            return False
            
        # Получаем ID статусов
        cursor.execute('SELECT id FROM status ORDER BY id LIMIT 5')
        status_ids = [row[0] for row in cursor.fetchall()]
        
        # Создаем рефералы для каждого контакта
        referals_data = []
        for i, contact in enumerate(test_contacts):
            user_id = users[i % len(users)][0]  # Распределяем между пользователями
            contact_id = contact[0]
            status_id = random.choice(status_ids)
            
            referals_data.append((
                user_id,
                contact_id,
                status_id,
                'В работе' if status_id <= 3 else 'Завершен',
                random.choice([True, False]) if status_id > 2 else False,  # initial_approval
                random.choice([True, False]) if status_id > 3 else False,  # analytics_approval
                random.choice([True, False]) if status_id > 4 else False,  # cc_approval  
                random.choice([True, False]) if status_id > 5 else False,  # cd_approval
                random.randint(500000, 2000000) if status_id >= 6 else None  # payment_amount
            ))
        
        cursor.executemany('''
            INSERT OR IGNORE INTO referal 
            (user_id, contact_id, status_id, status_name, initial_approval, analytics_approval, cc_approval, cd_approval, payment_amount)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', referals_data)
        
        print(f"   Добавлено {len(referals_data)} тестовых рефералов")
        
        # 5. Создаем данные рефералов (ReferalData)
        print("4. Создание данных рефералов...")
        
        cursor.execute('SELECT id FROM referal')
        referal_ids = [row[0] for row in cursor.fetchall()]
        
        referal_data_entries = []
        for i, referal_id in enumerate(referal_ids):
            contact = test_contacts[i]
            referal_data_entries.append((
                referal_id,
                datetime.now().date() if i % 2 == 0 else None,  # contract_date
                f'CONTRACT-2025-{i+1:03d}' if i % 3 == 0 else None,  # contract_number
                contact[1],  # full_name
                contact[2],  # passport_number  
                datetime.strptime('1990-01-01', '%Y-%m-%d').date(),  # passport_date
                contact[3],  # passport_giver
                contact[5],  # passport_address
                contact[2]   # phone_number
            ))
        
        cursor.executemany('''
            INSERT OR IGNORE INTO referal_data
            (referal_id, contract_date, contract_number, full_name, passport_number, passport_date, passport_giver, passport_adress, phone_number)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', referal_data_entries)
        
        print(f"   Добавлено {len(referal_data_entries)} записей данных рефералов")
        
        conn.commit()
        
        # 6. Проверяем результат
        print("\n=== РЕЗУЛЬТАТ ===")
        cursor.execute('SELECT COUNT(*) FROM macro_contact')
        print(f"Макро-контактов: {cursor.fetchone()[0]}")
        
        cursor.execute('SELECT COUNT(*) FROM referal')
        print(f"Рефералов: {cursor.fetchone()[0]}")
        
        cursor.execute('SELECT COUNT(*) FROM referal_data')
        print(f"Данных рефералов: {cursor.fetchone()[0]}")
        
        cursor.execute('SELECT login, role FROM user')
        users = cursor.fetchall()
        print("Пользователи:")
        for user in users:
            print(f"  {user[0]}: {user[1]}")
        
        print("\n✅ Тестовые данные успешно созданы!")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка при создании тестовых данных: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    print("🚀 Создание тестовых данных для системы рефералов...")
    success = create_test_data()
    if success:
        print("\n🎉 Готово! Теперь у вас есть тестовые данные и исправлены роли.")
        print("💡 Рекомендации:")
        print("   - Проверьте работу фильтров в админ-панели")
        print("   - Убедитесь, что пользователь prodgaraj может войти в админку")
        print("   - Данные пользователей и документы должны храниться в auth-service")
    else:
        print("\n💥 Что-то пошло не так. Проверьте ошибки выше.")