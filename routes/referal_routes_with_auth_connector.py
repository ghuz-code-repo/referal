"""
Example referal_routes.py updated with auth-connector
Shows how to migrate from simple role checks to permission-based authorization
"""

from flask import Blueprint, render_template, request, redirect, url_for, jsonify, g, current_app, flash
from sqlalchemy import or_, not_
from datetime import datetime
import services.referal_service as referal_service
from models import User, Referal, ReferalData, MacroContact, Status, ReferalDeal, MacroDeal, db
import re
import os
import random
import requests
from services import notification_service
from notification_client import get_notification_client
from routes.auth_routes import get_current_user
import utils

# AUTH-CONNECTOR INTEGRATION
try:
    from auth_connector import require_permission, require_any_permission, get_current_user as get_auth_user
    AUTH_CONNECTOR_AVAILABLE = True
    print("✅ referal_routes_with_auth_connector: auth_connector imported successfully")
except ImportError as e:
    print(f"⚠️  referal_routes_with_auth_connector: Failed to import auth_connector: {e}")
    AUTH_CONNECTOR_AVAILABLE = False
    # Fallback decorators
    def require_permission(permission, allow_admin=True):
        def decorator(f):
            return f
        return decorator
    
    def require_any_permission(permissions, allow_admin=True):
        def decorator(f):
            return f
        return decorator

referal_bp = Blueprint('referal', __name__)

def get_user():
    """Get current user - uses auth-connector if available, falls back to legacy"""
    if AUTH_CONNECTOR_AVAILABLE:
        auth_user = get_auth_user()
        print(f"🔍 get_user() | AUTH_CONNECTOR_AVAILABLE: True | get_auth_user() returned: {type(auth_user).__name__ if auth_user else 'None'}")
        return auth_user
    else:
        legacy_user = get_current_user()
        print(f"🔍 get_user() | AUTH_CONNECTOR_AVAILABLE: False | get_current_user() returned: {type(legacy_user).__name__ if legacy_user else 'None'}")
        return legacy_user


# COMMENTED OUT - now handled by @app.route('/') in app_with_auth_connector.py
# @referal_bp.route('/', methods=['GET'])
# @require_permission('referal.profile.view')  # NEW: Permission-based authorization
# def index():
#     """Main referral page with smart redirection based on permissions"""
#     print("DEBUG INDEX: function called")
#     user = get_user()
#     
#     if not user:
#         print("DEBUG INDEX: No user found, redirecting to referal profile")
#         return redirect(url_for('referal.profile'))
#     
#     print(f"DEBUG INDEX: User found: {user.login if hasattr(user, 'login') else 'unknown'}")
#     
#     # Check permissions and redirect accordingly
#     if AUTH_CONNECTOR_AVAILABLE:
#         print("DEBUG INDEX: AUTH_CONNECTOR_AVAILABLE = True")
#         
#         # Admin panel access for admin roles
#         has_admin_panel = user.has_permission('referal.admin.panel')
#         has_manage_users = user.has_any_permission(['referal.admin.manage_users', 'referal.users.manage'])
#         print(f"DEBUG INDEX: has_admin_panel={has_admin_panel}, has_manage_users={has_manage_users}")
#         
#         if has_admin_panel or has_manage_users:
#             print("DEBUG INDEX: Redirecting to admin panel")
#             return redirect(url_for('admin.admin_panel'))
#         
#         # For users without referral list permissions, redirect to a page they can access
#         has_referral_list = user.has_permission('referal.referrals.list')
#         print(f"DEBUG INDEX: has_referral_list={has_referral_list}")
#         
#         if not has_referral_list:
#             print("DEBUG INDEX: User has no referral list permission")
#             # Check what they can access and redirect accordingly
#             if user.has_permission('referal.payments.view'):
#                 print("DEBUG INDEX: Redirecting to payments")
#                 return redirect(url_for('referal.payments'))
#             else:
#                 # Redirect to a basic profile page or show limited access message
#                 print("DEBUG INDEX: Redirecting to limited profile")
#                 return redirect(url_for('referal.limited_profile'))
#     else:
#         print("DEBUG INDEX: AUTH_CONNECTOR_AVAILABLE = False, using legacy")
#         # Legacy fallback
#         if hasattr(user, 'role') and user.role in ['admin', 'manager', 'call-center']:
#             print("DEBUG INDEX: Legacy redirect to admin panel")
#             return redirect(url_for('admin.admin_panel'))
#     
#     print("DEBUG INDEX: Default path - updating deal info and redirecting to profile")
#     # Update deal info for regular users with referral access
#     if hasattr(user, 'id'):
#         referal_service.update_deal_info(user)
#     
#     return redirect(url_for('referal.profile'))

