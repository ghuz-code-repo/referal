"""Маршруты для работы с пользователями"""

from flask import Blueprint, request, redirect, url_for, flash
from .auth_routes import get_current_user
from models import *

user_bp = Blueprint('user', __name__)


@user_bp.route('/update_user_info', methods=['POST'])  
def update_user_info():
    """Функция для обновления информации о пользователе."""
    user = get_current_user()
    if not user:
        flash('Пожалуйста, войдите в систему', 'error')
        return redirect(url_for('main.main'))
    
    userinfo = UserData.query.filter_by(user_id=user.id).first()
    if not userinfo:
        userinfo = UserData(
            user_id=user.id,
            name=request.form.get('name'),
            passport_number=request.form.get('passport_number'),
            passport_giver=request.form.get('passport_giver'),
            passport_date=request.form.get('passport_date'),
            passport_adress=request.form.get('passport_adress'),
            mail_adress=request.form.get('mail_adress'),
            pinfl=request.form.get('pinfl'),
            trans_schet=request.form.get('trans_schet'),
            card_number=request.form.get('card_number'),
            bank_name=request.form.get('bank_name'),
            mfo=request.form.get('mfo'),
            phone=request.form.get('phone'),
            e_mail=request.form.get('e_mail')
        )
        db.session.add(userinfo)
    
    try:
        db.session.commit()
        flash('Данные пользователя обновлены', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при обновлении данных: {e}', 'error')
    
    return redirect(url_for('referal.profile'))
