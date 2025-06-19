from .auth_routes import auth_bp
from .referal_routes import referal_bp
from .admin_routes import admin_bp
from .document_routes import document_bp
from .main_routes import main_bp
from .user_routes import user_bp

# Экспортируем все Blueprint'ы для использования в app.py
__all__ = ['auth_bp', 'referal_bp', 'admin_bp', 'document_bp', 'main_bp', 'user_bp']