@referal_bp.route('/profile', methods=['GET'])
def profile():
    """User profile page - requires referral access"""
    user = get_user()
    
    print(f"🔍 Profile route | User: {user} | Type: {type(user).__name__ if user else 'None'}")
    if user:
        print(f"   has_id: {hasattr(user, 'id')} | has_user_id: {hasattr(user, 'user_id')} | username: {user.username if hasattr(user, 'username') else 'N/A'}")
    
    if not user:
        return render_template('access_denied.html',
                             service_name='Реферальная программа',
                             required_permissions=['referal.referrals.list', 'referal.referrals.create']), 403
    
    # Check if user has any referral access
    has_referral_access = False
    if AUTH_CONNECTOR_AVAILABLE:
        # Получаем все права пользователя для проверки
        user_perms = request.headers.get('X-User-Service-Permissions', '').split(',')
        
        # Администратор с правами на админ-панель также имеет доступ к профилю
        has_admin_access = user.has_any_permission(['referal.admin.panel', 'referal.admin.manage_users'])
        
        # Проверяем разрешения на просмотр профиля или рефералов
        required_perms = [
            'referal.profile.view',      # Основное разрешение на просмотр профиля
            'referal.referrals.list',    # Список рефералов
            'referal.referrals.view',    # Просмотр рефералов
            'referal.referrals.create',  # Создание рефералов
            'referal.referrals.add'      # Альтернативное название для создания
        ]
        has_referral_access = user.has_any_permission(required_perms) or has_admin_access
        
        print(f"🔐 Profile access check | User: {user.username} | Admin: {has_admin_access} | Referral: {user.has_any_permission(required_perms)} | Perms: {user_perms}")
        
        if not has_referral_access:
            print(f"⚠️ Profile access DENIED")
    else:
        # Legacy fallback - if no auth-connector, allow access for backward compatibility
        has_referral_access = True
    
    if not has_referral_access:
        return render_template('access_denied.html',
                             service_name='Реферальная программа',
                             required_permissions=['referal.profile.view', 'referal.referrals.list', 'referal.referrals.view']), 403
    
    # Legacy user handling for backward compatibility
    # Keep the original user object (UserContext from auth-connector) for permission checks
    # but get db_user for profile data and sync
    db_user = None
    if not hasattr(user, 'id') and hasattr(user, 'user_id'):
        # This is auth-connector user (UserContext), need to get from DB for profile data
        db_user = User.query.filter_by(login=user.username).first()
        print(f"👤 Looking up database user for {user.username}: {'Found' if db_user else 'Not found'}")
        if db_user:
            print(f"   DB user has auth_user_id: {db_user.auth_user_id if hasattr(db_user, 'auth_user_id') else 'N/A'}")
            # Синхронизируем ВСЕ данные из auth-service (телефон, email, паспорт, ПИНФЛ, банк)
            from utils import sync_user_data_from_auth_service
        # ПРИНУДИТЕЛЬНО синхронизируем данные пользователя из auth-service при каждом запросе
        from utils import sync_user_profile_always
        sync_user_profile_always(db_user)
    elif user and hasattr(user, 'id'):
        # This is legacy user from database
        db_user = user
        # ПРИНУДИТЕЛЬНО синхронизируем данные пользователя из auth-service при каждом запросе
        from utils import sync_user_profile_always
        sync_user_profile_always(db_user)
    
    # Check available permissions
    can_view_referrals = False
    can_add_referrals = False
    
    if AUTH_CONNECTOR_AVAILABLE and user:
        # Check SPECIFIC referral permissions (not admin.panel!)
        can_view_referrals = user.has_any_permission([
            'referal.referrals.list',
            'referal.referrals.view'
        ])
        can_add_referrals = user.has_any_permission([
            'referal.referrals.create',
            'referal.referrals.add'
        ])
    
    # Get user balance info if available
    current_balance = 0
    pending_withdrawal = 0
    total_withdrawal = 0
    
    if db_user:
        current_balance = getattr(db_user, 'current_balance', 0)
        pending_withdrawal = getattr(db_user, 'pending_withdrawal', 0)
        total_withdrawal = getattr(db_user, 'total_withdrawal', 0)
    
    # Show profile page with user information and available actions
    return render_template('profile.html',
                         user=db_user if db_user else user,
                         can_view_referrals=can_view_referrals,
                         can_add_referrals=can_add_referrals,
                         current_balance=current_balance,
                         pending_withdrawal=pending_withdrawal,
                         total_withdrawal=total_withdrawal)

@referal_bp.route('/limited_profile', methods=['GET'])
@require_permission('referal.profile.view')
def limited_profile():
    """Limited profile page for users without referral access"""
    user = get_user()
    
    if not user:
        return render_template('limited_profile.html', 
                             error="Пользователь не найден. Обратитесь к администратору.")
    
    # Legacy user handling for backward compatibility
    if not hasattr(user, 'id') and hasattr(user, 'user_id'):
        # This is auth-connector user, need to get from DB
        db_user = User.query.filter_by(login=user.username).first()
        if db_user:
            user = db_user
    
    # Синхронизируем данные пользователя с auth-service
    if user and hasattr(user, 'id'):
        try:
            from utils import sync_user_data_from_auth_service
            sync_user_data_from_auth_service(user, force_sync=True, headers=request.headers)
        except Exception as e:
            print(f"Warning: Failed to sync user data from auth-service: {e}")
    
    # Check available permissions for this user
    available_actions = []
    
    if AUTH_CONNECTOR_AVAILABLE and user:
        # Добавить реферала
        if user.has_permission('referal.referrals.create'):
            available_actions.append({
                'title': 'Добавить реферала',
                'url': url_for('referal.add_referal_form'),
                'icon': 'fas fa-user-plus',
                'description': 'Добавить нового реферала в систему'
            })
        
        # Просмотр своих рефералов
        if user.has_permission('referal.referrals.list'):
            available_actions.append({
                'title': 'Мои рефералы',
                'url': url_for('referal.my_referrals'),
                'icon': 'fas fa-users',
                'description': 'Просмотр списка моих рефералов'
            })
        
        # Административная панель
        if user.has_permission('referal.admin.panel'):
            available_actions.append({
                'title': 'Панель администратора',
                'url': url_for('admin.admin_panel'),
                'icon': 'fas fa-cog',
                'description': 'Управление системой и пользователями'
            })
        
        # Платежи
        if user.has_permission('referal.payments.view'):
            available_actions.append({
                'title': 'Платежи и выплаты',
                'url': url_for('referal.payments'),
                'icon': 'fas fa-credit-card',
                'description': 'Просмотр информации о платежах и балансе'
            })
    
    return render_template('limited_profile.html', 
                         user=user,
                         available_actions=available_actions)

