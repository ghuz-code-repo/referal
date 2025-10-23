"""
Example referal_routes.py updated with auth-connector
Shows how to migrate from simple role checks to permission-based authorization
"""

from flask import Blueprint, render_template, request, redirect, url_for, jsonify, g, current_app, flash
from sqlalchemy import or_, not_
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
            # Синхронизация не требуется - данные пользователя уже в headers от gateway
    elif user and hasattr(user, 'id'):
        # This is legacy user from database
        db_user = user
        # Синхронизация не требуется - данные пользователя уже в headers от gateway
    
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
            sync_user_data_from_auth_service(user, force_sync=True)
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
    user = get_user()
    
    if not user:
        return jsonify({'success': False, 'message': 'Пользователь не авторизован'})
    
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
        
        # Validate and format phone
        phone_digits = re.sub(r'\D', '', phone)
        if len(phone_digits) < 9:
            return jsonify({
                'success': False,
                'message': 'Пожалуйста, введите корректный номер телефона'
            })
        
        formatted_phone = f"+998{phone_digits[-9:]}"
        
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
        
        # Check if this person is already a MacroContact
        macro_contact = MacroContact.query.filter_by(phone_number=formatted_phone).first()
        if macro_contact:
            return jsonify({
                'success': False,
                'message': 'Данный человек не может являться рефералом'
            })
        
        # Get initial status (should be the first status or status with is_start=True)
        initial_status = Status.query.filter_by(is_start=True).first()
        if not initial_status:
            # Fallback to first status if no start status is set
            initial_status = Status.query.order_by(Status.id).first()
        
        # Create new referral with initial status
        new_referal = Referal(
            user_id=user.id,
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
        
        # Send notification if user has permission
        if AUTH_CONNECTOR_AVAILABLE and user.has_permission('referal.notifications.send'):
            send_referral_notification(user, full_name, formatted_phone)
        elif not AUTH_CONNECTOR_AVAILABLE:
            # Legacy notification sending
            send_referral_notification(user, full_name, formatted_phone)
        
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
    # Get auth-connector user first for permissions
    auth_user = None
    if AUTH_CONNECTOR_AVAILABLE:
        try:
            from auth_connector import get_current_user as get_auth_user
            auth_user = get_auth_user()
        except:
            pass
    
    # Get DB user for referrals
    user = get_user()
    
    if not user:
        return redirect(url_for('referal.profile'))
    
    # Legacy user handling for backward compatibility
    if not hasattr(user, 'id') and hasattr(user, 'user_id'):
        # This is auth-connector user, need to get from DB
        db_user = User.query.filter_by(login=user.username).first()
        if db_user:
            user = db_user
    
    # Check permissions using auth_user if available  
    can_add_referrals = True  # Default to True if user passed @require_permission check
    can_view_referrals = True  # Default to True if user passed @require_permission check
    
    if auth_user:
        can_view_referrals = auth_user.has_any_permission(['referal.referrals.list', 'referal.referrals.view'])
        can_add_referrals = auth_user.has_any_permission(['referal.referrals.create', 'referal.referrals.add'])
    
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
    
    if hasattr(user, 'id'):
        if view_mode == 'referals':
            # Режим рефералов - показываем список рефералов
            referrals = Referal.query.filter_by(user_id=user.id).all()
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
                .filter(Referal.user_id == user.id)\
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
                         user=user, 
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
@require_permission('referal.referrals.edit')
def update_referal_documents(referal_id):
    """Update referral documents and data"""
    from datetime import datetime
    
    user = get_user()
    if not user:
        flash('Пользователь не авторизован', 'error')
        return redirect(url_for('referal.my_referrals'))
    
    # Check if referal belongs to user
    referal = Referal.query.filter_by(id=referal_id, user_id=user.id).first()
    if not referal:
        flash('Реферал не найден', 'error')
        return redirect(url_for('referal.my_referrals'))
    
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
                        flash('Неверный формат даты выдачи паспорта. Используйте формат ДД.ММ.ГГГГ', 'error')
                        return redirect(url_for('referal.my_referrals'))
        else:
            referal.referal_data.passport_date = None
        
        # Валидация ФИО
        if full_name and (not re.match(r'^[A-Za-z`\']+(?: [A-Za-z`\']+){2,}$', full_name) or '  ' in full_name):
            flash('Неверно введено ФИО. Используйте латиницу и минимум 3 слова', 'error')
            return redirect(url_for('referal.my_referrals'))
        
        # Валидация телефона
        if phone_number and not formatted_phone:
            flash('Неверный формат телефона. Введите корректный номер телефона', 'error')
            return redirect(url_for('referal.my_referrals'))
        
        db.session.commit()
        flash('Данные реферала успешно обновлены', 'success')
        
    except Exception as e:
        db.session.rollback()
        print(f"Error updating referal documents: {str(e)}")
        import traceback
        traceback.print_exc()
        flash(f'Ошибка при обновлении данных: {e}', 'error')
    
    return redirect(url_for('referal.my_referrals'))

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
    """Send notification about new referral"""
    try:
        managers = ["Mamatov A'zam", "Saidov Bekzod", "Karimov Jasur", 
                   "Toshmatov Aziz", "Nazarov Sherzod"]
        manager = managers[random.randint(0, len(managers) - 1)]
        
        # Check if notification service is configured
        call_center_email = os.getenv('CALL_CENTER_MANAGER_EMAIL')
        if not call_center_email:
            print("Call center email not configured")
            return
        
        # Send notification
        notification_client = get_notification_client()
        notification_client.send_email(
            recipient=call_center_email,
            subject='Новый реферал добавлен',
            body=f'Пользователь {user.user_data.full_name if hasattr(user, "user_data") else user.full_name} добавил нового реферала: {full_name} ({phone}). Создайте встречу реферала с менеджером: {manager} для дальнейшего взаимодействия с клиентом.'
        )
        
    except Exception as e:
        print(f"Failed to send referral notification: {str(e)}")


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
    """Send notification about deal status change to appropriate recipient based on new status"""
    try:
        # Определяем получателя на основе нового статуса
        # Status mapping:
        # 0 -> Ждёт проверки
        # 1 -> Проверка отделом аналитики (MAIN_ADMIN_EMAIL)
        # 10 -> Проверка колл центром (CALL_CENTER_MANAGER_EMAIL)
        # 20 -> Проверка Коммерческим Директором (MAIN_ADMIN_EMAIL)
        # 200 -> Акцептовано к оплате (PAYMENT_MANAGER_EMAIL)
        # 300 -> Оплачено (PAYMENT_MANAGER_EMAIL)
        # 500 -> Отказано (уведомить пользователя)
        
        recipient_email = None
        subject_prefix = ""
        
        if new_status_id == 1:
            # Проверка отделом аналитики
            recipient_email = os.getenv('MAIN_ADMIN_EMAIL')
            subject_prefix = "на проверку отделом аналитики"
        elif new_status_id == 10:
            # Проверка колл-центром
            recipient_email = os.getenv('CALL_CENTER_MANAGER_EMAIL')
            subject_prefix = "на проверку колл-центром"
        elif new_status_id == 20:
            # Проверка КД - админу
            recipient_email = os.getenv('MAIN_ADMIN_EMAIL')
            subject_prefix = f"на проверку Коммерческим Директором"
        elif new_status_id in [200, 300]:
            # Акцептовано к оплате или Оплачено - менеджеру по платежам
            recipient_email = os.getenv('PAYMENT_MANAGER_EMAIL')
            subject_prefix = f"изменён на '{new_status_name}'"
        elif new_status_id == 500:
            # Отказано - уведомить пользователя-реферала + администраторов
            user_email = None
            
            # Получаем актуальный email из auth-service
            if referal_deal.referal and referal_deal.referal.user and referal_deal.referal.user.auth_user_id:
                user_email = get_user_email_from_auth_service(referal_deal.referal.user.auth_user_id)
            
            # Получаем данные о договоре
            agreement_number = referal_deal.deal.agreement_number if referal_deal.deal else 'Неизвестно'
            referal_name = referal_deal.referal.referal_data.full_name if referal_deal.referal and referal_deal.referal.referal_data else 'Неизвестно'
            referal_phone = referal_deal.referal.referal_data.phone_number if referal_deal.referal and referal_deal.referal.referal_data else 'Неизвестно'
            withdrawal_amount = referal_deal.withdrawal_amount or 0
            rejection_reason = referal_deal.rejection_reason or 'Причина не указана'
            user_name = user.user_data.full_name if hasattr(user, "user_data") and user.user_data else user.full_name if hasattr(user, "full_name") else "Неизвестный пользователь"
            
            notification_client = get_notification_client()
            
            # 1. Отправляем письмо пользователю об отказе
            if user_email:
                subject = f'Отказ по договору №{agreement_number}'
                body = f"""Уважаемый(ая) {referal_name},

К сожалению, ваш договор №{agreement_number} был отклонён.

Причина отказа: {rejection_reason}

Если у вас есть вопросы, пожалуйста, свяжитесь с нами."""
                
                notification_client.send_email(
                    recipient=user_email,
                    subject=subject,
                    body=body
                )
                print(f"✅ Rejection notification sent to user {user_email} for deal {referal_deal.id}")
            else:
                print(f"⚠️ Cannot send rejection notification: user email not found for deal {referal_deal.id}")
            
            # 2. Отправляем уведомление MAIN_ADMIN
            main_admin_email = os.getenv('MAIN_ADMIN_EMAIL')
            if main_admin_email:
                subject = f'Договор №{agreement_number} отклонён'
                body = f"""Сотрудник {user_name} отклонил договор.

Детали договора:
- Номер договора: {agreement_number}
- Реферал: {referal_name} ({referal_phone})
- Сумма вывода: {withdrawal_amount:,.0f} сум
- Статус: Отказано
- Причина отказа: {rejection_reason}"""
                
                if user_email:
                    body += f"\n\n✅ Пользователь уведомлён на email: {user_email}"
                else:
                    body += f"\n\n⚠️ Email пользователя не найден, уведомление не отправлено"
                
                notification_client.send_email(
                    recipient=main_admin_email,
                    subject=subject,
                    body=body
                )
                print(f"✅ Rejection notification sent to MAIN_ADMIN {main_admin_email} for deal {referal_deal.id}")
            
            # 3. Отправляем уведомление PAYMENT_MANAGER
            payment_manager_email = os.getenv('PAYMENT_MANAGER_EMAIL')
            if payment_manager_email and payment_manager_email != main_admin_email:
                subject = f'Договор №{agreement_number} отклонён'
                body = f"""Сотрудник {user_name} отклонил договор.

Детали договора:
- Номер договора: {agreement_number}
- Реферал: {referal_name} ({referal_phone})
- Сумма вывода: {withdrawal_amount:,.0f} сум
- Статус: Отказано
- Причина отказа: {rejection_reason}"""
                
                notification_client.send_email(
                    recipient=payment_manager_email,
                    subject=subject,
                    body=body
                )
                print(f"✅ Rejection notification sent to PAYMENT_MANAGER {payment_manager_email} for deal {referal_deal.id}")
            
            return
        else:
            print(f"⚠️ Unknown status_id {new_status_id} - skipping notification")
            return
        
        if not recipient_email:
            print(f"⚠️ Email not configured for status {new_status_id}")
            return
        
        # Получаем данные о договоре и реферале
        agreement_number = referal_deal.deal.agreement_number if referal_deal.deal else 'Неизвестно'
        referal_name = referal_deal.referal.referal_data.full_name if referal_deal.referal and referal_deal.referal.referal_data else 'Неизвестно'
        referal_phone = referal_deal.referal.referal_data.phone_number if referal_deal.referal and referal_deal.referal.referal_data else 'Неизвестно'
        withdrawal_amount = referal_deal.withdrawal_amount or 0
        user_name = user.user_data.full_name if hasattr(user, "user_data") and user.user_data else user.full_name if hasattr(user, "full_name") else "Неизвестный пользователь"
        
        # Формируем тело письма
        subject = f'Договор №{agreement_number} отправлен {subject_prefix}'
        body = f"""Сотрудник {user_name} отправил договор {subject_prefix}.

Детали договора:
- Номер договора: {agreement_number}
- Реферал: {referal_name} ({referal_phone})
- Сумма вывода: {withdrawal_amount:,.0f} сум
- Новый статус: {new_status_name}

Требуется ваша проверка."""
        
        # Получаем notification client
        notification_client = get_notification_client()
        
        # Отправляем уведомление основному получателю
        notification_client.send_email(
            recipient=recipient_email,
            subject=subject,
            body=body
        )
        print(f"✅ Deal status notification sent to {recipient_email} for deal {referal_deal.id}, status {new_status_id}")
        
        # Дублируем письмо на MAIN_ADMIN_EMAIL если это не он был основным получателем
        main_admin_email = os.getenv('MAIN_ADMIN_EMAIL')
        if main_admin_email and recipient_email != main_admin_email and new_status_id != 1:
            notification_client.send_email(
                recipient=main_admin_email,
                subject=f"[Копия] {subject}",
                body=body
            )
            print(f"✅ Copy sent to MAIN_ADMIN_EMAIL: {main_admin_email}")
        
    except Exception as e:
        print(f"❌ Failed to send deal status notification: {str(e)}")


# DEAL STATUS UPDATE
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
        
        # Проверяем права - пользователь должен быть владельцем реферала
        if referal_deal.referal.user_id != local_user.id:
            print(f"🚫 Send for review: Access denied. Referal user_id={referal_deal.referal.user_id}, Local user id={local_user.id}")
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