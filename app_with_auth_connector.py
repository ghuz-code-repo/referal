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

# Импортируем тестовый blueprint
from test_template import test_bp

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

import services
import utils as utils
from header_utils import decode_header_full_name

env_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=env_path)

# Инициализация приложения Flask
app = Flask(__name__, 
           static_url_path='/static',
           static_folder='static')

# Configure app to work behind a proxy
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

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

# Добавляем context processor для получения данных пользователя из auth-service
@app.context_processor
def inject_auth_user_data():
    """Добавляет функцию получения данных пользователя в контекст всех шаблонов"""
    def get_auth_user_data():
        """Получить данные пользователя из заголовков auth-service"""
        from flask import request
        
        # Отладочная информация
        print(f"DEBUG get_auth_user_data: called")
        
        full_name = decode_header_full_name(request)
        username = request.headers.get('X-User-Name')
        avatar_path = request.headers.get('X-User-Avatar')
        
        # DEBUG: печатаем все заголовки с X-User
        debug_headers = {k: v for k, v in request.headers.items() if 'X-User' in k}
        print(f"DEBUG get_auth_user_data: all X-User headers: {debug_headers}")
        
        print(f"DEBUG get_auth_user_data: full_name='{full_name}', username='{username}', avatar_path='{avatar_path}'")
        
        # Если нет username вообще, возвращаем None
        if not username:
            print(f"DEBUG get_auth_user_data: returning None because username is empty")
            return None
        
        # Если full_name пустое или None, используем username как fallback
        if not full_name or full_name.strip() == '':
            print(f"DEBUG get_auth_user_data: using username '{username}' as fallback")
            result = {
                'full_name': username,
                'short_name': username,
                'username': username,
                'avatar_path': avatar_path
            }
            print(f"DEBUG get_auth_user_data: returning fallback {result}")
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
            'avatar_path': avatar_path
        }
        print(f"DEBUG get_auth_user_data: returning formatted {result}")
        return result

    def check_permission(permission_name):
        """Проверить разрешение пользователя"""
        try:
            if AuthClient:
                # Импортируем auth_connector только если он доступен
                from auth_connector import check_user_permission
                return check_user_permission(permission_name)
            return False
        except ImportError:
            print(f"WARNING: auth_connector not available for permission check: {permission_name}")
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

# Register all blueprints WITHOUT URL prefixes
app.register_blueprint(auth_bp)
app.register_blueprint(referal_bp)  # Убрали url_prefix='/referal'
app.register_blueprint(admin_bp)
app.register_blueprint(document_bp)
app.register_blueprint(user_bp)
app.register_blueprint(user_documents_bp)  # Новый blueprint для документов
app.register_blueprint(api_user_documents_bp)  # API blueprint для документов
app.register_blueprint(sync_bp, url_prefix='/api/sync')
app.register_blueprint(test_bp)  # Добавляем тестовый blueprint

# Add prefix middleware after registering blueprint but before initializing scheduler
# This will strip the /referal prefix when running behind proxy
app.wsgi_app = PrefixMiddleware(app.wsgi_app, prefix='/referal')

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
        
    # Additional initialization if needed
    pass

if __name__ == '__main__':
    print("Starting referal application...")
    
    # Show configuration
    print(f"Database URI: {app.config.get('SQLALCHEMY_DATABASE_URI', 'Not configured')}")
    print(f"Auth Service URL: {os.getenv('AUTH_SERVICE_URL', 'Not configured')}")
    
    app.run(debug=True, host='0.0.0.0', port=80)