@referal_bp.route('/add_referal', methods=['POST'])
@require_permission('referal.referrals.create')
def add_referal():
    """Add new referral with permission check"""
    user_context = get_user()
    
    if not user_context:
        return jsonify({'success': False, 'message': 'Пользователь не авторизован'})
    
    # Get local user from database
    local_user = User.query.filter_by(auth_user_id=user_context.user_id).first()
    
    if not local_user:
        return jsonify({
            'success': False, 
            'message': 'Пользователь не найден в системе. Обратитесь к администратору.'
        })
    
    try:
        # Get form data
        full_name = request.form.get('full_name', '').strip()
        phone = request.form.get('phone', '').strip()
        
        # Validate required fields
        if not full_name:
            return jsonify({
                'success': False, 
                'message': 'Имя реферала обязательно для заполнения'
            })
        
        if not phone:
            return jsonify({
                'success': False,
                'message': 'Телефон реферала обязателен для заполнения'
            })
        
        # Validate and format phone using standard format_phone_number
        from utils import format_phone_number
        formatted_phone = format_phone_number(phone)
        
        if not formatted_phone:
            return jsonify({
                'success': False,
                'message': 'Пожалуйста, введите корректный номер телефона'
            })
        
        # Check if referral with this phone already exists
        existing_referal = Referal.query.join(ReferalData).filter(
            ReferalData.phone_number == formatted_phone
        ).first()
        if existing_referal:
            return jsonify({
                'success': False,
                'message': f'Реферал с номером {formatted_phone} уже добавлен'
            })
        
        # Check if referral with this name already exists
        existing_referal = Referal.query.join(ReferalData).filter(
            ReferalData.full_name == full_name
        ).first()
        if existing_referal:
            return jsonify({
                'success': False,
                'message': f'Реферал с именем {full_name} уже добавлен'
            })
        
        # CRITICAL: Check contact history in CRM for the last 45 days
        # This prevents registering clients who already have deals/applications
        check_result = referal_service.check_contact_history_before_adding(
            phone_number=formatted_phone,
            full_name=full_name,
            days_threshold=45
        )
        
        if not check_result['can_add']:
            # Contact has recent activity in CRM - cannot register as referral
            reason = check_result.get('reason', 'Контакт имеет недавнюю активность в CRM')
            contact = check_result.get('contact')
            
            # Build detailed error message
            if contact:
                error_msg = f'Данный человек не может являться рефералом. {reason}'
                if contact.last_deal_date:
                    days_ago = (datetime.now() - datetime.combine(contact.last_deal_date, datetime.min.time())).days
                    error_msg = f'Данный клиент уже имеет сделку в нашей системе ({days_ago} дней назад). Регистрировать как реферала можно только клиентов без заявок и сделок за последние 45 дней.'
            else:
                error_msg = f'Данный человек не может являться рефералом. {reason}'
            
            return jsonify({
                'success': False,
                'message': error_msg
            })
        
        # Get initial status (should be the first status or status with is_start=True)
        initial_status = Status.query.filter_by(is_start=True).first()
        if not initial_status:
            # Fallback to first status if no start status is set
            initial_status = Status.query.order_by(Status.id).first()
        
        # Create new referral with initial status
        new_referal = Referal(
            user_id=local_user.id,
            status_id=initial_status.id if initial_status else 1,
            status_name=initial_status.name if initial_status else 'Не начата'
        )
        db.session.add(new_referal)
        db.session.commit()
        db.session.flush()  # Get referral ID
        
        # Create referral data
        referal_data = ReferalData(
            referal_id=new_referal.id,
            full_name=full_name,
            phone_number=formatted_phone
        )
        
        # Optional passport fields
        passport_number = request.form.get('passport_number', '').strip()
        passport_date = request.form.get('passport_date', '').strip()
        passport_giver = request.form.get('passport_giver', '').strip()
        
        if passport_number:
            referal_data.passport_number = passport_number
        if passport_date:
            from datetime import datetime
            try:
                referal_data.passport_date = datetime.strptime(passport_date, '%Y-%m-%d')
            except ValueError:
                pass  # Ignore invalid date format
        if passport_giver:
            referal_data.passport_giver = passport_giver
        
        db.session.add(referal_data)
        db.session.commit()
        
        # Always send notification to call-center when new referral is created
        send_referral_notification(local_user, full_name, formatted_phone)
        
        return jsonify({
            'success': True,
            'message': 'Реферал успешно добавлен!',
            'referal_id': new_referal.id
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"Error adding referral: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': 'Ошибка при добавлении реферала. Попробуйте еще раз.'
        })

