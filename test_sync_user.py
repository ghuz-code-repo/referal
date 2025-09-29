#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тест синхронизации данных пользователя с auth-service
"""
import os
import sys
sys.path.append('/app')

# Импортируем app напрямую из app_with_auth_connector
import app_with_auth_connector
from models import User, UserData, db
from utils import sync_user_data_from_auth_service

def test_sync_user_data():
    """Тестирует синхронизацию данных пользователя"""
    app = app_with_auth_connector.app  # Используем готовый объект app
    
    with app.app_context():
        print("🔄 Тестирование синхронизации данных пользователя...")
        
        # Получаем пользователя d.tolkunov
        user = User.query.filter_by(login='d.tolkunov').first()
        if not user:
            print("❌ Пользователь d.tolkunov не найден")
            return False
            
        print(f"✅ Найден пользователь: {user.login}")
        print(f"   ID: {user.id}")
        print(f"   Auth_ID: {user.auth_user_id}")
        print(f"   Роль: {user.role}")
        
        if not user.auth_user_id:
            print("❌ У пользователя нет auth_user_id")
            return False
        
        # Проверяем текущие данные
        print("\n📋 Данные до синхронизации:")
        if user.user_data:
            print(f"   ФИО: {user.user_data.full_name}")
            print(f"   Телефон: {user.user_data.phone}")
            print(f"   Email: {user.user_data.e_mail}")
            print(f"   Паспорт: {user.user_data.passport_number}")
            print(f"   Кем выдан: {user.user_data.passport_giver}")
            print(f"   Адрес: {user.user_data.passport_adress}")
        else:
            print("   Нет данных пользователя")
        
        # Синхронизируем данные
        print("\n🔄 Выполняем синхронизацию...")
        try:
            result = sync_user_data_from_auth_service(user, force_sync=True)
            print(f"   Результат синхронизации: {result}")
        except Exception as e:
            print(f"   ❌ Ошибка синхронизации: {e}")
            return False
        
        # Проверяем данные после синхронизации
        print("\n📋 Данные после синхронизации:")
        user = User.query.filter_by(login='d.tolkunov').first()  # Перезагружаем
        if user and user.user_data:
            print(f"   ФИО: {user.user_data.full_name}")
            print(f"   Телефон: {user.user_data.phone}")
            print(f"   Email: {user.user_data.e_mail}")
            print(f"   Паспорт: {user.user_data.passport_number}")
            print(f"   Кем выдан: {user.user_data.passport_giver}")
            print(f"   Адрес: {user.user_data.passport_adress}")
            print(f"   ПИНФЛ: {user.user_data.pinfl}")
            print(f"   Банк: {user.user_data.bank_name}")
            print(f"   Карта: {user.user_data.card_number}")
        else:
            print("   Данные не загружены")
        
        return True

if __name__ == "__main__":
    success = test_sync_user_data()
    if success:
        print("\n🎉 Тест синхронизации завершен!")
    else:
        print("\n💥 Тест завершился с ошибками")