"""
Updated referal app.py with auth-connector integration
This shows how to integrate the auth-connector module
"""

# Импорты необходимых библиотек
from datetime import datetime, timedelta
import locale
from pathlib import Path
import re
import sys
from flask import Flask, request, g, redirect, url_for
from werkzeug.middleware.proxy_fix import ProxyFix
import pymysql
from models import MacroContact, MacroDeal, db, User, Referal, Status

# Импортируем все Blueprint'ы из папки routes
from routes import auth_bp, referal_bp, admin_bp, document_bp, user_bp, sync_bp
from routes.user_documents_routes import user_documents_bp, api_user_documents_bp
from routes.user_documents_api import user_documents_api_bp
# from test_profile_features import test_profile_bp
# from test_headers import test_headers_bp
# from test_email_quick import test_email_bp
# from debug_headers import debug_headers_bp
# from minimal_test import minimal_test_bp

# Импортируем тестовый blueprint
# from test_template import test_bp

# AUTH-CONNECTOR INTEGRATION
try:
    from auth_connector import AuthMiddleware, AuthClient
except ImportError:
    print("Warning: auth-connector not installed. Install with: pip install -e ../auth-connector")
    AuthMiddleware = None
    AuthClient = None

import pandas as pd
from werkzeug.security import generate_password_hash
from dotenv import load_dotenv
import os
from flask_apscheduler import APScheduler
from prefix_middleware import PrefixMiddleware
import requests
import json

import services
import utils as utils
from header_utils import decode_header_full_name

env_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=env_path)

# Инициализация приложения Flask - восстанавливаем встроенные статические файлы
app = Flask(__name__, 
           static_url_path='/static',
           static_folder='static')

# Configure app to work behind a proxy
# First apply ProxyFix
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

# Then apply PrefixMiddleware to strip /referal prefix
app.wsgi_app = PrefixMiddleware(app.wsgi_app, prefix='/referal')

# Fix the SERVER_NAME issue properly - update the config instead of modifying it directly
app.config.update(
    SERVER_NAME=None,
    SQLALCHEMY_DATABASE_URI=os.getenv('SQLALCHEMY_DATABASE_URI'),
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    SECRET_KEY=os.getenv('SECRET_KEY', 'default-secret-key'),
    APPLICATION_ROOT='/referal',
    PREFERRED_URL_SCHEME='http',
    AUTH_SERVICE_URL=os.getenv('AUTH_SERVICE_URL', 'http://gateway-nginx-1')
)

# Инициализация базы данных
db.init_app(app)

# Добавляем кастомный фильтр для очистки None значений
@app.template_filter('clean_none')
def clean_none_filter(value):
    """Фильтр для очистки None значений и строки 'None'"""
    if value is None or value == 'None' or str(value) == 'None':
        return ''
    return value