@referal_bp.route('/my_referrals')
@require_permission('referal.referrals.view')
def my_referrals():
    """View user's referrals and deals"""
    # Get user context from auth-connector
    user_context = get_user()
    
    if not user_context:
        return redirect(url_for('referal.profile'))
    
    # Get local user from database
    local_user = User.query.filter_by(auth_user_id=user_context.user_id).first()
    
    if not local_user:
        flash('Пользователь не найден в системе. Обратитесь к администратору.', 'error')
        return redirect(url_for('referal.profile'))
    
    # Check permissions
    can_add_referrals = user_context.has_any_permission(['referal.referrals.create', 'referal.referrals.add'])
    can_view_referrals = user_context.has_any_permission(['referal.referrals.list', 'referal.referrals.view'])
    
    # Получаем режим просмотра: 'referals' (по умолчанию) или 'deals'
    view_mode = request.args.get('view_mode', 'referals')
    
    # Получаем параметры фильтрации
    name_filter = request.args.get('name', '').strip()
    contract_filter = request.args.get('contract', '').strip()
    status_filter = request.args.get('status', '').strip()
    amount_filter = request.args.get('amount', '').strip()
    
    # Get user's referrals or deals based on view_mode
    referrals = []
    total_user_referals = 0
    deals = []
    
    if view_mode == 'referals':
        # Режим рефералов - показываем список рефералов
        referrals = Referal.query.filter_by(user_id=local_user.id).all()
        total_user_referals = len(referrals)
    elif view_mode == 'deals':
        # Режим договоров - показываем все договоры пользователя
        from sqlalchemy.orm import joinedload
        
        # Получаем все договоры пользователя через его рефералов
        deals_query = ReferalDeal.query\
            .options(
                joinedload(ReferalDeal.status),
                joinedload(ReferalDeal.deal),
                joinedload(ReferalDeal.referal).joinedload(Referal.referal_data),
                joinedload(ReferalDeal.referal).joinedload(Referal.user)
            )\
            .join(Referal, ReferalDeal.referal_id == Referal.id)\
            .filter(Referal.user_id == local_user.id)\
            .join(MacroDeal, ReferalDeal.deal_id == MacroDeal.id)
        
        # Фильтруем только реальные договоры (с номером договора)
        # Логика соответствует get_deals_summary(): показываем если есть оплата ИЛИ выплата И статус валидный
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
        
        # Применяем фильтры для режима договоров
        if status_filter:
            try:
                # Обрабатываем множественный выбор статусов (через запятую)
                status_ids = [int(s.strip()) for s in status_filter.split(',') if s.strip().isdigit()]
                if status_ids:
                    deals_query = deals_query.filter(ReferalDeal.status_id.in_(status_ids))
            except ValueError:
                pass
        
        if name_filter:
            deals_query = deals_query.join(ReferalData, Referal.id == ReferalData.referal_id).filter(
                ReferalData.full_name.ilike(f'%{name_filter}%')
            )
        
        if contract_filter:
            deals_query = deals_query.filter(MacroDeal.agreement_number.ilike(f'%{contract_filter}%'))
        
        if amount_filter:
            try:
                min_amount = float(amount_filter)
                deals_query = deals_query.filter(ReferalDeal.withdrawal_amount >= min_amount)
            except ValueError:
                pass
        
        # Сортировка по ID (новые сверху)
        deals_query = deals_query.order_by(ReferalDeal.id.desc())
        
        # Получаем все договоры
        deals = deals_query.all()
    
    # Получаем все статусы для фильтра
    all_statuses_in_db = Status.query.all()
    
    return render_template('my_referrals.html', 
                         user=local_user, 
                         referals=referrals,  # Changed from referrals to referals
                         total_user_referals=total_user_referals,
                         can_add_referrals=can_add_referrals,
                         can_view_referrals=can_view_referrals,
                         view_mode=view_mode,
                         deals=deals,
                         all_statuses_in_db=all_statuses_in_db,
                         sort_fields=[],
                         current_filters={},
                         current_sort=None)

@referal_bp.route('/request_withdrawal/<int:referal_id>', methods=['POST'])
@require_permission('referal.payments.request')
def request_withdrawal(referal_id):
    """Request withdrawal for a specific referral"""
    from services import withdrawal_service
    
    user = get_user()
    if not user:
        return redirect(url_for('referal.my_referrals'))
    
    try:
        withdrawal_service.request_withdrawal(referal_id, user=user)
        return redirect(url_for('referal.my_referrals'))
    except Exception as e:
        print(f"Error requesting withdrawal: {str(e)}")
        import traceback
        traceback.print_exc()
        return redirect(url_for('referal.my_referrals'))

@referal_bp.route('/update_referal_documents/<int:referal_id>', methods=['POST'])
def update_referal_documents(referal_id):
    """Update referral documents and data - доступно владельцам и админам"""
    from datetime import datetime
    
    user_context = get_user()
    if not user_context:
        return jsonify({
            'success': False,
            'message': 'Пользователь не авторизован'
        }), 401
    
    # Get local user from database
    local_user = User.query.filter_by(auth_user_id=user_context.user_id).first()
    
    if not local_user:
        return jsonify({
            'success': False,
            'message': 'Пользователь не найден в системе'
        }), 404
    
    # Check if referal belongs to user (admins can edit any)
    if user_context.is_admin:
        referal = Referal.query.get(referal_id)
    else:
        referal = Referal.query.filter_by(id=referal_id, user_id=local_user.id).first()
    
    if not referal:
        return jsonify({
            'success': False,
            'message': 'Реферал не найден'
        }), 404
    
    try:
        # If referal has no data, create it
        if not referal.referal_data:
            referal.referal_data = ReferalData(referal_id=referal_id)
            db.session.add(referal.referal_data)
            db.session.flush()
        
        # Get form data
        full_name = request.form.get('full_name', '').strip()
        phone_number = request.form.get('phone_number', '').strip()
        passport_number = request.form.get('passport_number', '').strip()
        passport_giver = request.form.get('passport_giver', '').strip()
        passport_adress = request.form.get('passport_adress', '').strip()
        mail_adress = request.form.get('mail_adress', '').strip()
        passport_date_str = request.form.get('passport_date', '').strip()
        
        # Форматируем номер телефона через utils функцию
        formatted_phone = None
        if phone_number:
            # Если есть запятые, берем только первый номер
            first_phone = phone_number.split(',')[0].strip()
            formatted_phone = utils.format_phone_number(first_phone)
        
        # Update referal data fields
        referal.referal_data.full_name = full_name if full_name else None
        referal.referal_data.phone_number = formatted_phone if formatted_phone else phone_number if phone_number else None
        referal.referal_data.passport_number = passport_number if passport_number else None
        referal.referal_data.passport_giver = passport_giver if passport_giver else None
        referal.referal_data.passport_adress = passport_adress if passport_adress else None
        referal.referal_data.mail_adress = mail_adress if mail_adress else None
        
        # Handle passport_date
        if passport_date_str:
            try:
                passport_date = datetime.strptime(passport_date_str, '%Y-%m-%d')
                referal.referal_data.passport_date = passport_date
            except ValueError:
                try:
                    passport_date = datetime.strptime(passport_date_str, '%d.%m.%Y')
                    referal.referal_data.passport_date = passport_date
                except ValueError:
                    try:
                        passport_date = datetime.strptime(passport_date_str, '%d/%m/%Y')
                        referal.referal_data.passport_date = passport_date
                    except ValueError:
                        return jsonify({
                            'success': False,
                            'message': 'Неверный формат даты выдачи паспорта. Используйте формат ДД.ММ.ГГГГ'
                        }), 400
        else:
            referal.referal_data.passport_date = None
        
        # Валидация ФИО (опциональная - только если заполнено)
        if full_name:
            # Проверяем минимум 2 слова и отсутствие двойных пробелов
            words = full_name.strip().split()
            if len(words) < 2 or '  ' in full_name:
                return jsonify({
                    'success': False,
                    'message': 'Неверно введено ФИО. Минимум 2 слова без двойных пробелов'
                }), 400
        
        # Валидация телефона
        if phone_number and not formatted_phone:
            return jsonify({
                'success': False,
                'message': 'Неверный формат телефона. Введите корректный номер телефона'
            }), 400
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Данные реферала успешно обновлены'
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"Error updating referal documents: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return jsonify({
            'success': False,
            'message': f'Ошибка при обновлении данных: {str(e)}'
        }), 400

