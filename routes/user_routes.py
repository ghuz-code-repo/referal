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
        return redirect(url_for('referal.profile'))
    
    # Получаем или создаем данные пользователя
    if not user.user_data:
        user.user_data = UserData(user_id=user.id)
        db.session.add(user.user_data)
        db.session.commit()
    
    return render_template('user_profile.html', current_user=user)


@user_bp.route('/update_user_info', methods=['POST'])  
def update_user_info():
    """Функция для обновления информации о пользователе."""
    user = get_current_user()
    if not user:
        flash('Пожалуйста, войдите в систему', 'error')
        return redirect(url_for('referal.profile'))
    
    # Получаем или создаем данные пользователя
    userinfo = UserData.query.filter_by(user_id=user.id).first()
    if not userinfo:
        userinfo = UserData(user_id=user.id)
        db.session.add(userinfo)
    
    # Обновляем данные из формы (пустые строки сохраняем как None)
    userinfo.full_name = request.form.get('name', '').strip() or None
    userinfo.passport_number = request.form.get('passport_number', '').strip() or None
    userinfo.passport_giver = request.form.get('passport_giver', '').strip() or None
    userinfo.passport_adress = request.form.get('passport_adress', '').strip() or None
    userinfo.mail_adress = request.form.get('mail_adress', '').strip() or None
    userinfo.pinfl = request.form.get('pinfl', '').strip() or None
    userinfo.trans_schet = request.form.get('trans_schet', '').strip() or None
    userinfo.card_number = request.form.get('card_number', '').strip() or None
    userinfo.bank_name = request.form.get('bank_name', '').strip() or None
    userinfo.mfo = request.form.get('mfo', '').strip() or None
    userinfo.phone = request.form.get('phone', '').strip() or None
    userinfo.e_mail = request.form.get('e_mail', '').strip() or None
    
    # Обработка даты выдачи паспорта
    passport_date_str = request.form.get('passport_date', '').strip()
    if passport_date_str:
        try:
            from datetime import datetime
            userinfo.passport_date = datetime.strptime(passport_date_str, '%Y-%m-%d').date()
        except ValueError:
            flash('Неверный формат даты выдачи паспорта', 'error')
            return redirect(url_for('user.user_profile'))
    else:
        userinfo.passport_date = None
    
    try:
        db.session.commit()
        flash('Данные пользователя обновлены', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при обновлении данных: {e}', 'error')
    
    return redirect(url_for('user.user_profile'))