def get_user_documents_from_auth_service(user_id):
    """Получение документов пользователя из auth-service через API для сервиса referal
    Новая логика:
    1) Получаем все документы пользователя для сервиса 'referal' 
    2) Из каждой группы берем документ, который используется для данного сервиса
    3) Если несколько документов в группе используются для сервиса - берем последний добавленный
    """
    try:
        auth_service_url = app.config.get('AUTH_SERVICE_URL', 'http://gateway-nginx-1')
        url = f"{auth_service_url}/api/users/{user_id}/documents/for-service/referal"
        
        print(f"🔍 Запрашиваю документы пользователя для сервиса referal: {url}")
        
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            documents_for_service = data.get('documents_for_service', {})
            print(f"📄 Получено {len(documents_for_service)} групп документов для пользователя {user_id}")
            
            # Преобразуем документы в удобный формат
            result = {}
            
            # Обрабатываем группу identity (паспорт, ПИНФЛ и т.д.)
            if 'identity' in documents_for_service:
                identity_doc = documents_for_service['identity']['document']
                doc_type = identity_doc.get('document_type', '').lower()
                fields = identity_doc.get('fields', {})
                
                if doc_type == 'passport':
                    result.update({
                        'passport_number': fields.get('passport_number'),
                        'passport_giver': fields.get('passport_giver'),
                        'passport_date': fields.get('passport_date'),
                        'passport_address': fields.get('passport_address')
                    })
                elif doc_type == 'passport_ru':
                    result.update({
                        'passport_number': f"{fields.get('series', '')} {fields.get('number', '')}".strip(),
                        'passport_giver': fields.get('issued_by'),
                        'passport_date': fields.get('issued_date'),
                        'passport_address': fields.get('address', '')  # Может отсутствовать в РФ паспорте
                    })
                elif doc_type == 'pinfl':
                    result['pinfl'] = fields.get('pinfl')
                
                print(f"🆔 Документ удостоверения личности: {doc_type} - {fields}")
            
            # Обрабатываем группу financial (банковские данные)
            if 'financial' in documents_for_service:
                financial_doc = documents_for_service['financial']['document']
                doc_type = financial_doc.get('document_type', '').lower()
                fields = financial_doc.get('fields', {})
                
                if doc_type == 'bank_details':
                    result.update({
                        'bank_name': fields.get('bank_name'),
                        'bank_card': fields.get('card_number'),
                        'bank_account': fields.get('trans_schet'),
                        'bank_mfo': fields.get('mfo')
                    })
                
                print(f"💳 Финансовый документ: {doc_type} - {fields}")
            
            print(f"📋 Итоговые обработанные документы: {result}")
            return result
            
        else:
            print(f"❌ Ошибка получения документов: {response.status_code}")
            return {}
            
    except requests.RequestException as e:
        print(f"❌ Сетевая ошибка при получении документов: {e}")
        return {}
    except Exception as e:
        print(f"❌ Общая ошибка при получении документов: {e}")
        return {}

# Добавляем context processor для получения данных пользователя из auth-service
@app.context_processor
def inject_auth_user_data():
    """Добавляет функцию получения данных пользователя в контекст всех шаблонов"""
    def get_auth_user_data():
        """Получить данные пользователя из заголовков auth-service"""
        from flask import request
        
        # ОТЛАДКА: логируем все заголовки
        print("=" * 50)
        print("🔍 ВЫЗОВ get_auth_user_data() !!!")
        print("=" * 50)
        user_headers = {}
        for name, value in request.headers:
            if name.startswith('X-User-'):
                user_headers[name] = value
        print(f"📧 ALL USER HEADERS: {user_headers}")
        
        full_name = decode_header_full_name(request)
        username = request.headers.get('X-User-Name')
        avatar_path = request.headers.get('X-User-Avatar')
        email = request.headers.get('X-User-Email')
        user_id = request.headers.get('X-User-ID')
        permissions = request.headers.get('X-User-Permissions', '').split(',') if request.headers.get('X-User-Permissions') else []
        
        # Получаем документы через API
        documents_data = {}
        if user_id:
            documents_data = get_user_documents_from_auth_service(user_id)
        
        print(f"📧 EMAIL HEADER: '{email}'")
        print(f"👤 USERNAME: '{username}'")
        print(f"📄 DOCUMENTS FROM API: {documents_data}")
        
        # Если нет username вообще, возвращаем None
        if not username:
            print("❌ NO USERNAME FOUND, returning None")
            return None
        
        # Если full_name пустое или None, используем username как fallback
        if not full_name or full_name.strip() == '':
            result = {
                'full_name': username,
                'short_name': username,
                'username': username,
                'avatar_path': avatar_path,
                'email': email,
                'user_id': user_id,
                'permissions': permissions,
                # Документы из API
                'passport_number': documents_data.get('passport_number'),
                'passport_giver': documents_data.get('passport_giver'),
                'passport_date': documents_data.get('passport_date'),
                'passport_address': documents_data.get('passport_address'),
                'pinfl': documents_data.get('pinfl'),
                'phone': request.headers.get('X-User-Phone'),  # Телефон остается из заголовков
                # Банковские данные
                'bank_name': documents_data.get('bank_name'),
                'bank_account': documents_data.get('bank_account'),
                'bank_card': documents_data.get('bank_card'),
                'bank_mfo': documents_data.get('bank_mfo'),
            }
            print(f"✅ RETURNING (username fallback): {result}")
            print("=" * 50)
            return result
        
        # Форматируем full_name в short_name (Фамилия И.О.)
        name_parts = full_name.strip().split()
        if len(name_parts) >= 3:
            # Фамилия Имя Отчество -> Фамилия И.О.
            surname = name_parts[0]
            name_initial = name_parts[1][0] + '.' if name_parts[1] else ''
            patronymic_initial = name_parts[2][0] + '.' if name_parts[2] else ''
            short_name = f"{surname} {name_initial}{patronymic_initial}"
        elif len(name_parts) == 2:
            # Фамилия Имя -> Фамилия И.
            surname = name_parts[0]
            name_initial = name_parts[1][0] + '.' if name_parts[1] else ''
            short_name = f"{surname} {name_initial}"
        else:
            # Если только одно слово, возвращаем как есть
            short_name = full_name
        
        result = {
            'full_name': full_name,
            'short_name': short_name,
            'username': username,
            'avatar_path': avatar_path,
            'email': email,
            'user_id': user_id,
            'permissions': permissions,
            # Документы из API
            'passport_number': documents_data.get('passport_number'),
            'passport_giver': documents_data.get('passport_giver'),
            'passport_date': documents_data.get('passport_date'),
            'passport_address': documents_data.get('passport_address'),
            'pinfl': documents_data.get('pinfl'),
            'phone': request.headers.get('X-User-Phone'),  # Телефон остается из заголовков
            # Банковские данные
            'bank_name': documents_data.get('bank_name'),
            'bank_account': documents_data.get('bank_account'),
            'bank_card': documents_data.get('bank_card'),
            'bank_mfo': documents_data.get('bank_mfo'),
        }
        print(f"✅ RETURNING (full name): {result}")
        print("=" * 50)
        return result

    def check_permission(permission_name):
        """Проверить разрешение пользователя"""
        try:
            # Получаем текущего пользователя из flask.g
            from flask import g
            user = getattr(g, 'user', None)
            
            if user and hasattr(user, 'has_permission'):
                result = user.has_permission(permission_name)
                print(f"🔑 check_permission('{permission_name}') -> {result} | User: {getattr(user, 'username', 'unknown')}")
                return result
            
            print(f"🔑 check_permission('{permission_name}') -> False | No user or no has_permission method")
            return False
        except Exception as e:
            print(f"ERROR check_permission: {e}")
            return False
    
    return dict(get_auth_user_data=get_auth_user_data, check_permission=check_permission)

