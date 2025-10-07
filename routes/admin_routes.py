"""Маршруты для администрирования"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from services import fetch_data_from_mysql
from .auth_routes import get_current_user
from models import *
from services import withdrawal_service
from permission_utils import (
    requires_admin_access, 
    get_allowed_statuses_for_user, 
    get_default_status_filter,
    can_change_status_to,
    can_change_status_from_to,
    get_user_role_type,
    get_allowed_status_changes_for_user,
    has_permission
)
from status_permissions import (
    get_user_status_summary,
    get_all_status_permissions,
    format_permission_name,
    ROLE_PERMISSION_PRESETS
)
import utils
import os


admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/debug/current-user', methods=['GET'])
def debug_current_user():
    """Отладочный маршрут для проверки текущего пользователя"""
    from flask import jsonify
    
    # Выводим все заголовки
    print("=== ALL HEADERS ===")
    for header, value in request.headers:
        print(f"{header}: {value}")
    print("==================")
    
    try:
        user = get_current_user()
        
        if not user:
            return jsonify({
                'status': 'no_user',
                'message': 'Пользователь не найден',
                'headers': dict(request.headers)
            })
        
        user_info = {
            'status': 'user_found',
            'user': {
                'id': user.id,
                'login': user.login,
                'role': user.role,
                'auth_user_id': user.auth_user_id,
                'full_name': user.user_data.full_name if user.user_data else None
            },
            'headers': dict(request.headers),
            'admin_access': user.role in ['admin', 'manager', 'call-center']
        }
        
        return jsonify(user_info)
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e),
            'headers': dict(request.headers)
        })


@admin_bp.route('/debug/permissions', methods=['GET'])
def debug_permissions():
    """Отладочный маршрут для проверки разрешений пользователя"""
    from permission_utils import get_user_permissions
    
    permissions_summary = get_user_status_summary()
    role_type = get_user_role_type()
    user_permissions = get_user_permissions()
    
    # Получаем все доступные разрешения для справки
    all_permissions = get_all_status_permissions()
    
    return jsonify({
        'user_role_type': role_type,
        'raw_permissions': user_permissions,
        'detailed_summary': permissions_summary,
        'all_available_permissions': all_permissions,
        'formatted_permissions': {perm: format_permission_name(perm) for perm in all_permissions},
        'role_presets': ROLE_PERMISSION_PRESETS
    })


@admin_bp.route('/debug/permissions-ui', methods=['GET'])
def debug_permissions_ui():
    """UI для отладки разрешений"""
    permissions_summary = get_user_status_summary()
    role_type = get_user_role_type()
    
    # Получаем все доступные разрешения для справки
    all_permissions = get_all_status_permissions()
    formatted_permissions = {perm: format_permission_name(perm) for perm in all_permissions}
    
    return render_template('debug_permissions.html',
                         role_type=role_type,
                         permissions_summary=permissions_summary,
                         all_permissions=all_permissions,
                         formatted_permissions=formatted_permissions,
                         role_presets=ROLE_PERMISSION_PRESETS)


@admin_bp.route('/admin', methods=['GET'])
def admin_panel():
    """Административная панель для управления рефералами."""
    
    user = get_current_user()
    
    if not user:
        flash('Доступ запрещен - пользователь не найден', 'error')
        return redirect(url_for('referal.profile'))
        
    # Check permissions instead of hardcoded roles
    if not requires_admin_access():
        flash('Доступ запрещен - недостаточно прав', 'error')
        return redirect(url_for('referal.profile'))
    
    
    # Get user role type based on permissions
    user_role_type = get_user_role_type()
    
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
        # Используем функцию для получения фильтра по умолчанию на основе разрешений
        default_status = get_default_status_filter()
        if default_status:
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

    selected_statuses = []
    status_ids = []

    # Получаем разрешенные статусы на основе разрешений пользователя
    ALL_STATUSES = get_allowed_statuses_for_user()
    
    # Получаем доступные статусы для изменения
    allowed_status_changes = get_allowed_status_changes_for_user()
    
    # Для фильтра используем только статусы для просмотра
    # Для выпадающего списка изменения будем использовать allowed_status_changes отдельно
    filter_status_ids = ALL_STATUSES
         
    if status_filter:
        try:
            statuses = status_filter.split(',')
            for status in statuses:
                if status.isdigit():
                    status_id = int(status)
                    # Проверяем, может ли пользователь видеть этот статус (только статусы для просмотра в фильтре)
                    if status_id in filter_status_ids:
                        status_ids.append(status_id)
                    else:
                        flash(f'У вас нет прав для просмотра статуса: {status}', 'warning')
                else:
                    flash(f'Неверный формат статуса: {status}', 'warning')
            if status_ids:
                query = query.filter(Referal.status_id.in_(status_ids))
                selected_statuses = status_ids
        except ValueError:
            # Если в параметре что-то не то, игнорируем его
            flash('Получен неверный формат статусов в фильтре.', 'warning')
            pass 
    else:
        # СТАНДАРТНОЕ ПОВЕДЕНИЕ: Показываем статусы по умолчанию для роли пользователя (только для просмотра)
        INCLUDED_STATUSES = filter_status_ids  # Используем только статусы для просмотра
        if INCLUDED_STATUSES:
            query = query.filter(Referal.status_id.in_(INCLUDED_STATUSES))
            selected_statuses = [s.id for s in Status.query.filter(Status.id.in_(INCLUDED_STATUSES)).all()]
    
    # Для фильтра используем только статусы для просмотра (filter_status_ids)
    # Но для шаблона нужны также статусы для изменения, чтобы показать их названия в выпадающем списке
    template_status_ids = list(set(filter_status_ids + allowed_status_changes))
    statuses = [s for s in Status.query.filter(Status.id.in_(template_status_ids)).all()]
    
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
    referals = pagination.items

    # Обогащаем каждый реферал данными MacroContact
    for referal in referals:
        if referal.contact_id:
            referal.macro_contacts = MacroContact.query.filter_by(contacts_id=referal.contact_id).all()
            referal.macro_contact = referal.macro_contacts[0] if referal.macro_contacts else None
        else:
            referal.macro_contacts = []
            referal.macro_contact = None
    
    
    all_statuses_in_db = Status.query.all()
    return render_template('admin.html', 
                          current_user=user,
                          referals=referals,
                          pagination=pagination,
                          current_filters={
                              'status': status_filter,
                              'name': name_filter,
                              'phone': phone_filter,
                              'contract': contract_filter,
                              'contact_id': contact_id_filter,
                              'user': user_filter,
                              'per_page': per_page
                          },
                          selected_statuses=selected_statuses,
                          statuses=statuses,
                          filter_statuses=[s for s in statuses if s.id in filter_status_ids],  # Только для фильтра
                          current_sort=sort_param,
                          sort_fields=sort_fields,
                          user_role_type=user_role_type,
                          can_change_status_from_to=can_change_status_from_to,
                          allowed_status_changes=allowed_status_changes)


@admin_bp.route('/update_withdrawal_stage/<int:referal_id>', methods=['POST'])
def update_withdrawal_stage(referal_id):
    """Обновление статуса реферала."""
    current_user = get_current_user()
    if not current_user or not requires_admin_access():
        flash('Доступ запрещен', 'error')
        return redirect(url_for('referal.profile'))

    referal = Referal.query.get_or_404(referal_id)
    withdrawal_stage = int(request.form.get('withdrawal_stage'))
    
    # Проверяем, может ли пользователь изменить статус с текущего на указанный
    if not can_change_status_from_to(referal.status_id, withdrawal_stage):
        flash('У вас нет прав для изменения статуса с текущего на выбранный', 'error')
        return redirect(url_for('admin.admin_panel'))
    
    user = User.query.get(referal.user_id)
    
    from flask import session
    filter_keys = ['status', 'name', 'phone', 'contract', 'contact_id', 'user', 'per_page', 'sort', 'page']
    return_params = {}
    # 1. Сначала пробуем получить из формы (скрытые поля)
    for key in request.form.keys():
        if key.startswith('return_'):
            param_name = key.replace('return_', '')
            return_params[param_name] = request.form[key]
    # 2. Если не переданы, пробуем получить из referer (URL)
    if not return_params:
        referer_url = request.headers.get('Referer', '')
        from urllib.parse import urlparse, parse_qs
        if referer_url:
            parsed = urlparse(referer_url)
            qs = parse_qs(parsed.query)
            for key in filter_keys:
                val = qs.get(key)
                if val:
                    return_params[key] = val[0]
    # 3. Если не переданы, пробуем получить из сессии
    if not return_params:
        for key in filter_keys:
            val = session.get(f'admin_filter_{key}')
            if val is not None:
                return_params[key] = val

    # 4. Сохраняем фильтры в сессии для будущих переходов
    for key in filter_keys:
        if key in return_params:
            session[f'admin_filter_{key}'] = return_params[key]

    
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
        payment_email = os.getenv('PAYMENT_MANAGER_EMAIL')

        utils.send_email(
            os.getenv('PAYMENT_MANAGER_EMAIL'),
            'Запрос на выплату рефереру',
            f'{user.user_data.full_name} запросил вывод средств за реферала:\nФИО: {referal.referal_data.full_name}\nMacro ID: {referal.contact_id}\n пожалуйста проверьте меню реферальной программы и подтвердите/отклоните выплату.'
        )



    elif withdrawal_stage == 300:
        utils.send_email(
            os.getenv('MAIN_ADMIN_EMAIL'),
            'Реферал был оплачен рефереру',
            f'Реферал от {user.user_data.full_name} был помечен как оплаченый:\nФИО: {referal.referal_data.full_name}\nMacro ID: {referal.contact_id}\n'
        )
        if not referal.balance_withdrawn:
            user.pending_withdrawal -= referal.withdrawal_amount
            user.total_withdrawal += referal.withdrawal_amount
            referal.balance_withdrawn = True

    elif withdrawal_stage == 500:
        rejection_reason = request.form.get('rejection_reason', '')
        if not rejection_reason:
            flash('Пожалуйста, укажите причину отказа', 'error')
            return redirect(url_for('admin.admin_panel', **return_params))
        referal.rejection_reason = rejection_reason
        rejecter_name = current_user.user_data.full_name
        utils.send_email(
            os.getenv('MAIN_ADMIN_EMAIL'),
            'Реферал не прошёл проверку',
            f"""
            Реферал от {user.user_data.full_name} не прошёл проверку {referal.status_name}\n
            Причина: {rejection_reason}.\n
            Отклонил: {rejecter_name}\n
            Данные реферала:\n
            ФИО: {referal.referal_data.full_name}\n
            Macro ID: {referal.contact_id}\n"""
        )
        user.pending_withdrawal -= referal.withdrawal_amount

    referal.status_id = withdrawal_stage
    referal.status_name = Status.query.get(withdrawal_stage).name
    db.session.commit()
    flash('Статус реферала обновлен успешно', 'success')

    # --- Восстанавливаем параметры фильтрации из referer (URL) если их нет в форме ---
    

    # 5. Редиректим с фильтрами, если есть
    if return_params:
        return redirect(url_for('admin.admin_panel', **return_params))
    else:
        return redirect(url_for('admin.admin_panel'))

@admin_bp.route('/force_update', methods=['GET'])
def force_update():
    """Принудительное обновление всех рефералов. ТОЛЬКО для администраторов!"""
    user = get_current_user()
    
    # Проверяем что пользователь существует
    if not user:
        print("⛔ Force update access DENIED - No user found")
        flash('Доступ запрещен - пользователь не найден', 'error')
        return redirect(url_for('referal.profile'))
    
    # Проверяем права: только админ системы или админ сервиса
    user_role = get_user_role_type()
    has_admin_permission = has_permission('referal.admin.force_update')
    is_system_admin = user_role == 'admin'
    
    if not (is_system_admin or has_admin_permission):
        username = request.headers.get('X-User-Name', 'Unknown')
        print(f"⛔ Force update access DENIED | User: {username} | Role: {user_role} | Has permission: {has_admin_permission}")
        flash('Доступ запрещен - недостаточно прав для принудительной синхронизации', 'error')
        return redirect(url_for('admin.admin_panel'))
    
    # Логируем начало принудительной синхронизации
    username = request.headers.get('X-User-Name', user.login if hasattr(user, 'login') else 'Unknown')
    print(f"🔄 Force update STARTED by admin | User: {username} | Role: {user_role}")
    
    try:
        fetch_data_from_mysql()
        print(f"✅ Force update COMPLETED by {username}")
        flash('Данные успешно обновлены из MySQL', 'success')
    except Exception as e:
        print(f"❌ Force update FAILED by {username} | Error: {str(e)}")
        flash(f'Ошибка при обновлении данных: {str(e)}', 'error')
    
    return redirect(url_for('admin.admin_panel'))