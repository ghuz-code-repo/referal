#!/usr/bin/env python3
"""
Синхронизация auth_user_id для существующих пользователей
Скрипт получает всех пользователей сервиса 'referal' из auth-service и синхронизирует auth_user_id
"""
import os
import sys
import requests
from app import app, db
from models import User

# URL auth-service
AUTH_SERVICE_URL = os.getenv('AUTH_SERVICE_URL', 'http://auth-service:3001')
SERVICE_KEY = 'referal'

def get_all_service_users():
    """Получить всех пользователей сервиса 'referal' из auth-service"""
    try:
        url = f'{AUTH_SERVICE_URL}/api/services/{SERVICE_KEY}/users'
        print(f"🔍 Requesting: {url}")
        
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            users = response.json()
            print(f"✅ Got {len(users)} users from auth-service\n")
            return users
        else:
            print(f"❌ Error: {response.status_code}")
            print(f"Response: {response.text}")
            return []
    except Exception as e:
        print(f"❌ Exception: {e}")
        return []

def sync_users():
    """Синхронизировать auth_user_id для всех пользователей"""
    with app.app_context():
        # Получаем пользователей из auth-service
        auth_users = get_all_service_users()
        
        if not auth_users:
            print("⚠️  No users received from auth-service")
            return
        
        # Создаём маппинг username -> auth_user_id
        auth_mapping = {user['username']: user['id'] for user in auth_users}
        
        print(f"Auth-service users: {', '.join(auth_mapping.keys())}\n")
        
        # Находим пользователей без auth_user_id
        users_without_auth_id = User.query.filter_by(auth_user_id=None).all()
        
        print(f"Found {len(users_without_auth_id)} local users without auth_user_id\n")
        
        updated_count = 0
        skipped_count = 0
        not_found_count = 0
        
        for user in users_without_auth_id:
            print(f"Processing local user {user.id}: {user.login}")
            
            # Пропускаем служебных пользователей
            if user.login in ['admin', 'god', 'administrator', 'administartor', 'user-test']:
                print(f"  ⏭️  Skipped (service account)")
                skipped_count += 1
                continue
            
            # Ищем в маппинге
            auth_user_id = auth_mapping.get(user.login)
            
            if auth_user_id:
                user.auth_user_id = auth_user_id
                db.session.commit()
                print(f"  ✅ Updated: auth_user_id = {auth_user_id}")
                updated_count += 1
            else:
                print(f"  ❌ Not found in auth-service")
                not_found_count += 1
        
        print(f"\n{'='*60}")
        print(f"Summary:")
        print(f"  ✅ Updated:   {updated_count}")
        print(f"  ⏭️  Skipped:   {skipped_count} (service accounts)")
        print(f"  ❌ Not found: {not_found_count} (not in auth-service)")
        print(f"  📊 Total:     {len(users_without_auth_id)}")
        print(f"{'='*60}")
        
        if not_found_count > 0:
            print(f"\n⚠️  {not_found_count} users not found in auth-service.")
            print("They need to be created in auth-service first or have service access granted.")

if __name__ == '__main__':
    sync_users()
