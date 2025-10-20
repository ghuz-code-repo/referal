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
from routes.auth_routes import get_current_user

import pandas as pd
from werkzeug.security import generate_password_hash
from dotenv import load_dotenv
import os
from flask_apscheduler import APScheduler
from prefix_middleware import PrefixMiddleware

import services
import utils as utils
from header_utils import decode_header_full_name
from notification_client import init_notification_client


env_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=env_path)

# Инициализация клиента notification service
init_notification_client()

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
    PREFERRED_URL_SCHEME='http'
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

# Добавляем фильтр для форматирования чисел
@app.template_filter('format_number')
def format_number_filter(value):
    """Фильтр для форматирования чисел с разделителями тысяч"""
    if value is None:
        return '0'
    try:
        # Преобразуем в число и форматируем с пробелами как разделителями тысяч
        return '{:,}'.format(int(value)).replace(',', ' ')
    except (ValueError, TypeError):
        return '0'

# Регистрируем фильтры напрямую в Jinja окружении (для надежности)
app.jinja_env.filters['clean_none'] = clean_none_filter
app.jinja_env.filters['format_number'] = format_number_filter

scheduler = APScheduler()
scheduler.init_app(app)

# Schedule the daily update task to run at 04:00 every day
@scheduler.task('cron', id='daily_update_job', hour=23, minute=30)
def daily_update_task():
    """Task to update deal info for all users daily at 04:00."""
    with app.app_context():
        print("Running daily update task...")
        try:
            services.fetch_data_from_mysql()
            print("Daily update task finished.")
        except Exception as e:
            print(f"Error during daily update task: {e}")

# Start the scheduler
scheduler.start()

# Register all blueprints WITHOUT URL prefixes
app.register_blueprint(auth_bp)
app.register_blueprint(referal_bp)  # Убрали url_prefix='/referal'
app.register_blueprint(admin_bp)
app.register_blueprint(document_bp)
app.register_blueprint(user_bp)
app.register_blueprint(sync_bp, url_prefix='/api/sync')

# Add prefix middleware after registering blueprint but before initializing scheduler
# This will strip the /referal prefix when running behind proxy
if os.getenv('BEHIND_PROXY', 'false').lower() == 'true':
    app.wsgi_app = PrefixMiddleware(app.wsgi_app, prefix='/referal')


@app.route('/health')
def health():
    """Health check endpoint for Docker health checks."""
    return {'status': 'ok', 'service': 'referal-service'}, 200


@app.route('/')
def home():
    """Корневой маршрут - умное перенаправление на основе разрешений."""
    print("DEBUG HOME: function called")
    
    # Получаем текущего пользователя
    user = get_current_user()
    print(f"DEBUG HOME: User: {user.login if user else 'None'}")
    
    if not user:
        print("DEBUG HOME: No user, redirecting to profile")
        return redirect(url_for('referal.profile'))
    
    # AUTH-CONNECTOR INTEGRATION
    try:
        from auth_connector import get_current_user as get_auth_user
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
            
            # For users without referral list permissions, redirect to a page they can access
            has_referral_list = auth_user.has_permission('referal.referrals.list')
            print(f"DEBUG HOME: has_referral_list={has_referral_list}")
            
            if not has_referral_list:
                print("DEBUG HOME: User has no referral list permission")
                # Check what they can access and redirect accordingly
                if auth_user.has_permission('referal.payments.view'):
                    print("DEBUG HOME: Redirecting to payments")
                    return redirect(url_for('referal.payments'))
                else:
                    # Redirect to a basic profile page or show limited access message
                    print("DEBUG HOME: Redirecting to limited profile")
                    return redirect(url_for('referal.limited_profile'))
    except ImportError:
        print("DEBUG HOME: Auth-connector not available, using legacy logic")
        pass
    
    print("DEBUG HOME: Default path - redirecting to profile")
    return redirect(url_for('referal.profile'))


@app.before_request
def process_request_headers():
    """Обработка заголовков аутентификации перед обработкой запроса."""
    # Получаем информацию о пользователе из заголовков
    username = request.headers.get('X-User-Name')
    
    # Декодируем полное имя из base64 при необходимости
    full_name = decode_header_full_name(request)
    
    # Сохраняем в объект g Flask для доступа в маршрутах
    g.username = username
    g.full_name = full_name
    g.is_admin = request.headers.get('X-User-Admin', 'false').lower() == 'true'
    # Try service-specific roles first, fallback to legacy roles
    service_roles = request.headers.get('X-User-Service-Roles', '')
    legacy_roles = request.headers.get('X-User-Roles', '')
    roles_str = service_roles if service_roles else legacy_roles
    g.roles = roles_str.split(',') if roles_str else []

# Add this after the imports section
import locale

# Safely set the locale for date formatting
def setup_locale():
    try:
        # Try to set Russian locale
        if sys.platform == 'win32':
            locale.setlocale(locale.LC_TIME, 'rus_rus')
        else:
            locale.setlocale(locale.LC_TIME, 'ru_RU.UTF-8')
    except locale.Error:
        try:
            # Fallback to a more common locale format
            locale.setlocale(locale.LC_TIME, 'ru')
        except locale.Error:
            # If all else fails, use default locale
            locale.setlocale(locale.LC_TIME, '')
            print("Warning: Could not set Russian locale. Using system default.")


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        
        if not Status.query.filter_by(id=0).first():
            db.session.add(Status(id=0, name='Ждёт проверки',  is_start = True, is_final=False))
            db.session.add(Status(id=1, name='Проверка отделом аналитики', is_final=False))
            db.session.add(Status(id=10, name='Проверка колл центром', is_final=False))
            db.session.add(Status(id=20, name='Проверка Коммерческим Директором', is_final=False))
            db.session.add(Status(id=200, name='Акцептовано к оплате', is_final=False))
            db.session.add(Status(id=300, name='Оплачено', is_final=True))
            db.session.add(Status(id=500, name='Отказано', is_final=True))
            db.session.commit()
        
        print(timestamp := datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        # services.add_users_from_excel()
        if scheduler.get_job('daily_update_job'):
            print(f"Scheduled daily update task. {scheduler.get_job('daily_update_job').next_run_time}")

    setup_locale() 
    app.run(host='0.0.0.0', port=80, debug=True)

