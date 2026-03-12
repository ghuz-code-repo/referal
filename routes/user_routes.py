"""Маршруты для работы с пользователями"""

from flask import Blueprint, render_template, request, redirect, url_for, flash
from .auth_routes import get_current_user
from models import *

user_bp = Blueprint('user', __name__)


@user_bp.route('/profile', methods=['GET'])
def user_profile():
    """Отображение профиля пользователя."""
    user = get_current_user()
    if not user:
        flash('Пожалуйста, войдите в систему', 'error')
        return redirect(request.referrer or '/')
    
    # Получаем или создаем данные пользователя
    if not user.user_data:
        user.user_data = UserData(user_id=user.id)
        db.session.add(user.user_data)
        db.session.commit()
    
    return render_template('user_profile.html', current_user=user)


@user_bp.route('/update_user_info', methods=['POST'])  
def update_user_info():
    """Функция для обновления информации о пользователе.
    
    TODO: DEPRECATED - Documents should be updated in Auth-Service, not locally.
    This endpoint should redirect to Auth-Service for document updates.
    Currently disabled to prevent writing documents to local database.
    """
    user = get_current_user()
    if not user:
        flash('Пожалуйста, войдите в систему', 'error')
        return redirect(request.referrer or '/')
    
    # ❌ DEPRECATED: Documents are READ-ONLY from Auth-Service
    # Do not save documents to local database
    flash('Обновление документов должно происходить через Auth-Service. Документы доступны только для чтения.', 'warning')
    return redirect(url_for('user.user_profile'))