# SETUP AUTH-CONNECTOR (если доступен)
if AuthClient and AuthMiddleware:
    # Создаем клиент для auth-service
    auth_client = AuthClient(
        auth_service_url=os.getenv('AUTH_SERVICE_URL', 'http://gateway:8080'),
        service_key='referal',
        timeout=10
    )
    
    # Сохраняем auth_client в app для использования в других модулях
    app.auth_client = auth_client
    
    # Настраиваем middleware для извлечения контекста пользователя
    auth_middleware = AuthMiddleware(
        app=app,
        auth_client=auth_client,
        jwt_secret=os.getenv('JWT_SECRET'),
        verify_signature=False  # В dev среде можно отключить для упрощения
    )
    
    print("✅ Auth-connector initialized successfully")
else:
    print("⚠️  Auth-connector not available - using legacy auth")
    app.auth_client = None

# Создание таблиц в контексте приложения
with app.app_context():
    db.create_all()

# Инициализация планировщика
scheduler = APScheduler()
scheduler.init_app(app)
scheduler.start()

@app.route('/')
def home():
    """Корневой маршрут - умное перенаправление на основе разрешений."""
    print("DEBUG HOME: function called")
    
    # AUTH-CONNECTOR INTEGRATION - получаем пользователя
    try:
        from auth_connector import get_current_user as get_auth_user
        from routes.auth_routes import get_current_user
        
        auth_user = get_auth_user()
        if auth_user:
            print(f"DEBUG HOME: Auth-connector user found: {auth_user.username}")
            
            # Admin panel access for admin roles
            has_admin_panel = auth_user.has_permission('referal.admin.panel')
            has_manage_users = auth_user.has_any_permission(['referal.admin.manage_users', 'referal.users.manage'])
            print(f"DEBUG HOME: has_admin_panel={has_admin_panel}, has_manage_users={has_manage_users}")
            
            if has_admin_panel or has_manage_users:
                print("DEBUG HOME: Redirecting to admin panel")
                return redirect(url_for('admin.admin_panel'))
            
            # Check if user has access to referral functionality
            required_perms = [
                'referal.referrals.list',
                'referal.referrals.view',
                'referal.referrals.create',
                'referal.referrals.add'  # Альтернативное название для создания
            ]
            has_referral_access = auth_user.has_any_permission(required_perms)
            
            if has_referral_access:
                return redirect(url_for('referal.my_referrals'))
            else:
                # User has no access to referral functionality
                from flask import render_template
                return render_template('access_denied.html',
                                     service_name='Реферальная программа',
                                     required_permissions=['referal.admin.panel', 'referal.referrals.list', 'referal.referrals.create']), 403
            
    except ImportError:
        # Legacy fallback
        try:
            from routes.auth_routes import get_current_user
            user = get_current_user()
            if user and hasattr(user, 'role') and user.role in ['admin', 'manager', 'call-center']:
                return redirect(url_for('admin.admin_panel'))
        except Exception as e:
            pass
    
    return redirect(url_for('referal.profile'))

