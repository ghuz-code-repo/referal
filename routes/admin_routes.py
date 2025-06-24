"""Маршруты для администрирования"""

from flask import Blueprint, render_template, request, redirect, url_for, flash
from services import fetch_data_from_mysql
from .auth_routes import get_current_user
from models import *
from services import withdrawal_service
import utils
import os

admin_bp = Blueprint('admin', __name__)


@admin_bp.route('/admin', methods=['GET'])
def admin_panel():
    """Административная панель для управления рефералами."""
    user = get_current_user()
    if not user or user.role not in ['admin', 'manager', 'call-center']:
        flash('Доступ запрещен', 'error')
        return redirect(url_for('referal.profile'))
    
    # Получаем параметры из URL
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    # Получаем фильтры
    status_filter = request.args.get('status', '')
    name_filter = request.args.get('name', '')
    phone_filter = request.args.get('phone', '')
    contract_filter = request.args.get('contract', '')
    contact_id_filter = request.args.get('contact_id', '')
    user_filter = request.args.get('user', '')
    
    # Проверяем наличие заголовка Referer для определения "чистого" захода
    referer = request.headers.get('Referer', '')
    is_direct_access = not referer or '/admin' not in referer
    
    # УСТАНАВЛИВАЕМ ФИЛЬТРЫ ПО УМОЛЧАНИЮ ТОЛЬКО ПРИ ПРЯМОМ ЗАХОДЕ
    if not status_filter and not any([name_filter, phone_filter, contract_filter, contact_id_filter, user_filter]) and is_direct_access:
        # Устанавливаем фильтр по умолчанию только при первом заходе на страницу
        if user.role == 'manager':
            default_status = '200'
        elif user.role == 'call-center':
            default_status = '10'
        else:  # admin
            default_status = '1'
        
        # Перенаправляем с фильтром по умолчанию
        return redirect(url_for('admin.admin_panel', status=default_status))
    
    # Получаем сортировку
    sort_param = request.args.get('sort', '')
    sort_fields = []
    if sort_param:
        for sort_item in sort_param.split(','):
            if ':' in sort_item:
                field, order = sort_item.split(':')
                sort_fields.append({'field': field, 'order': order})
    
    # Базовый запрос
    query = Referal.query

    # Применяем фильтры
    if status_filter:
        if status_filter == '-1':
            # Админ выбрал "Все" - не применяем фильтр по статусу
            pass
        elif status_filter == 'all_manager':
            # Менеджер выбрал "Все доступные" - фильтруем по доступным статусам
            query = query.filter(Referal.status_id.in_([200, 300, 500]))
        elif status_filter == 'no_status':
            query = query.filter(Referal.status_id == 0)
        else:
            query = query.filter(Referal.status_id == int(status_filter))
    else:
        # Если нет фильтра по статусу для call-center - показываем все их доступные
        if user.role == 'call-center':
            query = query.filter(Referal.status_id == 10)
    
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
    
    # Для сортировки по user.login делаем join с User
    need_user_join = False
    need_referal_data_join = False
    if sort_fields:
        for sort_field in sort_fields:
            if sort_field['field'] == 'user':
                need_user_join = True
            if sort_field['field'] in ['name', 'phone', 'contract']:
                need_referal_data_join = True
    if need_user_join:
        query = query.join(User, Referal.user_id == User.id)
    if need_referal_data_join:
        query = query.join(ReferalData, Referal.referal_data)

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
                          referals=referals,
                          pagination=pagination,
                          statuses=Status.query.all(),
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
    """Обновление статуса реферала."""
    user = get_current_user()
    if not user or user.role not in ['admin', 'manager', 'call-center']:
        flash('Доступ запрещен', 'error')
        return redirect(url_for('referal.profile'))

    referal = Referal.query.get_or_404(referal_id)
    withdrawal_stage = int(request.form.get('withdrawal_stage'))
    rejection_reason = request.form.get('rejection_reason', '')
    
    referal.status_id = withdrawal_stage
    referal.status_name = Status.query.get(withdrawal_stage).name
    
    if withdrawal_stage == 1:
        utils.send_email(
            os.getenv('MAIN_ADMIN_EMAIL'),
            'Реферал поступил на проверку отделом аналитики',
            f'Реферал от {user.user_data.full_name} поступил на проверку отделу аналитики:\nФИО: {referal.referal_data.full_name}\nMacro ID: {referal.contact_id}\n'
        )
    
    elif withdrawal_stage == 20:
        utils.send_email(
            os.getenv('MAIN_ADMIN_EMAIL'),
            'Реферал прошёл проверку колл-центром',
            f'Реферал от {user.user_data.full_name} прошёл проверку колл-центром:\nФИО: {referal.referal_data.full_name}\nMacro ID: {referal.contact_id}\n'
        )
        
    elif withdrawal_stage == 10:
        utils.send_email(
            os.getenv('CALL_CENTER_MANAGER_EMAIL'),
            'Запрос на проверку реферала',
            f'Пожалуйста созвонитесь с рефералом от {user.user_data.full_name}: ФИО: {referal.referal_data.full_name} Телефон: {referal.referal_data.phone_number} для проверки его данных после чего обязательно измените статус реферала в системе.\n'
        )
        
    elif withdrawal_stage == 200:
        print(f"DEBUG: Withdrawal stage set to 200 for referal {referal.id} by user {user.login}")
        payment_email = os.getenv('PAYMENT_MANAGER_EMAIL')
        print(f"DEBUG: PAYMENT_MANAGER_EMAIL from env: {payment_email}")
        if payment_email:
            utils.send_email(
                payment_email,
                'Запрос на выплату рефереру',
                f'{user.user_data.full_name} запросил вывод средств за реферала:\nФИО: {referal.referal_data.full_name}\nMacro ID: {referal.contact_id}\n пожалуйста проверьте меню реферальной программы и подтвердите/отклоните выплату.'
            )
            print(f"DEBUG: Sending email to {payment_email} for referal {referal.id} with amount {referal.withdrawal_amount}")
        else:
            print("ERROR: PAYMENT_MANAGER_EMAIL is not set in environment variables!")


    elif withdrawal_stage == 300:
        utils.send_email(
            os.getenv('MAIN_ADMIN_EMAIL'),
            'Реферал был оплачен рефереру',
            f'Реферал от {user.user_data.full_name} был помечен как оплаченый:\nФИО: {referal.referal_data.full_name}\nMacro ID: {referal.contact_id}\n'
        )
        if not referal.balance_withdrawn:
            user = User.query.get(referal.user_id)
            user.pending_withdrawal -= referal.withdrawal_amount
            user.total_withdrawal += referal.withdrawal_amount
            referal.balance_withdrawn = True

    elif withdrawal_stage == 500:
        utils.send_email(
            os.getenv('MAIN_ADMIN_EMAIL'),
            'Реферал не прошёл проверку',
            f'Реферал от {user.user_data.full_name} не прошёл проверку:\nФИО: {referal.referal_data.full_name}\nMacro ID: {referal.contact_id}\n'
        )
        referal.rejection_reason = rejection_reason
        user = User.query.get(referal.user_id)
        user.pending_withdrawal -= referal.withdrawal_amount

    db.session.commit()
    flash('Статус реферала обновлен успешно', 'success')
    
    # Восстанавливаем параметры фильтрации из формы
    return_params = {}
    for key in request.form.keys():
        if key.startswith('return_'):
            param_name = key.replace('return_', '')
            return_params[param_name] = request.form[key]
    
    # Если есть сохраненные параметры, используем их для редиректа
    if return_params:
        return redirect(url_for('admin.admin_panel', **return_params))
    else:
        # Иначе просто возвращаемся на админ панель
        return redirect(url_for('admin.admin_panel'))

@admin_bp.route('/force_update', methods=['GET'])
def force_update():
    """Принудительное обновление всех рефералов."""
    user = get_current_user()
    if not user or user.role != 'admin':
        flash('Доступ запрещен', 'error')
    fetch_data_from_mysql()