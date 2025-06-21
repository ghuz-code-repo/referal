"""Маршруты для администрирования"""

from flask import Blueprint, render_template, request, redirect, url_for, flash
from .auth_routes import get_current_user
from models import *
from services import withdrawal_service
import utils
import os

admin_bp = Blueprint('admin', __name__)


@admin_bp.route('/admin')
def admin_panel():
    """Маршрут для отображения административной панели."""
    user = get_current_user()
    if not user and (not user.role == 'admin' or not user.role == 'manager'):
        flash('Access denied', 'error')
        return redirect(url_for('referal.profile'))
    
    # Получаем параметры фильтрации, пагинации и сортировки
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 5, type=int)
    status_filter = request.args.get('status', '')
    name_filter = request.args.get('name', '')
    phone_filter = request.args.get('phone', '')
    contract_filter = request.args.get('contract', '')
    contact_id_filter = request.args.get('contact_id', '')
    user_filter = request.args.get('user', '')
    sort_param = request.args.get('sort', '')
    
    # Парсим сортировку
    sort_fields = []
    if sort_param:
        for sort_item in sort_param.split(','):
            if ':' in sort_item:
                field, order = sort_item.split(':')
                sort_fields.append({'field': field, 'order': order})

    # Базовый запрос с JOIN
    query = Referal.query.join(User, Referal.user_id == User.id).filter(Referal.status_id != -1)
    
    # Определяем, нужно ли присоединять ReferalData
    needs_referal_data_join = (name_filter or phone_filter or contract_filter or 
                              any(sf['field'] in ['name', 'phone', 'contract'] for sf in sort_fields))
    
    if needs_referal_data_join:
        query = query.join(ReferalData)
    
    # Применяем фильтры

    if status_filter:
        if status_filter == '-1': 
            if user.role == 'manager':
                query = query.filter(Referal.status_id == 200)
                # недостижимый код
            elif user.role == 'admin':
                query = query.filter(Referal.status_id != -1)
        else:
            query = query.filter(Referal.status_id == int(status_filter))
    else:
        if user.role == 'manager':
            query = query.filter(Referal.status_id == 200)
            # недостижимый код
        elif user.role == 'admin':
            query = query.filter(Referal.status_id == 1)
            # недостижимый код

    print(f"Filtering by status: {status_filter}, user role: {user.role}")
    
    if name_filter:
        query = query.filter(ReferalData.full_name.ilike(f'%{name_filter}%'))
    
    if phone_filter:
        query = query.filter(ReferalData.phone_number.ilike(f'%{phone_filter}%'))
    
    if contract_filter:
        query = query.filter(ReferalData.contract_number.ilike(f'%{contract_filter}%'))
    
    if contact_id_filter:
        query = query.filter(Referal.contact_id.ilike(f'%{contact_id_filter}%'))
        
    if user_filter:
        query = query.filter(User.login.ilike(f'%{user_filter}%'))
    
    # Применяем сортировку
    if sort_fields:
        order_by_clauses = []
        for sort_field in sort_fields:
            field = sort_field['field']
            order = sort_field['order']
            
            if field == 'name':
                clause = ReferalData.full_name.desc() if order == 'desc' else ReferalData.full_name.asc()
            elif field == 'phone':
                clause = ReferalData.phone_number.desc() if order == 'desc' else ReferalData.phone_number.asc()
            elif field == 'contract':
                clause = ReferalData.contract_number.desc() if order == 'desc' else ReferalData.contract_number.asc()
            elif field == 'user':
                clause = User.login.desc() if order == 'desc' else User.login.asc()
            elif field == 'status':
                clause = Referal.status_id.desc() if order == 'desc' else Referal.status_id.asc()
            elif field == 'amount':
                clause = Referal.withdrawal_amount.desc() if order == 'desc' else Referal.withdrawal_amount.asc()
            else:
                continue
            
            order_by_clauses.append(clause)
        
        if order_by_clauses:
            query = query.order_by(*order_by_clauses)
    else:
        query = query.order_by(Referal.id.desc())
    
    # Пагинация
    pagination = query.paginate(
        page=page, 
        per_page=per_page, 
        error_out=False
    )
    withdrawal_requests = pagination.items
    
    statuses = Status.query.filter(Status.id != -1).all()

    referals = pagination.items

    # Обогащаем каждый реферал данными MacroContact
    for referal in referals:
        if referal.contact_id:
            referal.macro_contacts = MacroContact.query.filter_by(contacts_id=referal.contact_id).all()
            referal.macro_contact = referal.macro_contacts[0] if referal.macro_contacts else None
        else:
            referal.macro_contacts = []
            referal.macro_contact = None
    
    print(f"Found {len(referals)} referals for user {user.login}")


    return render_template('admin.html', 
                          current_user=user,
                          withdrawal_requests=withdrawal_requests,
                          pagination=pagination,
                          statuses=statuses,
                          referals=referals,
                          current_filters={
                              'status': status_filter,
                              'name': name_filter,
                              'phone': phone_filter,
                              'contract': contract_filter,
                              'contact_id': contact_id_filter,
                              'user': user_filter,
                              'per_page': per_page
                          },
                          current_sort=sort_param,
                          sort_fields=sort_fields)


@admin_bp.route('/update_withdrawal_stage/<int:referal_id>', methods=['POST'])
def update_withdrawal_stage(referal_id):
    """Маршрут для обновления статуса заявки на вывод средств."""
    user = get_current_user()
    if not user or not (user.role == 'admin' or user.role == 'manager'):
        flash('Access denied', 'error')
        return redirect(url_for('referal.profile'))

    referal = Referal.query.get_or_404(referal_id)
    withdrawal_stage = int(request.form.get('withdrawal_stage'))
    rejection_reason = request.form.get('rejection_reason', '')
    
    referal.status_id = withdrawal_stage
    referal.status_name = Status.query.get(withdrawal_stage).name
    
    if withdrawal_stage == 10:
        utils.send_email(
            os.getenv('CALL-CENTER-MANAGER_EMAIL'),
            'Запрос на проверку реферала',
            f'Пожалуйста созвонитесь с рефералом от {user.user_data.full_name}: ФИО: {referal.referal_data.full_name} Телефон: {referal.referal_data.phone_number} для проверки его данных.\n'
        )
    if withdrawal_stage == 200:
        utils.send_email(
            os.getenv('CALL-CENTER-MANAGER_EMAIL'),
            'Запрос на выплату рефереру',
            f'{user.user_data.full_name} запросил вывод средств за реферала:\nФИО: {referal.referal_data.full_name}\nMacro ID: {referal.contact_id}\n пожалуйста проверьте меню реферальной программы и подтвердите/отклоните выплату.'
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
