"""Маршруты для администрирования"""

import logging
import sys
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app, send_file, abort
from sqlalchemy import or_, cast, String, func, Date
from services import fetch_data_from_mysql
from services import notification_service
from notification_client import get_notification_client
from .auth_routes import get_current_user
from models import *
from services import withdrawal_service
from utils import get_user_full_name_from_auth
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
import requests

# Настраиваем логирование для gunicorn
logger = logging.getLogger('gunicorn.error')




admin_bp = Blueprint('admin', __name__)


def send_admin_deal_status_notification(referal_deal, admin_user, old_status_id, new_status_id, new_status_name, rejection_reason=None):
    """Send notification about deal status change by admin to users with appropriate permissions.
    
    Использует permission-based систему из notification_utils для определения получателей.
    Для статуса 500 (Отказ) дополнительно уведомляет самого пользователя-реферала.
    """
    try:
        from notification_utils import get_notification_recipients_for_status, get_status_display_name

        # Получаем общие данные о договоре
        agreement_number = referal_deal.deal.agreement_number if referal_deal.deal else 'Неизвестно'
        referal_name = referal_deal.referal.referal_data.full_name if referal_deal.referal and referal_deal.referal.referal_data else 'Неизвестно'
        referal_phone = referal_deal.referal.referal_data.phone_number if referal_deal.referal and referal_deal.referal.referal_data else 'Неизвестно'
        withdrawal_amount = referal_deal.withdrawal_amount or 0
        admin_name = get_user_full_name_from_auth(admin_user)
        status_display = get_status_display_name(new_status_id)
        old_status_display = get_status_display_name(old_status_id) if old_status_id is not None else 'Неизвестно'

        notification_client = get_notification_client()

        # --- Специальная логика для статуса 500 (Отказ): уведомляем самого пользователя ---
        if new_status_id == 500:
            # Логин портала хранится в своей же таблице пользователей — ходить
            # в auth-service за адресом больше не нужно, его подставит
            # notification-service
            user_login = None
            if referal_deal.referal and referal_deal.referal.user:
                user_login = referal_deal.referal.user.login

            if user_login:
                subject = f'Отказ по договору №{agreement_number}'
                body = f"""Уважаемый(ая) {referal_name},

К сожалению, ваш договор №{agreement_number} был отклонён."""

                if rejection_reason:
                    body += f"\n\nПричина отказа: {rejection_reason}"

                body += "\n\nЕсли у вас есть вопросы, пожалуйста, свяжитесь с нами."

                notification_client.send_email(
                    login=user_login,
                    subject=subject,
                    body=body
                )
                print(f"✅ Rejection notification sent to user {user_login} for deal {referal_deal.id}")
            else:
                print(f"⚠️ Cannot send rejection notification: user login not found for deal {referal_deal.id}")

        # --- Permission-based уведомления для всех ответственных сотрудников ---
        recipients = get_notification_recipients_for_status(new_status_id)

        if not recipients:
            print(f"⚠️ No users with notification permissions found for status {new_status_id} ({status_display}), skipping staff notification")
            return

        # Формируем тело письма для ответственных
        subject = f'Договор №{agreement_number} — статус: {status_display}'
        body = f"""Администратор {admin_name} изменил статус договора.

Детали договора:
- Номер договора: {agreement_number}
- Реферал: {referal_name} ({referal_phone})
- Сумма вывода: {withdrawal_amount:,.0f} сум
- Предыдущий статус: {old_status_display}
- Новый статус: {status_display}"""

        if new_status_id == 500 and rejection_reason:
            body += f"\n- Причина отказа: {rejection_reason}"

        body += "\n\nТребуется ваша проверка."

        # Отправляем уведомление каждому получателю с нужным разрешением
        sent_count = 0
        for recipient in recipients:
            recipient_login = recipient.get('username')
            recipient_name = recipient.get('full_name', recipient.get('username', 'Сотрудник'))

            if not recipient_login:
                print(f"⚠️ Recipient has no portal login, skipping: {recipient}")
                continue

            try:
                notification_client.send_email(
                    login=recipient_login,
                    subject=subject,
                    body=body
                )
                sent_count += 1
                print(f"📧 Status change notification sent to: {recipient_name} ({recipient_login}) for status {status_display}")
            except Exception as e:
                print(f"❌ Failed to send email to {recipient_login}: {str(e)}")

        print(f"✅ Admin status change notification process completed. Sent to {sent_count}/{len(recipients)} recipients for status {old_status_id} -> {new_status_id}")

    except Exception as e:
        print(f"❌ Failed to send admin status change notification: {str(e)}")
        import traceback
        traceback.print_exc()