@referal_bp.route('/payments')
@require_permission('referal.payments.view')
def payments():
    """View payment information"""
    user = get_user()
    
    if not user:
        return redirect(url_for('referal.profile'))
    
    return render_template('payments.html', user=user)

@referal_bp.route('/request_payment', methods=['POST'])
@require_permission('referal.payments.request')
def request_payment():
    """Request payment withdrawal"""
    user = get_user()
    
    if not user:
        return jsonify({'success': False, 'message': 'Пользователь не авторизован'})
    
    amount = request.form.get('amount')
    
    try:
        amount = float(amount)
        if amount <= 0:
            return jsonify({'success': False, 'message': 'Сумма должна быть положительной'})
        
        if amount > user.current_balance:
            return jsonify({'success': False, 'message': 'Недостаточно средств на балансе'})
        
        # Update balances
        user.current_balance -= amount
        user.pending_withdrawal += amount
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Заявка на выплату {amount} сум отправлена на рассмотрение'
        })
        
    except ValueError:
        return jsonify({'success': False, 'message': 'Некорректная сумма'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': 'Ошибка при обработке заявки'})

# ADMIN/MANAGER ROUTES WITH ENHANCED PERMISSIONS

@referal_bp.route('/admin/reports')
@require_any_permission(['referal.reports.view', 'referal.admin.view_reports'])
def admin_reports():
    """View reports - requires specific permissions"""
    user = get_user()
    
    # Additional permission check for sensitive data
    if AUTH_CONNECTOR_AVAILABLE and not user.has_any_permission([
        'referal.reports.view', 
        'referal.admin.view_reports',
        'referal.stats.view'
    ]):
        return render_template('error.html', 
                             error="У вас нет прав для просмотра отчетов")
    
    # Get report data based on permissions
    report_data = {}
    
    if user.has_permission('referal.stats.view'):
        # Full statistics
        report_data['full_stats'] = True
        report_data['total_users'] = User.query.count()
        report_data['total_referrals'] = Referal.query.count()
    
    if user.has_permission('referal.reports.view'):
        # Detailed reports
        report_data['detailed_reports'] = True
        report_data['recent_referrals'] = Referal.query.limit(10).all()
    
    return render_template('admin_reports.html', 
                         user=user, 
                         report_data=report_data)

@referal_bp.route('/admin/export')
@require_permission('referal.admin.export_data')
def admin_export():
    """Export data - admin only"""
    user = get_user()
    
    try:
        # Create export based on permissions
        export_data = []
        
        if user.has_permission('referal.admin.export_data'):
            # Full export
            referrals = Referal.query.all()
            for ref in referrals:
                export_data.append({
                    'id': ref.id,
                    'user_id': ref.user_id,
                    'full_name': ref.full_name,
                    'phone': ref.phone,
                    'created_at': ref.created_at.isoformat() if ref.created_at else None
                })
        
        return jsonify({
            'success': True,
            'data': export_data,
            'total_records': len(export_data)
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Ошибка экспорта: {str(e)}'})

def send_referral_notification(user, full_name, phone):
    """Send notification about new referral to users with appropriate permissions"""
    try:
        from notification_utils import get_notification_recipients_for_new_referral
        
        # Получаем всех получателей уведомлений о новых рефералах
        recipients = get_notification_recipients_for_new_referral()
        
        if not recipients:
            print("⚠️ No users with notification permissions found, skipping notification")
            return
        
        notification_client = get_notification_client()
        user_full_name = user.user_data.full_name if hasattr(user, "user_data") and user.user_data else user.full_name
        
        # Отправляем уведомление каждому получателю
        for recipient in recipients:
            recipient_email = recipient.get('email')
            recipient_name = recipient.get('full_name', recipient.get('username', 'Сотрудник'))
            
            if not recipient_email:
                print(f"⚠️ Recipient has no email: {recipient}")
                continue
            
            try:
                notification_client.send_email(
                    recipient=recipient_email,
                    subject='Новый реферал для обзвона',
                    body=f'Пользователь {user_full_name} добавил нового реферала:\n\n'
                         f'Имя: {full_name}\n'
                         f'Телефон: {phone}\n\n'
                         f'Пожалуйста, свяжитесь с рефералом для дальнейшего взаимодействия.'
                )
                print(f"📧 Email notification sent to: {recipient_name} ({recipient_email})")
            except Exception as e:
                print(f"❌ Failed to send email to {recipient_email}: {str(e)}")
        
        print(f"✅ Notification process completed. Sent to {len(recipients)} recipients")
        
    except Exception as e:
        print(f"❌ Failed to send referral notification: {str(e)}")
        import traceback
        traceback.print_exc()


def get_user_email_from_auth_service(auth_user_id):
    """Получить актуальный email пользователя из auth-service"""
    try:
        auth_service_url = os.getenv('AUTH_SERVICE_URL', 'http://auth-service:80')
        profile_url = f"{auth_service_url}/api/users/{auth_user_id}/profile"
        
        response = requests.get(profile_url, timeout=5)
        
        if response.status_code == 200:
            profile_data = response.json()
            email = profile_data.get('email')
            if email:
                print(f"✅ Got email from auth-service for user {auth_user_id}: {email}")
                return email
            else:
                print(f"⚠️ No email in auth-service profile for user {auth_user_id}")
        else:
            print(f"⚠️ Failed to get profile from auth-service: {response.status_code}")
    except Exception as e:
        print(f"❌ Error getting email from auth-service: {str(e)}")
    
    return None


def send_deal_status_notification(referal_deal, user, new_status_id, new_status_name):
    """Send notification about deal status change to users with appropriate permissions"""
    try:
        from notification_utils import get_notification_recipients_for_status, get_status_display_name
        
        # Получаем получателей уведомлений для этого статуса
        recipients = get_notification_recipients_for_status(new_status_id)
        
        if not recipients:
            print(f"⚠️ No users with notification permissions found for status {new_status_id}, skipping notification")
            return
        
        # Получаем данные о договоре
        agreement_number = referal_deal.deal.agreement_number if referal_deal.deal else 'Неизвестно'
        referal_name = referal_deal.referal.referal_data.full_name if referal_deal.referal and referal_deal.referal.referal_data else 'Неизвестно'
        referal_phone = referal_deal.referal.referal_data.phone_number if referal_deal.referal and referal_deal.referal.referal_data else 'Неизвестно'
        withdrawal_amount = referal_deal.withdrawal_amount or 0
        user_name = user.user_data.full_name if hasattr(user, "user_data") and user.user_data else user.full_name if hasattr(user, "full_name") else "Неизвестный пользователь"
        status_display = get_status_display_name(new_status_id)
        
        notification_client = get_notification_client()
        
        # Формируем общее тело письма
        subject = f'Договор №{agreement_number} - статус: {status_display}'
        body = f"""Статус договора изменён пользователем {user_name}.

Детали договора:
- Номер договора: {agreement_number}
- Реферал: {referal_name} ({referal_phone})
- Сумма вывода: {withdrawal_amount:,.0f} сум
- Новый статус: {status_display}"""
        
        # Добавляем причину отказа если есть (для статуса 500)
        if new_status_id == 500 and referal_deal.rejection_reason:
            body += f"\n- Причина отказа: {referal_deal.rejection_reason}"
        
        body += "\n\nТребуется ваша проверка."
        
        # Отправляем уведомление каждому получателю
        for recipient in recipients:
            recipient_email = recipient.get('email')
            recipient_name = recipient.get('full_name', recipient.get('username', 'Сотрудник'))
            
            if not recipient_email:
                print(f"⚠️ Recipient has no email: {recipient}")
                continue
            
            try:
                notification_client.send_email(
                    recipient=recipient_email,
                    subject=subject,
                    body=body
                )
                print(f"📧 Status change notification sent to: {recipient_name} ({recipient_email}) for status {status_display}")
            except Exception as e:
                print(f"❌ Failed to send email to {recipient_email}: {str(e)}")
        
        print(f"✅ Status change notification process completed. Sent to {len(recipients)} recipients for status {new_status_id}")
        
    except Exception as e:
        print(f"❌ Failed to send deal status notification: {str(e)}")
        import traceback
        traceback.print_exc()


@referal_bp.route('/deal/<int:deal_id>/send_for_review', methods=['POST'])
def send_deal_for_review(deal_id):
    """Отправляет договор на проверку (меняет статус с 0 на 100)"""
    try:
        user = get_user()
        if not user:
            print(f"🚫 Send for review: User not found")
            return jsonify({'success': False, 'message': 'Пользователь не найден'}), 401
        
        print(f"👤 Send for review: User {user.user_id}, Deal ID: {deal_id}")
        
        # Находим договор
        referal_deal = ReferalDeal.query.get(deal_id)
        if not referal_deal:
            print(f"🚫 Send for review: Deal {deal_id} not found")
            return jsonify({'success': False, 'message': 'Договор не найден'}), 404
        
        print(f"📄 Deal {deal_id}: Referal ID: {referal_deal.referal_id}, Referal user_id: {referal_deal.referal.user_id}, Current status: {referal_deal.status_id}")
        
        # Находим пользователя в локальной таблице user по auth_user_id
        local_user = User.query.filter_by(auth_user_id=user.user_id).first()
        if not local_user:
            print(f"🚫 Send for review: Local user not found for auth_user_id {user.user_id}")
            return jsonify({'success': False, 'message': 'Пользователь не найден в системе'}), 404
        
        print(f"👤 Local user found: ID={local_user.id}, Login={local_user.login}")
        
        # Проверяем права - пользователь должен быть владельцем реферала ИЛИ админом
        is_admin = user.has_any_permission(['referal.admin.view', 'referal.admin.full_access', 'referal.admin.change_status'])
        print(f"🔐 Is admin: {is_admin}")
        
        if referal_deal.referal.user_id != local_user.id and not is_admin:
            print(f"🚫 Send for review: Access denied. Referal user_id={referal_deal.referal.user_id}, Local user id={local_user.id}, is_admin={is_admin}")
            return jsonify({'success': False, 'message': 'Нет прав для этой операции'}), 403
        
        # Проверяем текущий статус - можно отправить только со статусом 0
        if referal_deal.status_id != 0:
            print(f"🚫 Send for review: Wrong status. Current: {referal_deal.status_id} ({referal_deal.status_name})")
            return jsonify({
                'success': False, 
                'message': f'Договор уже имеет статус "{referal_deal.status_name}". Отправить можно только договоры со статусом "Ждет проверки".'
            }), 400
        
        # Обновляем статус на 1 (Проверка отделом аналитики)
        print(f"✅ Updating deal {deal_id} status: 0 -> 1")
        referal_deal.status_id = 1
        referal_deal.deal_status = 'sent_for_review'
        
        db.session.commit()
        print(f"✅ Deal {deal_id} successfully sent for review with status_id=1")
        
        # Обновляем объект после коммита чтобы подгрузить связанный статус
        db.session.refresh(referal_deal)
        
        # Получаем название статуса
        status_name = referal_deal.status_name if referal_deal.status else 'Проверка отделом аналитики'
        print(f"📊 New status name: {status_name}")
        
        # Отправляем уведомление в отдел аналитики
        send_deal_status_notification(referal_deal, user, 1, status_name)
        
        return jsonify({
            'success': True,
            'message': f'Договор {referal_deal.deal.agreement_number if referal_deal.deal else deal_id} отправлен на проверку',
            'new_status_id': 1,
            'new_status_name': status_name
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error sending deal for review: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Ошибка: {str(e)}'}), 500


@referal_bp.route('/get_referal_deals/<int:referal_id>', methods=['GET'])
def get_referal_deals(referal_id):
    """API endpoint для получения списка договоров реферала"""
    print(f"🔍 get_referal_deals called with referal_id={referal_id}")
    try:
        user_context = get_user()
        
        if not user_context:
            print(f"❌ User not authorized")
            return jsonify({'success': False, 'message': 'Пользователь не авторизован'}), 401
        
        # Получаем локального пользователя из БД
        from models import User
        local_user = User.query.filter_by(auth_user_id=user_context.user_id).first()
        
        print(f"🔍 Auth user_id: {user_context.user_id}")
        print(f"🔍 Local user: {local_user.id if local_user else 'NOT FOUND'}")
        print(f"🔍 Is admin: {user_context.is_admin}")
        
        if not local_user:
            print(f"❌ Local user not found for auth_user_id={user_context.user_id}")
            return jsonify({'success': False, 'message': 'Пользователь не найден в системе'}), 404
        
        print(f"🔍 Looking for referal with id={referal_id}")
        referal = Referal.query.get(referal_id)
        
        if not referal:
            print(f"❌ Referal not found: id={referal_id}")
            return jsonify({'success': False, 'message': 'Реферал не найден'}), 404
            
        print(f"✅ Referal found: {referal.id}, user_id={referal.user_id}")
        
        # Проверяем права доступа: либо это владелец реферала, либо админ
        is_owner = referal.user_id == local_user.id
        is_admin = user_context.is_admin
        
        print(f"🔍 Is admin: {is_admin}, Is owner: {is_owner}")
        
        if not is_admin and not is_owner:
            print(f"❌ Access denied: not admin and not owner")
            return jsonify({'success': False, 'message': 'Доступ запрещен'}), 403
        
        print(f"🔍 Access granted! Getting deals summary...")
        deals_summary = referal.get_deals_summary()
        print(f"✅ Deals summary retrieved: {len(deals_summary)} deals")
        
        # Отладка: выводим первый договор если есть
        if deals_summary:
            print(f"🔍 First deal data: {deals_summary[0]}")
        
        # Получаем данные реферала
        referal_data = referal.referal_data
        
        result = {
            'success': True,
            'referal_id': referal.id,
            'referal_name': referal_data.full_name if referal_data else 'Неизвестно',
            'referal_phone': referal_data.phone_number if referal_data else '',
            'referal_contact_id': referal.contact_id if referal.contact_id else '',
            'passport_number': referal_data.passport_number if referal_data else '',
            'passport_giver': referal_data.passport_giver if referal_data else '',
            'passport_date': referal_data.passport_date.strftime('%Y-%m-%d') if referal_data and referal_data.passport_date else '',
            'total_deals': referal.get_deals_count(),
            'pending_deals': referal.get_pending_deals_count(),
            'approved_deals': referal.get_approved_deals_count(),
            'total_withdrawal': referal.get_total_withdrawal_amount(),
            'deals': deals_summary
        }
        print(f"✅ Returning success response")
        return jsonify(result)
    except Exception as e:
        print(f"❌ ERROR in get_referal_deals: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Ошибка: {str(e)}'}), 500


@referal_bp.route('/get_rejection_reason/<int:deal_id>', methods=['GET'])
def get_rejection_reason(deal_id):
    """Получить причину отказа для договора"""
    try:
        user = get_user()
        if not user:
            return jsonify({'success': False, 'message': 'Пользователь не найден'}), 401
        
        # Находим договор
        referal_deal = ReferalDeal.query.get(deal_id)
        if not referal_deal:
            return jsonify({'success': False, 'message': 'Договор не найден'}), 404
        
        # Проверяем права - пользователь должен быть владельцем реферала
        if referal_deal.referal.user_id != user.user_id:
            return jsonify({'success': False, 'message': 'Нет прав для просмотра'}), 403
        
        # Проверяем, что есть причина отказа
        rejection_reason = referal_deal.rejection_reason or 'Причина отказа не указана'
        
        return jsonify({
            'success': True,
            'reason': rejection_reason,
            'status_name': referal_deal.status_name,
            'status_id': referal_deal.status_id
        })
        
    except Exception as e:
        print(f"Error getting rejection reason: {str(e)}")
        return jsonify({'success': False, 'message': f'Ошибка: {str(e)}'}), 500


# ========================================
# DEAL MANAGEMENT ROUTES
# ========================================

@referal_bp.route('/add_referal_deal/<int:referal_id>', methods=['POST'])
@require_permission('referal.referrals.edit')
def add_referal_deal(referal_id):
    """Добавление нового договора к рефералу вручную"""
    try:
        user_context = get_user()
        if not user_context:
            return jsonify({'success': False, 'message': 'Пользователь не авторизован'}), 401
        
        referal = Referal.query.get_or_404(referal_id)
        
        # Проверяем доступ - пользователь должен быть владельцем реферала или админом
        local_user = User.query.filter_by(auth_user_id=user_context.user_id).first()
        is_admin = user_context.has_any_permission(['referal.admin.view', 'referal.admin.full_access'])
        
        if not local_user:
            return jsonify({'success': False, 'message': 'Пользователь не найден в системе'}), 403
        
        if referal.user_id != local_user.id and not is_admin:
            return jsonify({'success': False, 'message': 'Нет доступа к этому рефералу'}), 403
        
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'Не переданы данные'}), 400
            
        contact_id = data.get('contact_id')
        deal_id = data.get('deal_id')
        deal_status = data.get('deal_status', 'pending')
        
        deal = None
        
        # Ищем договор по deal_id или contact_id
        if deal_id:
            deal = MacroDeal.query.get(deal_id)
        elif contact_id:
            deal = MacroDeal.query.filter_by(contacts_buy_id=contact_id).first()
        
        if not deal:
            return jsonify({'success': False, 'message': 'Договор не найден. Укажите корректный deal_id или contact_id'}), 404
        
        # Проверяем, не существует ли уже такая связь
        existing = ReferalDeal.query.filter_by(referal_id=referal_id, deal_id=deal.id).first()
        if existing:
            return jsonify({'success': False, 'message': f'Договор {deal.agreement_number} уже связан с этим рефералом'}), 400
        
        # Рассчитываем дни от создания реферала до договора
        days_from_creation = None
        if referal.created_at and deal.agreement_date:
            deal_date = deal.agreement_date
            if hasattr(deal_date, 'date'):
                deal_date = deal_date
            else:
                deal_date = datetime.combine(deal_date, datetime.min.time())
            
            referal_date = referal.created_at
            if isinstance(deal_date, datetime):
                days_from_creation = (deal_date - referal_date).days
        
        # Определяем, попадает ли в 45-дневное окно
        is_within_window = True
        if days_from_creation is not None:
            is_within_window = days_from_creation <= referal.days_window
        
        # Создаем новую связь
        referal_deal = ReferalDeal(
            referal_id=referal_id,
            deal_id=deal.id,
            deal_status=deal_status,
            days_from_referal_creation=days_from_creation,
            is_within_window=is_within_window,
            linked_at=datetime.now()
        )
        
        db.session.add(referal_deal)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Договор {deal.agreement_number} успешно добавлен к рефералу',
            'referal_deal_id': referal_deal.id,
            'deal': {
                'id': deal.id,
                'agreement_number': deal.agreement_number,
                'project_name': deal.project_name,
                'deal_status_name': deal.deal_status_name
            }
        })
    except Exception as e:
        db.session.rollback()
        print(f"Error in add_referal_deal: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Ошибка: {str(e)}'}), 500


@referal_bp.route('/update_deal_status/<int:referal_deal_id>', methods=['POST'])
@require_permission('referal.referrals.edit')
def update_deal_status(referal_deal_id):
    """Обновление статуса связи реферал-договор"""
    try:
        user_context = get_user()
        if not user_context:
            return jsonify({'success': False, 'message': 'Пользователь не авторизован'}), 401
        
        referal_deal = ReferalDeal.query.get_or_404(referal_deal_id)
        referal = referal_deal.referal
        
        # Проверяем доступ
        local_user = User.query.filter_by(auth_user_id=user_context.user_id).first()
        is_admin = user_context.has_any_permission(['referal.admin.view', 'referal.admin.full_access'])
        
        if not local_user:
            return jsonify({'success': False, 'message': 'Пользователь не найден в системе'}), 403
        
        if referal.user_id != local_user.id and not is_admin:
            return jsonify({'success': False, 'message': 'Нет доступа'}), 403
        
        data = request.get_json()
        new_status = data.get('deal_status')
        
        if not new_status:
            return jsonify({'success': False, 'message': 'Статус обязателен'}), 400
        
        valid_statuses = ['pending', 'sent_for_review', 'approved', 'rejected', 'paid']
        if new_status not in valid_statuses:
            return jsonify({'success': False, 'message': f'Неверный статус. Допустимые: {", ".join(valid_statuses)}'}), 400
        
        referal_deal.deal_status = new_status
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Статус успешно обновлен'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Ошибка: {str(e)}'}), 500


@referal_bp.route('/remove_referal_deal/<int:referal_deal_id>', methods=['DELETE'])
@require_permission('referal.referrals.edit')
def remove_referal_deal(referal_deal_id):
    """Удаление связи между рефералом и договором"""
    try:
        user_context = get_user()
        if not user_context:
            return jsonify({'success': False, 'message': 'Пользователь не авторизован'}), 401
        
        referal_deal = ReferalDeal.query.get_or_404(referal_deal_id)
        referal = referal_deal.referal
        
        # Проверяем доступ
        local_user = User.query.filter_by(auth_user_id=user_context.user_id).first()
        is_admin = user_context.has_any_permission(['referal.admin.view', 'referal.admin.full_access'])
        
        if not local_user:
            return jsonify({'success': False, 'message': 'Пользователь не найден в системе'}), 403
        
        if referal.user_id != local_user.id and not is_admin:
            return jsonify({'success': False, 'message': 'Нет доступа'}), 403
        
        deal_number = referal_deal.deal.agreement_number if referal_deal.deal else 'N/A'
        
        db.session.delete(referal_deal)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Договор {deal_number} отвязан от реферала'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Ошибка: {str(e)}'}), 500


# PERMISSION DEMONSTRATION ROUTE
@referal_bp.route('/debug/permissions')
def debug_permissions():
    """Debug route to show current user permissions"""
    if not current_app.debug:
        return "Debug mode only", 404
        
    user = get_user()
    
    if not user:
        return "No user found"
    
    debug_info = {
        'user_id': getattr(user, 'user_id', 'N/A'),
        'username': getattr(user, 'username', 'N/A'), 
        'full_name': getattr(user, 'full_name', 'N/A'),
        'is_admin': getattr(user, 'is_admin', False),
        'auth_connector_available': AUTH_CONNECTOR_AVAILABLE,
    }
    
    if AUTH_CONNECTOR_AVAILABLE and user:
        debug_info['permissions'] = user.permissions
        debug_info['roles'] = user.roles
        debug_info['has_view_permission'] = user.has_permission('referal.profile.view')
        debug_info['has_admin_permission'] = user.has_permission('referal.admin.export_data')
    
    return f"<pre>{debug_info}</pre>"