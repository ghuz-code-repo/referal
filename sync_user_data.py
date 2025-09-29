#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для синхронизации пользовательских данных с auth-service
Данные пользователей и их документы должны храниться в auth-service
"""
import requests
import json
import sqlite3
from datetime import datetime

def sync_user_documents_with_auth():
    """Синхронизирует документы пользователей с auth-service"""
    
    print("🔄 Синхронизация документов пользователей с auth-service...")
    
    # Подключаемся к локальной базе
    conn = sqlite3.connect('instance/referal_program.db')
    cursor = conn.cursor()
    
    try:
        # Получаем всех пользователей с их auth_user_id
        cursor.execute('''
            SELECT u.id, u.login, u.auth_user_id, ud.full_name, ud.passport_number, 
                   ud.passport_giver, ud.passport_date, ud.passport_adress, 
                   ud.phone, ud.e_mail, ud.pinfl, ud.bank_name, ud.trans_schet, 
                   ud.card_number, ud.mfo
            FROM user u 
            LEFT JOIN user_data ud ON u.id = ud.user_id
            WHERE u.auth_user_id IS NOT NULL
        ''')
        
        users_with_data = cursor.fetchall()
        
        if not users_with_data:
            print("   ⚠️  Нет пользователей с данными для синхронизации")
            return True
            
        print(f"   📋 Найдено {len(users_with_data)} пользователей для синхронизации")
        
        # Синхронизируем каждого пользователя
        for user_data in users_with_data:
            user_id, login, auth_user_id = user_data[:3]
            documents = user_data[3:]  # остальные поля документов
            
            if not any(documents):  # если нет данных документов
                print(f"   ⏭️  Пользователь {login}: нет данных документов, пропускаем")
                continue
                
            # Формируем данные для отправки в auth-service
            document_data = {
                "user_id": auth_user_id,
                "full_name": documents[0] or "",
                "passport": {
                    "number": documents[1] or "",
                    "giver": documents[2] or "",
                    "date": documents[3] or "",
                    "address": documents[4] or ""
                },
                "contact": {
                    "phone": documents[5] or "",
                    "email": documents[6] or ""
                },
                "financial": {
                    "pinfl": documents[7] or "",
                    "bank_name": documents[8] or "",
                    "account": documents[9] or "",
                    "card_number": documents[10] or "",
                    "mfo": documents[11] or ""
                }
            }
            
            try:
                # Отправляем данные в auth-service
                response = requests.post(
                    'http://localhost/auth/users/documents',
                    headers={'Content-Type': 'application/json'},
                    json=document_data,
                    timeout=10
                )
                
                if response.status_code == 200:
                    print(f"   ✅ {login}: документы синхронизированы")
                else:
                    print(f"   ❌ {login}: ошибка синхронизации - {response.status_code}")
                    
            except requests.exceptions.RequestException as e:
                print(f"   ⚠️  {login}: ошибка соединения с auth-service: {e}")
                continue
                
        return True
        
    except Exception as e:
        print(f"❌ Ошибка синхронизации: {e}")
        return False
    finally:
        conn.close()

def create_user_documents_in_auth():
    """Создает тестовые документы пользователей в auth-service"""
    
    print("📄 Создание тестовых документов пользователей...")
    
    # Тестовые документы для пользователей
    test_documents = {
        "d.tolkunov": {
            "full_name": "Толкунов Дмитрий Александрович",
            "passport": {
                "number": "AD1234567",
                "giver": "ГУВД г. Ташкента",
                "date": "2015-03-10",
                "address": "г. Ташкент, ул. Навои, д. 45, кв. 12"
            },
            "contact": {
                "phone": "+998901111111", 
                "email": "d.tolkunov@company.com"
            },
            "financial": {
                "pinfl": "12345678901234",
                "bank_name": "Узпромстройбанк",
                "account": "20208000400001234567",
                "card_number": "8600****1234",
                "mfo": "00060"
            }
        },
        "prodgaraj": {
            "full_name": "Продгарадж Админ Тестович", 
            "passport": {
                "number": "BC9876543",
                "giver": "ГУВД г. Ташкента",
                "date": "2018-07-15", 
                "address": "г. Ташкент, ул. Мирабад, д. 78, кв. 45"
            },
            "contact": {
                "phone": "+998902222222",
                "email": "prodgaraj@company.com" 
            },
            "financial": {
                "pinfl": "98765432109876",
                "bank_name": "Народный банк",
                "account": "20208000400009876543", 
                "card_number": "8600****9876",
                "mfo": "00033"
            }
        }
    }
    
    # Получаем ID пользователей из MongoDB
    try:
        users_response = requests.get('http://localhost/auth/users', timeout=10)
        if users_response.status_code != 200:
            print("   ❌ Не удалось получить список пользователей из auth-service")
            return False
            
        users = users_response.json()
        
        for user in users:
            username = user.get('username')
            if username in test_documents:
                doc_data = test_documents[username].copy()
                doc_data['user_id'] = user.get('_id')
                
                response = requests.post(
                    'http://localhost/auth/users/documents',
                    headers={'Content-Type': 'application/json'},
                    json=doc_data,
                    timeout=10
                )
                
                if response.status_code == 200:
                    print(f"   ✅ {username}: документы созданы в auth-service")
                else:
                    print(f"   ❌ {username}: ошибка создания - {response.status_code}")
        
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"   ⚠️  Ошибка соединения с auth-service: {e}")
        return False

def update_referal_auth_ids():
    """Обновляет auth_user_id в таблице пользователей referal service"""
    
    print("🔗 Обновление связей с auth-service...")
    
    try:
        # Получаем пользователей из auth-service
        response = requests.get('http://localhost/auth/users', timeout=10)
        if response.status_code != 200:
            print("   ❌ Не удалось получить пользователей из auth-service")
            return False
            
        auth_users = response.json()
        
        # Подключаемся к локальной базе
        conn = sqlite3.connect('instance/referal_program.db')
        cursor = conn.cursor()
        
        for auth_user in auth_users:
            username = auth_user.get('username')
            auth_id = auth_user.get('_id')
            
            if username and auth_id:
                cursor.execute(
                    'UPDATE user SET auth_user_id = ? WHERE login = ?',
                    (auth_id, username)
                )
                
        conn.commit()
        conn.close()
        
        print(f"   ✅ Обновлены связи для {len(auth_users)} пользователей")
        return True
        
    except Exception as e:
        print(f"   ❌ Ошибка обновления связей: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Синхронизация пользовательских данных с auth-service...\n")
    
    # 1. Обновляем связи с auth-service
    if not update_referal_auth_ids():
        print("💥 Не удалось обновить связи с auth-service")
        exit(1)
    
    # 2. Создаем тестовые документы в auth-service (если API доступно)
    print()
    create_user_documents_in_auth()
    
    # 3. Синхронизируем существующие документы (если есть)
    print()
    sync_user_documents_with_auth()
    
    print("\n🎉 Синхронизация завершена!")
    print("💡 Рекомендации:")
    print("   - Проверьте, что документы пользователей доступны через auth-service API")
    print("   - Убедитесь, что referal service обращается к auth-service за данными пользователей")
    print("   - Данные рефералов остаются в referal service")