@admin_bp.route('/admin', methods=['GET'])
def admin_panel():
    """Административная панель для управления рефералами и договорами."""
    
    user = get_current_user()
    
    if not user:
        flash('Доступ запрещен - пользователь не найден', 'error')
        return redirect(request.referrer or '/')
        
    # Проверка доступа через permissions (новая система)
    if not requires_admin_access():
        flash('Доступ запрещен - недостаточно прав', 'error')
        return redirect(request.referrer or '/')
    
    
    # Get user role type based on permissions
    user_role_type = get_user_role_type()
    
    # Получаем режим просмотра: 'referals' (по умолчанию) или 'deals'
    view_mode = request.args.get('view_mode', 'deals')  # По умолчанию показываем договоры
    
    # Получаем параметры из URL
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    # РАЗДЕЛЯЕМ ФИЛЬТРЫ ПО РЕЖИМАМ
    # Префикс 'r_' для рефералов, 'd_' для договоров
    if view_mode == 'referals':
        status_filter = ''  # У рефералов НЕТ статусов!
        name_filter = request.args.get('r_name', '')
        phone_filter = request.args.get('r_phone', '')
        contract_filter = request.args.get('r_contract', '')
        contact_id_filter = request.args.get('r_contact_id', '')
        user_filter = request.args.get('r_user', '')
        created_at_filter = request.args.get('r_created_at', '')
        total_withdrawal_filter = request.args.get('r_total_withdrawal', '')
        deals_count_filter = ''  # Убираем фильтр по deals_count так как это вычисляемое поле
        amount_filter = ''
        sort_param = request.args.get('r_sort', '')
    else:  # deals
        status_filter = request.args.get('d_status', '')
        name_filter = request.args.get('d_name', '')
        phone_filter = ''  # Для договоров нет фильтра по телефону
        contract_filter = request.args.get('d_contract', '')
        contact_id_filter = ''  # Для договоров нет фильтра по contact_id
        user_filter = request.args.get('d_user', '')
        created_at_filter = ''  # Для договоров нет фильтра по дате создания
        total_withdrawal_filter = ''  # Для договоров нет фильтра по выплатам
        deals_count_filter = ''  # Для договоров нет фильтра по количеству
        amount_filter = request.args.get('d_amount', '').strip()
        sort_param = request.args.get('d_sort', '')
    
    # Проверяем наличие заголовка Referer для определения "чистого" захода
    referer = request.headers.get('Referer', '')
    is_direct_access = not referer or '/admin' not in referer
    
    # УСТАНАВЛИВАЕМ ФИЛЬТРЫ ПО УМОЛЧАНИЮ ТОЛЬКО ПРИ ПРЯМОМ ЗАХОДЕ (только для договоров!)
    if view_mode == 'deals' and not status_filter and not any([name_filter, phone_filter, contract_filter, contact_id_filter, user_filter, amount_filter]) and is_direct_access:
        # Используем функцию для получения фильтра по умолчанию на основе разрешений
        default_status = get_default_status_filter()
        if default_status:
            # Перенаправляем с фильтром по умолчанию (с правильным префиксом)
            status_param = f"{'r_status' if view_mode == 'referals' else 'd_status'}"
            return redirect(url_for('admin.admin_panel', view_mode=view_mode, **{status_param: default_status}))
    
    # Получаем сортировку
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

    # Получаем разрешенные статусы на основе разрешений пользователя (только для договоров!)
    ALL_STATUSES = get_allowed_statuses_for_user()
    print(f"🔍 DEBUG: get_allowed_statuses_for_user() returned: {ALL_STATUSES}")
    print(f"🔍 DEBUG: User permissions from headers: {request.headers.get('X-User-Service-Permissions', 'NONE')}")
    print(f"🔍 DEBUG: User service roles: {request.headers.get('X-User-Service-Roles', 'NONE')}")
    
    # Получаем доступные статусы для изменения
    allowed_status_changes = get_allowed_status_changes_for_user()
    
    # Для фильтра используем только статусы для просмотра
    # Для выпадающего списка изменения будем использовать allowed_status_changes отдельно
    filter_status_ids = ALL_STATUSES
    
    # ВАЖНО: Фильтрация по статусам ТОЛЬКО для режима 'deals', у рефералов нет статусов!
    # Для рефералов просто показываем все записи
    if view_mode == 'referals':
        # Рефералы не имеют статусов - показываем все
        pass
    else:
        # Логика фильтрации статусов только для договоров (будет применена позже к ReferalDeal)
        if status_filter:
            try:
                statuses = status_filter.split(',')
                for status in statuses:
                    if status.isdigit():
                        status_id = int(status)
                        # Проверяем, может ли пользователь видеть этот статус
                        if status_id in filter_status_ids:
                            status_ids.append(status_id)
                        else:
                            flash(f'У вас нет прав для просмотра статуса: {status}', 'warning')
                    else:
                        flash(f'Неверный формат статуса: {status}', 'warning')
                
                # ВАЖНО: Если пользователь запросил фильтрацию, но ни один статус не прошел проверку прав,
                # применяем фильтр по умолчанию (только разрешенные статусы)
                if status_ids:
                    selected_statuses = status_ids
                else:
                    # Все запрошенные статусы недоступны - показываем только разрешенные
                    print(f"⚠️ All requested statuses denied! Applying default filter: {filter_status_ids}")
                    status_ids = filter_status_ids
                    selected_statuses = status_ids
            except ValueError:
                # Если в параметре что-то не то, применяем фильтр по умолчанию
                flash('Получен неверный формат статусов в фильтре.', 'warning')
                status_ids = filter_status_ids
                selected_statuses = status_ids
    
    # Для фильтра используем ТОЛЬКО статусы для просмотра (filter_status_ids)
    # Статусы для изменения (allowed_status_changes) будут использоваться отдельно в выпадающем списке изменения статуса
    statuses = [s for s in Status.query.filter(Status.id.in_(filter_status_ids)).all()]
    
    # Для выпадающего списка изменения статуса получим отдельный список
    change_statuses = [s for s in Status.query.filter(Status.id.in_(allowed_status_changes)).all()]
    
    if name_filter:
        query = query.filter(ReferalData.full_name.ilike(f'%{name_filter}%'))
    
    if phone_filter:
        query = query.filter(ReferalData.phone_number.ilike(f'%{phone_filter}%'))
    
    if contract_filter:
        query = query.filter(ReferalData.contract_number.ilike(f'%{contract_filter}%'))
    
    if contact_id_filter:
        # contact_id - это integer, приводим к строке через cast
        query = query.filter(cast(Referal.contact_id, String).ilike(f'%{contact_id_filter}%'))
        
    if user_filter:
        query = query.filter(User.login.ilike(f'%{user_filter}%'))
    
    if created_at_filter:
        # created_at это timestamp, конвертируем в дату для поиска
        query = query.filter(func.date(Referal.created_at) == created_at_filter)
    
    if total_withdrawal_filter:
        query = query.filter(cast(User.total_withdrawal, String).ilike(f'%{total_withdrawal_filter}%'))
    
    # deals_count убираем - это вычисляемое поле, не колонка БД
    
    # Определяем нужны ли джойны для фильтров и сортировки
    need_user_join = False
    need_referal_data_join = False
    
    # Проверяем фильтры
    if user_filter or total_withdrawal_filter:
        need_user_join = True
    if name_filter or phone_filter or contract_filter:
        need_referal_data_join = True
    
    # Проверяем сортировку
    if sort_fields:
        for sort_field in sort_fields:
            if sort_field['field'] == 'user':
                need_user_join = True
            if sort_field['field'] in ['name', 'phone', 'contract']:
                need_referal_data_join = True
                
    # Делаем джойны если нужно
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
            elif field == 'created_at':
                clause = Referal.created_at.desc() if order == 'desc' else Referal.created_at.asc()
            elif field == 'total_withdrawal':
                clause = User.total_withdrawal.desc() if order == 'desc' else User.total_withdrawal.asc()
            # deals_count убираем - это вычисляемое поле
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
    
    # Если режим просмотра - договоры, получаем список всех договоров
    deals_pagination = None
    deals = []
    if view_mode == 'deals':
        from models import ReferalDeal, MacroDeal
        from sqlalchemy.orm import joinedload
        
        print(f"=== DEALS VIEW MODE ACTIVATED ===")
        print(f"User: {user.login}, Role: {user.role}")
        print(f"Filter status IDs: {filter_status_ids}")
        print(f"Status filter param: {status_filter}")
        print(f"Status IDs list: {status_ids}")
        
        # Базовый запрос для договоров с загрузкой связанных данных
        deals_query = ReferalDeal.query\
            .options(
                joinedload(ReferalDeal.status),
                joinedload(ReferalDeal.deal),
                joinedload(ReferalDeal.referal).joinedload(Referal.referal_data),
                joinedload(ReferalDeal.referal).joinedload(Referal.user)
            )\
            .join(Referal, ReferalDeal.referal_id == Referal.id)\
            .join(MacroDeal, ReferalDeal.deal_id == MacroDeal.id)\
            .join(ReferalData, Referal.id == ReferalData.referal_id)\
            .join(User, Referal.user_id == User.id)
        
        print(f"Base query created")
        
        # Фильтруем только реальные договоры (с номером договора)
        deals_query = deals_query.filter(
            MacroDeal.agreement_number.isnot(None),
            MacroDeal.agreement_number != ''
        )
        
        # Фильтруем: либо есть оплата >= 3млн, либо есть рассчитанная выплата
        deals_query = deals_query.filter(
            or_(
                MacroDeal.total_payments >= 3000000,
                ReferalDeal.withdrawal_amount > 0
            )
        )
        
        # Только реальные договора: "Сделка проведена" и "Сделка в работе"
        valid_statuses = ['Сделка проведена', 'Сделка в работе']
        deals_query = deals_query.filter(
            MacroDeal.deal_status_name.in_(valid_statuses)
        )
        
        # Фильтры для режима договоров
        if status_filter:
            # Применяем фильтр по статусам (уже проверенным на права доступа)
            # Если все статусы были отклонены, status_ids уже содержит filter_status_ids
            deals_query = deals_query.filter(ReferalDeal.status_id.in_(status_ids))
            print(f"Applied status filter with IDs: {status_ids}")
        else:
            # ФИЛЬТР ПО УМОЛЧАНИЮ: Показываем ТОЛЬКО договоры с разрешенными статусами
            # Это предотвращает показ ВСЕХ договоров для call-center и других ролей
            if filter_status_ids:
                deals_query = deals_query.filter(ReferalDeal.status_id.in_(filter_status_ids))
                print(f"Applied default status filter with IDs: {filter_status_ids}")
                # Устанавливаем selected_statuses чтобы UI показывал какие статусы применены
                selected_statuses = filter_status_ids
        
        if name_filter:
            deals_query = deals_query.filter(
                ReferalData.full_name.ilike(f'%{name_filter}%')
            )
            print(f"Applied name filter: {name_filter}")
        
        if contract_filter:
            deals_query = deals_query.filter(MacroDeal.agreement_number.ilike(f'%{contract_filter}%'))
            print(f"Applied contract filter: {contract_filter}")
        
        if user_filter:
            deals_query = deals_query.filter(
                User.login.ilike(f'%{user_filter}%')
            )
            print(f"Applied user filter: {user_filter}")
        
        if amount_filter:
            try:
                min_amount = float(amount_filter)
                deals_query = deals_query.filter(ReferalDeal.withdrawal_amount >= min_amount)
                print(f"Applied amount filter: >= {min_amount}")
            except ValueError:
                print(f"Invalid amount filter value: {amount_filter}")
        
        # Сортировка по умолчанию - по ID договора (новые сверху)
        deals_query = deals_query.order_by(ReferalDeal.id.desc())
        
        print(f"Query SQL: {str(deals_query)}")
        
        # Пагинация для договоров
        try:
            deals_pagination = deals_query.paginate(
                page=page,
                per_page=per_page,
                error_out=False
            )
            deals = deals_pagination.items
            print(f"Query executed successfully. Total deals: {deals_pagination.total}, Current page deals: {len(deals)}")
            for deal in deals[:5]:  # Показываем первые 5 для отладки
                print(f"Deal ID: {deal.id}, Referal: {deal.referal_id}, Status: {deal.status_id}")
        except Exception as e:
            print(f"ERROR executing deals query: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
    
    
    all_statuses_in_db = Status.query.all()
    
    # Синхронизируем данные ВСЕХ пользователей перед рендерингом
    from utils import sync_user_data_from_auth_service
    synced_users = set()  # Чтобы не синхронизировать одного пользователя дважды
    
    print(f"🔄 Starting user data synchronization for admin panel...")
    
    # Синхронизируем пользователей из рефералов
    if referals:
        for referal in referals:
            if referal.user and referal.user.auth_user_id and referal.user.id not in synced_users:
                try:
                    print(f"  📥 Syncing referal user: {referal.user.login} (auth_user_id: {referal.user.auth_user_id})")
                    sync_user_data_from_auth_service(referal.user, force_sync=True, headers=request.headers)
                    synced_users.add(referal.user.id)
                except Exception as e:
                    print(f"  ❌ Failed to sync user {referal.user.login}: {e}")
    
    # Синхронизируем пользователей из договоров
    if deals:
        for deal in deals:
            if deal.referal and deal.referal.user and deal.referal.user.auth_user_id and deal.referal.user.id not in synced_users:
                try:
                    print(f"  📥 Syncing deal user: {deal.referal.user.login} (auth_user_id: {deal.referal.user.auth_user_id})")
                    sync_user_data_from_auth_service(deal.referal.user, force_sync=True, headers=request.headers)
                    synced_users.add(deal.referal.user.id)
                except Exception as e:
                    print(f"  ❌ Failed to sync user {deal.referal.user.login}: {e}")
    
    print(f"✅ Synchronized {len(synced_users)} users")
    
    # Загружаем документы для каждого пользователя из Auth-Service
    print(f"📄 Loading documents for users from Auth-Service...")
    user_documents = {}  # {user_id: {documents: [], download_urls: {}}}
    
    from app_with_auth_connector import get_user_documents_from_auth_service

    # Собираем уникальных пользователей из рефералов и договоров
    users_to_load = set()
    if referals:
        for referal in referals:
            if referal.user and referal.user.auth_user_id:
                users_to_load.add((referal.user.id, referal.user.auth_user_id))
    
    if deals:
        for deal in deals:
            if deal.referal and deal.referal.user and deal.referal.user.auth_user_id:
                users_to_load.add((deal.referal.user.id, deal.referal.user.auth_user_id))
    
    # Загружаем документы для каждого пользователя
    for user_id, auth_user_id in users_to_load:
        try:
            docs = get_user_documents_from_auth_service(auth_user_id)
            
            # Формируем URL для скачивания документов
            auth_service_url = current_app.config.get('AUTH_SERVICE_URL', 'http://gateway-nginx-1')
            download_urls = {
                'pinfl': f"{auth_service_url}/api/users/{auth_user_id}/documents/pinfl/download",
                'passport': f"{auth_service_url}/api/users/{auth_user_id}/documents/passport/download",
                'bank_details': f"{auth_service_url}/api/users/{auth_user_id}/documents/bank_details/download",
                'employment_certificate': f"{auth_service_url}/api/users/{auth_user_id}/documents/employment_certificate/download"
            }
            
            user_documents[user_id] = {
                'documents': docs,
                'download_urls': download_urls,
                'auth_user_id': auth_user_id
            }
            print(f"  📄 Loaded documents for user {user_id} (auth_user_id: {auth_user_id}): {docs}")
        except Exception as e:
            print(f"  ❌ Failed to load documents for user {user_id}: {e}")
            user_documents[user_id] = {
                'documents': {},
                'download_urls': {},
                'auth_user_id': auth_user_id,
                'error': str(e)
            }
    
    print(f"✅ Loaded documents for {len(user_documents)} users")
    
    print(f"📋 Rendering template with selected_statuses: {selected_statuses}")
    print(f"📋 filter_statuses count: {len(statuses)}")
    
    return render_template('admin.html', 
                          current_user=user,
                          referals=referals,
                          pagination=pagination,
                          view_mode=view_mode,
                          deals=deals,
                          deals_pagination=deals_pagination,
                          user_documents=user_documents,  # Документы пользователей из Auth-Service
                          all_statuses_in_db=all_statuses_in_db,  # Добавляем все статусы для фильтра
                          current_filters={
                              'status': status_filter,
                              'name': name_filter,
                              'phone': phone_filter,
                              'contract': contract_filter,
                              'contact_id': contact_id_filter,
                              'user': user_filter,
                              'amount': amount_filter,
                              'created_at': created_at_filter,
                              'total_withdrawal': total_withdrawal_filter,
                              'per_page': per_page
                          },
                          selected_statuses=selected_statuses,
                          statuses=statuses,  # Только статусы для просмотра
                          filter_statuses=statuses,  # Для фильтра - те же статусы для просмотра
                          change_statuses=change_statuses,  # Отдельно - статусы для изменения (выпадающий список)
                          current_sort=sort_param,
                          sort_fields=sort_fields,
                          user_role_type=user_role_type,
                          can_change_status_from_to=can_change_status_from_to,
                          allowed_status_changes=allowed_status_changes)


@admin_bp.route('/admin/deal/<int:deal_id>/update_status', methods=['POST'])
def update_deal_status(deal_id):
    """Обновляет статус договора (только для админов)"""
    try:
        user = get_current_user()
        if not user or not requires_admin_access():
            return jsonify({'success': False, 'message': 'Доступ запрещен'}), 403
        
        # Получаем новый статус из запроса
        data = request.get_json()
        new_status_id = data.get('status_id')
        rejection_reason = data.get('rejection_reason', '').strip()
        
        print(f"DEBUG update_deal_status: deal_id={deal_id}, new_status_id={new_status_id}, type={type(new_status_id)}")
        
        # ВАЖНО: Проверяем is None, т.к. статус 0 это валидное значение!
        if new_status_id is None:
            return jsonify({'success': False, 'message': 'Не указан новый статус'}), 400
        
        # Проверяем обязательность комментария при отказе (status_id = 500)
        if new_status_id == 500 and not rejection_reason:
            return jsonify({
                'success': False,
                'message': 'При отказе необходимо указать причину в поле "Комментарий об отказе"'
            }), 400
        
        # Находим договор
        referal_deal = ReferalDeal.query.get(deal_id)
        if not referal_deal:
            return jsonify({'success': False, 'message': 'Договор не найден'}), 404
        
        # Проверяем права на изменение статуса
        old_status = referal_deal.status_id
        if not can_change_status_from_to(old_status, new_status_id):
            return jsonify({
                'success': False,
                'message': f'Недостаточно прав для изменения статуса с {old_status} на {new_status_id}'
            }), 403
        
        # Обновляем статус
        referal_deal.status_id = new_status_id
        
        # Сохраняем или очищаем причину отказа
        if new_status_id == 500:
            referal_deal.rejection_reason = rejection_reason
        else:
            referal_deal.rejection_reason = None  # Очищаем при смене на другой статус
        
        # Обновляем deal_status для обратной совместимости
        status_mapping = {
            0: 'pending',
            100: 'sent_for_review',
            200: 'approved',
            300: 'paid',
            500: 'rejected'
        }
        referal_deal.deal_status = status_mapping.get(new_status_id, 'pending')
        
        db.session.commit()
        
        # Обновляем объект после коммита чтобы подгрузить связанный статус
        db.session.refresh(referal_deal)
        
        # Отправляем уведомление о смене статуса
        send_admin_deal_status_notification(referal_deal, user, old_status, new_status_id, referal_deal.status_name, rejection_reason)
        
        return jsonify({
            'success': True,
            'message': f'Статус договора обновлен: {referal_deal.status_name}',
            'new_status_id': new_status_id,
            'new_status_name': referal_deal.status_name
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"Error updating deal status: {str(e)}")
        return jsonify({'success': False, 'message': f'Ошибка: {str(e)}'}), 500


@admin_bp.route('/admin/referal/<int:referal_id>/add_deal', methods=['POST'])
def add_deal_to_referal(referal_id):
    """Вручную добавляет договор к рефералу по номеру договора"""
    try:
        print(f"🔍 add_deal_to_referal called for referal_id={referal_id}")
        
        user = get_current_user()
        print(f"🔍 get_current_user returned: {user}")
        
        has_access = requires_admin_access()
        print(f"🔍 requires_admin_access returned: {has_access}")
        
        if not user or not has_access:
            print(f"❌ Access denied: user={user}, has_access={has_access}")
            return jsonify({'success': False, 'message': 'Доступ запрещен'}), 403
        
        # Получаем номер договора из запроса
        data = request.get_json()
        print(f"🔍 Request data: {data}")
        
        if not data:
            return jsonify({'success': False, 'message': 'Не получены данные запроса'}), 400
            
        agreement_number = data.get('agreement_number', '').strip()
        
        if not agreement_number:
            return jsonify({'success': False, 'message': 'Не указан номер договора'}), 400
        
        print(f"🔍 Looking for referal with id={referal_id}")
        # Находим реферала
        referal = Referal.query.get(referal_id)
        if not referal:
            return jsonify({'success': False, 'message': 'Реферал не найден'}), 404
        
        print(f"🔍 Looking for deal with agreement_number={agreement_number}")
        # Находим договор по номеру.
        # Сначала точное совпадение, затем устойчивый поиск (trim + регистронезависимо),
        # т.к. в CRM номер может отличаться пробелами/регистром.
        deal = MacroDeal.query.filter_by(agreement_number=agreement_number).first()
        if not deal:
            deal = MacroDeal.query.filter(
                func.lower(func.trim(MacroDeal.agreement_number)) == agreement_number.lower()
            ).first()
        if not deal:
            # Fallback: договор мог не попасть в локальное зеркало при суточной синхронизации.
            # Пробуем загрузить его напрямую из MacroCRM по номеру и импортировать в MacroDeal.
            print(f"🔍 Deal not in local mirror, trying direct MacroCRM fetch for {agreement_number}")
            from services import fetch_single_deal_from_macro
            deal = fetch_single_deal_from_macro(agreement_number)

        if not deal:
            return jsonify({
                'success': False, 
                'message': f'Договор с номером "{agreement_number}" не найден в базе данных'
            }), 404
        
        print(f"🔍 Found deal: id={deal.id}, agreement_number={deal.agreement_number}, deal_metr={deal.deal_metr}, total_payments={deal.total_payments}")
        
        # Проверяем не добавлен ли уже этот договор
        existing_link = ReferalDeal.query.filter_by(
            referal_id=referal_id,
            deal_id=deal.id
        ).first()
        
        if existing_link:
            return jsonify({
                'success': False,
                'message': f'Договор "{agreement_number}" уже привязан к этому рефералу'
            }), 400
        
        # Рассчитываем сумму выплаты по площади квартиры (та же логика что и при автоматическом добавлении)
        withdrawal_amount = 0
        logger.error(f"🔥🔥🔥 НАЧИНАЕМ РАСЧЁТ ВЫПЛАТЫ для deal_id={deal.id}, deal_metr={deal.deal_metr}, total_payments={deal.total_payments}")
        try:
            # Проверяем есть ли оплата больше брони (3млн)
            if deal.total_payments and deal.total_payments >= 3000000:
                deal_metr = deal.deal_metr or 0
                logger.error(f"🔥 УСЛОВИЕ 1 ВЫПОЛНЕНО: total_payments={deal.total_payments} >= 3000000")
                
                # Логика расчёта по площади из referal_service.py
                if 20.0 <= deal_metr < 40.0:
                    withdrawal_amount = int(os.getenv('REFERAL_WITHDRAWAL_FOR_40M', 300000))
                    logger.error(f"🔥 ВЕТКА 20-40м²: withdrawal_amount={withdrawal_amount}")
                elif 40.0 <= deal_metr < 60.0:
                    withdrawal_amount = int(os.getenv('REFERAL_WITHDRAWAL_FOR_60M', 400000))
                    logger.error(f"🔥 ВЕТКА 40-60м²: withdrawal_amount={withdrawal_amount}")
                elif 60.0 <= deal_metr < 80.0:
                    withdrawal_amount = int(os.getenv('REFERAL_WITHDRAWAL_FOR_80M', 500000))
                    logger.error(f"🔥 ВЕТКА 60-80м²: withdrawal_amount={withdrawal_amount}")
                elif deal_metr >= 80.0:
                    withdrawal_amount = int(os.getenv('REFERAL_WITHDRAWAL_FOR_81M', 600000))
                    logger.error(f"🔥 ВЕТКА 80+м²: withdrawal_amount={withdrawal_amount}")
                elif deal_metr > 0:
                    # Для квартир меньше 20м² - минимальная выплата
                    withdrawal_amount = int(os.getenv('REFERAL_WITHDRAWAL_FOR_40M', 300000))
                    logger.error(f"🔥 ВЕТКА <20м²: withdrawal_amount={withdrawal_amount}")
                else:
                    logger.error(f"🔥 НИ ОДНА ВЕТКА НЕ СРАБОТАЛА! deal_metr={deal_metr}")
                
                logger.error(f"💰 Calculated withdrawal_amount: {withdrawal_amount} for deal {deal.agreement_number} (deal_metr={deal_metr})")
            else:
                logger.error(f"⚠️ Deal {deal.agreement_number} has insufficient payments: {deal.total_payments}")
        except Exception as calc_error:
            import traceback
            logger.error(f"❌ Error calculating withdrawal: {calc_error}")
            logger.error(f"❌ Traceback: {traceback.format_exc()}")
        
        logger.error(f"🔥🔥🔥 ИТОГО withdrawal_amount={withdrawal_amount}")
        sys.stdout.flush()
        
        # Обновляем contact_id (macro_id) у реферала из договора
        if deal.contacts_buy_id and not referal.contact_id:
            referal.contact_id = deal.contacts_buy_id
            print(f"📋 Updated referal.contact_id = {deal.contacts_buy_id} from deal")
        elif deal.contacts_buy_id and referal.contact_id != deal.contacts_buy_id:
            # Если contact_id уже есть но отличается - логируем предупреждение
            print(f"⚠️ Referal already has contact_id={referal.contact_id}, deal has contacts_buy_id={deal.contacts_buy_id}")
        
        # Создаем связь
        referal_deal = ReferalDeal(
            referal_id=referal_id,
            deal_id=deal.id,
            status_id=0,  # Начальный статус "Ждет проверки"
            is_within_window=True,  # Ручное добавление админом - считаем в окне
            withdrawal_amount=withdrawal_amount,
            payment_processed=False,
            deal_status='pending',
            days_from_referal_creation=None,  # Не рассчитываем для ручного добавления
            manually_added=True  # Флаг ручного добавления - всегда показывать в списке
        )
        
        db.session.add(referal_deal)
        db.session.commit()
        
        print(f"✅ Admin manually added deal {agreement_number} to referal {referal_id} | User: {user.login} | withdrawal_amount: {withdrawal_amount} | contact_id: {referal.contact_id}")
        
        # Отправляем уведомление менеджеру КЦ о новом договоре
        try:
            from notification_client import get_notification_client
            
            notification_client = get_notification_client()
            from utils import staff_recipient

            call_center = staff_recipient('CALL_CENTER_MANAGER')
            main_admin = staff_recipient('MAIN_ADMIN')
            
            # Получаем информацию о рефе��але
            referal_name = referal.referal_data.full_name if referal.referal_data else 'Неизвестно'
            referal_phone = referal.referal_data.phone_number if referal.referal_data else 'Неизвестно'
            admin_name = get_user_full_name_from_auth(user)
            
            subject = f'Новый договор №{agreement_number} добавлен к рефералу'
            body = f"""Администратор {admin_name} добавил новый договор к рефералу.

Детали договора:
- Номер договора: {agreement_number}
- Проект: {deal.project_name or 'Не указан'}
- Сумма платежей: {deal.total_payments:,.0f} сум

Информация о реферале:
- ФИО: {referal_name}
- Телефон: {referal_phone}

Необходимо связаться с рефералом для назначения встречи."""

            # Отправляем менеджеру КЦ
            if call_center:
                notification_client.send_email(
                    subject=subject,
                    body=body,
                    **call_center
                )
                print(f"✅ Notification sent to call center manager: {call_center}")
            
            # Копия главному админу
            if main_admin and main_admin != call_center:
                notification_client.send_email(
                    subject=f"[Копия] {subject}",
                    body=body,
                    **main_admin
                )
                print(f"✅ Copy sent to main admin: {main_admin}")
                
        except Exception as email_error:
            print(f"⚠️ Failed to send notification for deal add: {str(email_error)}")
            # Не прерываем операцию если письмо не отправилось
        
        return jsonify({
            'success': True,
            'message': f'Договор "{agreement_number}" успешно привязан к рефералу',
            'deal_id': deal.id,
            'referal_deal_id': referal_deal.id,
            'withdrawal_amount': withdrawal_amount,
            'debug_info': {
                'deal_metr': deal.deal_metr,
                'total_payments': deal.total_payments,
                'calculated_withdrawal': withdrawal_amount
            },
            'deal_info': {
                'agreement_number': deal.agreement_number,
                'contacts_buy_id': deal.contacts_buy_id,
                'total_payments': deal.total_payments,
                'project_name': deal.project_name
            }
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error adding deal to referal: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Ошибка: {str(e)}'}), 500


@admin_bp.route('/update_withdrawal_stage/<int:referal_id>', methods=['POST'])
def update_withdrawal_stage(referal_id):
    """Обновление статуса реферала."""
    current_user = get_current_user()
    if not current_user or not requires_admin_access():
        flash('Доступ запрещен', 'error')
        return redirect(request.referrer or '/')

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
         utils.send_email_to_staff(
            'MAIN_ADMIN',
            'Реферал поступил на проверку отделом аналитики',
            f'Реферал от {get_user_full_name_from_auth(user)} поступил на проверку отделу аналитики:\nФИО: {referal.referal_data.full_name}\nMacro ID: {referal.contact_id}\n'
        )
    
    elif withdrawal_stage == 20:
         utils.send_email_to_staff(
            'MAIN_ADMIN',
            'Реферал прошёл проверку колл-центром',
            f'Реферал от {get_user_full_name_from_auth(user)} прошёл проверку колл-центром:\nФИО: {referal.referal_data.full_name}\nMacro ID: {referal.contact_id}\n'
        )
        
    elif withdrawal_stage == 10:
         utils.send_email_to_staff(
            'CALL_CENTER_MANAGER',
            'Запрос на проверку реферала',
            f'Пожалуйста созвонитесь с рефералом от {get_user_full_name_from_auth(user)}: ФИО: {referal.referal_data.full_name} Телефон: {referal.referal_data.phone_number} для проверки его данных после чего обязательно измените статус реферала в системе.\n'
        )
        
    elif withdrawal_stage == 200:
        payment_email = os.getenv('PAYMENT_MANAGER_EMAIL')

        utils.send_email_to_staff(
            'PAYMENT_MANAGER',
            'Запрос на выплату рефереру',
            f'{get_user_full_name_from_auth(user)} запросил вывод средств за реферала:\nФИО: {referal.referal_data.full_name}\nMacro ID: {referal.contact_id}\n пожалуйста проверьте меню реферальной программы и подтвердите/отклоните выплату.'
        )



    elif withdrawal_stage == 300:
        utils.send_email_to_staff(
            'MAIN_ADMIN',
            'Реферал был оплачен рефереру',
            f'Реферал от {get_user_full_name_from_auth(user)} был помечен как оплаченый:\nФИО: {referal.referal_data.full_name}\nMacro ID: {referal.contact_id}\n'
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
        rejecter_name = get_user_full_name_from_auth(current_user)
        utils.send_email_to_staff(
            'MAIN_ADMIN',
            'Реферал не прошёл проверку',
            f"""
            Реферал от {get_user_full_name_from_auth(user)} не прошёл проверку {referal.status_name}\n
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

# Глобальное состояние синхронизации (для отслеживания прогресса)
import threading
from datetime import datetime as dt

_sync_status = {
    'is_running': False,
    'started_at': None,
    'started_by': None,
    'completed_at': None,
    'last_error': None,
    'last_result': None
}
_sync_lock = threading.Lock()


def _run_sync_in_background(app, username):
    """Выполняет синхронизацию в фоновом потоке"""
    global _sync_status
    
    with app.app_context():
        try:
            print(f"🔄 Background sync STARTED by {username}")
            sync_result = fetch_data_from_mysql()
            
            # fetch_data_from_mysql НЕ бросает исключение при сбое задач,
            # а возвращает статус в словаре — проверяем его явно,
            # иначе падение обеих задач отчитывалось как 'success'.
            result_status = (sync_result or {}).get('status', 'unknown')
            if result_status == 'success':
                with _sync_lock:
                    _sync_status['completed_at'] = dt.now()
                    _sync_status['is_running'] = False
                    _sync_status['last_result'] = 'success'
                    _sync_status['last_error'] = None
                print(f"✅ Background sync COMPLETED by {username}")
            else:
                error_summary = f"contacts={((sync_result or {}).get('contacts') or {}).get('status')}, deals={((sync_result or {}).get('deals') or {}).get('status')}"
                with _sync_lock:
                    _sync_status['completed_at'] = dt.now()
                    _sync_status['is_running'] = False
                    _sync_status['last_result'] = result_status
                    _sync_status['last_error'] = error_summary
                print(f"⚠️ Background sync FINISHED WITH ERRORS by {username} | {error_summary}")
            
        except Exception as e:
            with _sync_lock:
                _sync_status['completed_at'] = dt.now()
                _sync_status['is_running'] = False
                _sync_status['last_result'] = 'error'
                _sync_status['last_error'] = str(e)
            
            print(f"❌ Background sync FAILED by {username} | Error: {str(e)}")
            
            # Алерт на почту о падении ручной синхронизации
            try:
                import traceback
                from services.data_sync_service import send_sync_failure_alert
                send_sync_failure_alert(
                    f'manual sync (started by {username})',
                    f"{str(e)}\n\n{traceback.format_exc()}"
                )
            except Exception as alert_error:
                print(f"⚠️ Failed to send sync failure alert: {alert_error}")


@admin_bp.route('/force_update', methods=['GET'])
def force_update():
    """Принудительное обновление всех рефералов. ТОЛЬКО для администраторов!
    Запускает синхронизацию в фоновом режиме и сразу возвращает ответ.
    """
    global _sync_status
    
    user = get_current_user()
    
    # Проверяем что пользователь существует
    if not user:
        print("⛔ Force update access DENIED - No user found")
        flash('Доступ запрещен - пользователь не найден', 'error')
        return redirect(request.referrer or '/')
    
    # Проверяем права: только админ системы или админ сервиса
    user_role = get_user_role_type()
    has_admin_permission = has_permission('referal.admin.force_update')
    is_system_admin = user_role == 'admin'
    
    if not (is_system_admin or has_admin_permission):
        username = request.headers.get('X-User-Name', 'Unknown')
        print(f"⛔ Force update access DENIED | User: {username} | Role: {user_role} | Has permission: {has_admin_permission}")
        flash('Доступ запрещен - недостаточно прав для принудительной синхронизации', 'error')
        return redirect(url_for('admin.admin_panel'))
    
    username = request.headers.get('X-User-Name', user.login if hasattr(user, 'login') else 'Unknown')
    
    # Проверяем, не запущена ли уже синхронизация
    with _sync_lock:
        if _sync_status['is_running']:
            started_at = _sync_status['started_at']
            started_by = _sync_status['started_by']
            flash(f'Синхронизация уже выполняется (запущена {started_by} в {started_at.strftime("%H:%M:%S")}). Дождитесь завершения.', 'warning')
            return redirect(url_for('admin.admin_panel'))
        
        # Устанавливаем статус "выполняется"
        _sync_status['is_running'] = True
        _sync_status['started_at'] = dt.now()
        _sync_status['started_by'] = username
        _sync_status['completed_at'] = None
        _sync_status['last_error'] = None
        _sync_status['last_result'] = None
    
    # Запускаем синхронизацию в фоновом потоке
    print(f"🔄 Force update QUEUED by admin | User: {username} | Role: {user_role}")
    
    app = current_app._get_current_object()
    sync_thread = threading.Thread(
        target=_run_sync_in_background,
        args=(app, username),
        daemon=True
    )
    sync_thread.start()
    
    flash('Синхронизация запущена в фоновом режиме. Проверьте статус через несколько минут.', 'info')
    return redirect(url_for('admin.admin_panel'))


@admin_bp.route('/sync_status', methods=['GET'])
def sync_status():
    """Возвращает текущий статус синхронизации (JSON)"""
    if not requires_admin_access():
        return jsonify({'error': 'Доступ запрещен'}), 403
    
    global _sync_status
    
    with _sync_lock:
        status = {
            'is_running': _sync_status['is_running'],
            'started_at': _sync_status['started_at'].isoformat() if _sync_status['started_at'] else None,
            'started_by': _sync_status['started_by'],
            'completed_at': _sync_status['completed_at'].isoformat() if _sync_status['completed_at'] else None,
            'last_result': _sync_status['last_result'],
            'last_error': _sync_status['last_error']
        }
    
    return jsonify(status)


@admin_bp.route('/admin/export_database.xlsx', methods=['GET'])
def export_database_excel():
    """Полный экспорт всех таблиц БД referal в один .xlsx файл (по листу на таблицу).

    Защищён отдельным разрешением `referal.admin.export_database_excel`,
    которое НЕ выдаётся автоматически вместе с обычным admin-доступом.
    """
    user = get_current_user()
    if not user:
        abort(403)

    if not has_permission('referal.admin.export_database_excel'):
        username = getattr(user, 'username', None) or request.headers.get('X-User-Name', 'unknown')
        print(f"⛔ DB export DENIED for user '{username}' - missing 'referal.admin.export_database_excel'")
        abort(403)

    import io
    import datetime as _dt
    from decimal import Decimal
    from openpyxl import Workbook

    EXCEL_CELL_LIMIT = 32767  # хард-лимит Excel на размер строки в ячейке

    def _normalize(value):
        """Приводит значение к типу, пригодному для openpyxl-ячейки."""
        if value is None:
            return None
        if isinstance(value, (str, int, float, bool, Decimal)):
            if isinstance(value, str) and len(value) > EXCEL_CELL_LIMIT:
                return value[:EXCEL_CELL_LIMIT - 3] + '...'
            return value
        if isinstance(value, (_dt.datetime, _dt.date, _dt.time)):
            # openpyxl поддерживает date/datetime/time напрямую,
            # но aware-datetime нужно сделать naive (Excel timezones не хранит).
            if isinstance(value, _dt.datetime) and value.tzinfo is not None:
                return value.replace(tzinfo=None)
            return value
        if isinstance(value, (bytes, bytearray, memoryview)):
            return f'<binary {len(bytes(value))} bytes>'
        # dict / list / прочее — сериализуем строкой
        text = str(value)
        if len(text) > EXCEL_CELL_LIMIT:
            text = text[:EXCEL_CELL_LIMIT - 3] + '...'
        return text

    try:
        wb = Workbook(write_only=True)
        sorted_tables = list(db.metadata.sorted_tables)
        used_sheet_names = set()

        for table in sorted_tables:
            # Имя листа: max 31 символ, без запрещённых символов, уникальное.
            raw_name = table.name
            sheet_name = ''.join(ch for ch in raw_name if ch not in '[]:*?/\\')[:31] or 'sheet'
            base = sheet_name
            counter = 1
            while sheet_name.lower() in used_sheet_names:
                suffix = f"_{counter}"
                sheet_name = (base[:31 - len(suffix)] + suffix)
                counter += 1
            used_sheet_names.add(sheet_name.lower())

            ws = wb.create_sheet(title=sheet_name)
            columns = [c.name for c in table.columns]
            ws.append(columns)

            result = db.session.execute(table.select())
            for row in result:
                ws.append([_normalize(v) for v in row])

        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)

        timestamp = _dt.datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'referal_db_export_{timestamp}.xlsx'

        username = getattr(user, 'username', None) or request.headers.get('X-User-Name', 'unknown')
        print(f"📤 DB export OK | user='{username}' | tables={len(sorted_tables)} | file={filename}")

        return send_file(
            buf,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename,
            max_age=0,
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"❌ DB export FAILED: {e}")
        return jsonify({'success': False, 'message': f'Ошибка экспорта: {e}'}), 500


@admin_bp.route('/admin/manual_backup', methods=['POST'])
def manual_db_backup():
    """Создаёт ручной бэкап БД через pg_dump в /app/backups/manual/.

    Файлы в этой папке НИКОГДА не очищаются автоматически (cron-сервис
    postgres-backup трогает только daily/weekly/monthly).

    Защищён отдельным разрешением `referal.admin.manual_db_backup`.
    """
    user = get_current_user()
    if not user:
        abort(403)

    if not has_permission('referal.admin.manual_db_backup'):
        username = getattr(user, 'username', None) or request.headers.get('X-User-Name', 'unknown')
        print(f"⛔ Manual backup DENIED for user '{username}' - missing 'referal.admin.manual_db_backup'")
        abort(403)

    import subprocess
    import datetime as _dt
    import re as _re

    pg_host = os.getenv('POSTGRES_HOST', 'postgres')
    pg_port = os.getenv('POSTGRES_PORT', '5432')
    pg_db = os.getenv('POSTGRES_DB', 'referal_db')
    pg_user = os.getenv('POSTGRES_USER', 'referal_user')
    pg_pass = os.getenv('POSTGRES_PASSWORD', '')

    backups_dir = '/app/backups/manual'
    os.makedirs(backups_dir, exist_ok=True)

    timestamp = _dt.datetime.now().strftime('%Y%m%d_%H%M%S')

    username = getattr(user, 'username', None) or request.headers.get('X-User-Name', 'unknown')
    safe_username = _re.sub(r'[^A-Za-z0-9_.-]+', '_', str(username))[:40] or 'unknown'

    filename = f'referal_db_manual_{timestamp}_by_{safe_username}.sql.gz'
    out_path = os.path.join(backups_dir, filename)

    env = os.environ.copy()
    env['PGPASSWORD'] = pg_pass

    cmd = [
        'pg_dump',
        '-h', pg_host,
        '-p', str(pg_port),
        '-U', pg_user,
        '-d', pg_db,
        '--format=plain',
        '--no-owner',
        '--no-privileges',
        '--blobs',
    ]

    try:
        print(f"📦 Manual backup STARTED by '{username}' -> {out_path}")
        with open(out_path, 'wb') as raw_out:
            # pg_dump | gzip
            gzip_proc = subprocess.Popen(
                ['gzip', '-6'],
                stdin=subprocess.PIPE,
                stdout=raw_out,
                stderr=subprocess.PIPE,
            )
            dump_proc = subprocess.Popen(
                cmd,
                stdout=gzip_proc.stdin,
                stderr=subprocess.PIPE,
                env=env,
            )
            # close our handle so gzip sees EOF when pg_dump exits
            gzip_proc.stdin.close()
            dump_stderr = dump_proc.stderr.read().decode('utf-8', errors='replace')
            dump_rc = dump_proc.wait()
            gzip_stderr = gzip_proc.stderr.read().decode('utf-8', errors='replace')
            gzip_rc = gzip_proc.wait()

        if dump_rc != 0 or gzip_rc != 0:
            # удаляем неполный файл
            try:
                os.remove(out_path)
            except OSError:
                pass
            err_msg = f"pg_dump rc={dump_rc} ({dump_stderr.strip()}); gzip rc={gzip_rc} ({gzip_stderr.strip()})"
            print(f"❌ Manual backup FAILED: {err_msg}")
            return jsonify({'success': False, 'message': err_msg}), 500

        size_bytes = os.path.getsize(out_path)
        print(f"✅ Manual backup OK | user='{username}' | file={filename} | size={size_bytes} bytes")
        return jsonify({
            'success': True,
            'filename': filename,
            'path': out_path,
            'size_bytes': size_bytes,
        })

    except FileNotFoundError as e:
        # pg_dump не установлен в контейнере
        print(f"❌ Manual backup FAILED - pg_dump not found: {e}")
        return jsonify({
            'success': False,
            'message': 'pg_dump не найден в контейнере. Пересоберите образ referal с обновлённым Dockerfile.'
        }), 500
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"❌ Manual backup FAILED: {e}")
        return jsonify({'success': False, 'message': f'Ошибка бэкапа: {e}'}), 500


