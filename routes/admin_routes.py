"""Маршруты для администрирования"""

from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import *
from .auth_routes import get_current_user
from services import withdrawal_service
import utils
import os

admin_bp = Blueprint('admin', __name__)


@admin_bp.route('/admin')
def admin_panel():
    """Маршрут для отображения административной панели."""
    user = get_current_user()
    if not user or not user.role == 'admin':
        flash('Access denied', 'error')
        return redirect(url_for('referal.profile'))

    withdrawal_requests = Referal.query.filter(Referal.status_id != 0).all()
    statuses = Status.query.filter(Status.id != 0).all()
    return render_template('admin.html', 
                          current_user=user,
                          withdrawal_requests=withdrawal_requests, 
                          statuses=statuses)


@admin_bp.route('/update_withdrawal_stage/<int:referal_id>', methods=['POST'])
def update_withdrawal_stage(referal_id):
    """Маршрут для обновления статуса заявки на вывод средств."""
    user = get_current_user()
    if not user or not user.role == 'admin':
        flash('Access denied', 'error')
        return redirect(url_for('referal.profile'))

    referal = Referal.query.get_or_404(referal_id)
    withdrawal_stage = int(request.form.get('withdrawal_stage'))
    rejection_reason = request.form.get('rejection_reason', '')
    
    referal.status_id = withdrawal_stage
    referal.status_name = Status.query.get(withdrawal_stage).name
    
    if withdrawal_stage == 10:
        utils.send_email(
            os.getenv('MANAGER_EMAIL'),
            'Запрос на проверку реферала',
            f'Пожалуйста созвонитесь с рефералом от {user.user_data.full_name}: ФИО: {referal.referal_data.full_name} Телефон: {referal.referal_data.phone_number} для проверки его данных.\n'
        )

    if withdrawal_stage == 500:
        referal.rejection_reason = rejection_reason
        user = User.query.get(referal.user_id)
        user.pending_withdrawal -= referal.withdrawal_amount
    elif withdrawal_stage == 200 and not referal.balance_withdrawn:
        user = User.query.get(referal.user_id)
        user.pending_withdrawal -= referal.withdrawal_amount
        user.total_withdrawal += referal.withdrawal_amount
        referal.balance_withdrawn = True

    db.session.commit()
    flash('Withdrawal stage updated successfully', 'success')
    return redirect(url_for('admin.admin_panel'))