# Register all blueprints WITHOUT URL prefixes
app.register_blueprint(auth_bp)
app.register_blueprint(user_bp)  # БЕЗ префикса - nginx уже обрезает /referal
app.register_blueprint(referal_bp)  # БЕЗ префикса - nginx уже обрезает /referal  
app.register_blueprint(admin_bp)
app.register_blueprint(document_bp)
app.register_blueprint(user_documents_bp)  # Новый blueprint для документов
app.register_blueprint(user_documents_api_bp)  # API blueprint для документов
# app.register_blueprint(test_profile_bp)  # Тестовый blueprint для профиля
# app.register_blueprint(test_headers_bp)  # Тестовый blueprint для заголовков
# app.register_blueprint(test_email_bp)  # Быстрый тест email
# app.register_blueprint(debug_headers_bp)  # Отладка всех заголовков
# app.register_blueprint(minimal_test_bp)  # Минимальный тест заголовков

# Добавляем тестовый роут для проверки данных профиля
@app.route('/test_profile_data')
def test_profile_data_route():
    """Тестовая страница для проверки данных профиля"""
    from test_profile_data import test_profile_data
    return test_profile_data()
app.register_blueprint(sync_bp, url_prefix='/api/sync')
# app.register_blueprint(test_bp)  # Добавляем тестовый blueprint

# Note: PrefixMiddleware is already applied earlier in the code, right after ProxyFix

# Add scheduled tasks
@scheduler.task('cron', id='update_deals', hour=10, minute=30)
def update_deals_task():
    """Обновление информации о сделках"""
    with app.app_context():
        print("Starting scheduled deal update task...")
        try:
            # Получаем всех пользователей и обновляем их данные
            users = User.query.all()
            for user in users:
                try:
                    services.referal_service.update_deal_info(user)
                    print(f"Updated deals for user: {user.login}")
                except Exception as e:
                    print(f"Error updating deals for user {user.login}: {str(e)}")
            
            print("Scheduled deal update task completed successfully")
        except Exception as e:
            print(f"Error in scheduled deal update task: {str(e)}")

@app.before_request
def before_request():
    """Global before request handler"""
    # Skip auth for static files and sync endpoints
    if request.path.startswith('/static') or request.path.startswith('/api/sync'):
        return
    
    # Логируем минимальную информацию о пользователе для каждого запроса
    username = request.headers.get('X-User-Name', 'Anonymous')
    user_id = request.headers.get('X-User-ID', 'N/A')
    print(f"[{request.method}] {request.path} | User: {username} (ID: {user_id})")

if __name__ == '__main__':
    print("Starting referal application...")
    
    # Show configuration
    print(f"Database URI: {app.config.get('SQLALCHEMY_DATABASE_URI', 'Not configured')}")
    print(f"Auth Service URL: {os.getenv('AUTH_SERVICE_URL', 'Not configured')}")
    
    # Отключаем логи статических файлов (CSS, JS)
    import logging
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    
    app.run(debug=True, host='0.0.0.0', port=80)