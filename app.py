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
from routes import auth_bp, referal_bp, admin_bp, document_bp, user_bp  # Убрали main_bp

import pandas as pd
from werkzeug.security import generate_password_hash
from dotenv import load_dotenv
import os
from flask_apscheduler import APScheduler
from prefix_middleware import PrefixMiddleware

import services
import utils
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
    PREFERRED_URL_SCHEME='http'
)

# Инициализация базы данных
db.init_app(app)

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

# Add prefix middleware after registering blueprint but before initializing scheduler
# This will strip the /referal prefix when running behind proxy
if os.getenv('BEHIND_PROXY', 'false').lower() == 'true':
    app.wsgi_app = PrefixMiddleware(app.wsgi_app, prefix='/referal')


@app.route('/')
def home():
    """Корневой маршрут - редирект на профиль рефералов."""
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
    g.roles = request.headers.get('X-User-Roles', '').split(',') if request.headers.get('X-User-Roles') else []

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
            db.session.add(Status(id=0, name='Не начата',  is_start = True, is_final=False))
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
    app.run(host='0.0.0.0', port=80, debug=True)
