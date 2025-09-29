"""
Example referal_routes.py updated with auth-connector
Shows how to migrate from simple role checks to permission-based authorization
"""

from flask import Blueprint, render_template, request, redirect, url_for, jsonify, g, current_app
import services.referal_service as referal_service
from models import User, Referal, db
import re
import os
import random
from services import notification_service
from routes.auth_routes import get_current_user

# AUTH-CONNECTOR INTEGRATION
try:
    from auth_connector import require_permission, require_any_permission, get_current_user as get_auth_user
    AUTH_CONNECTOR_AVAILABLE = True
except ImportError:
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
        return get_auth_user()
    else:
        return get_current_user()

@referal_bp.route('/', methods=['GET'])
@require_permission('referal.profile.view')  # NEW: Permission-based authorization
def index():
    """Main referral page with permission check"""
    user = get_user()
    
    if not user:
        print("No user found, redirecting to referal profile")
        return redirect(url_for('referal.profile'))
    
    # OLD WAY (keep as fallback):
    # if user.role == 'admin' or user.role == 'manager' or user.role == 'call-center':
    
    # NEW WAY: Check permissions
    if AUTH_CONNECTOR_AVAILABLE:
        if user.has_any_permission(['referal.admin.manage_users', 'referal.users.manage', 'referal.leads.view']):
            return redirect(url_for('admin.admin_panel'))
    else:
        # Legacy fallback
        if hasattr(user, 'role') and user.role in ['admin', 'manager', 'call-center']:
            return redirect(url_for('admin.admin_panel'))
    
    # Update deal info for regular users
    if hasattr(user, 'id'):
        referal_service.update_deal_info(user)
    
    return redirect(url_for('referal.profile'))

@referal_bp.route('/profile', methods=['GET'])
@require_permission('referal.profile.view')
def profile():
    """User profile page"""
    user = get_user()
    
    if not user:
        return render_template('profile.html', 
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
    
    return render_template('profile.html', user=user)

@referal_bp.route('/add_referal', methods=['GET'])
@require_permission('referal.referrals.create')
def add_referal_form():
    """Show add referral form"""
    user = get_user()
    
    if not user:
        return redirect(url_for('referal.profile'))
    
    return render_template('add_referal.html', user=user)

@referal_bp.route('/add_referal', methods=['POST'])
@require_permission('referal.referrals.create')
def add_referal():
    """Add new referral with permission check"""
    user = get_user()
    
    if not user:
        return jsonify({'success': False, 'message': 'Пользователь не авторизован'})
    
    # Get form data
    full_name = request.form.get('full_name')
    phone = request.form.get('phone')
    contact_method = request.form.get('contact_method', 'Обычный звонок')
    
    if not full_name or not phone:
        return jsonify({
            'success': False, 
            'message': 'Пожалуйста, заполните все обязательные поля'
        })
    
    # Validate and format phone
    phone_digits = re.sub(r'\D', '', phone)
    if len(phone_digits) < 9:
        return jsonify({
            'success': False,
            'message': 'Пожалуйста, введите корректный номер телефона'
        })
    
    formatted_phone = f"+998{phone_digits[-9:]}"
    
    try:
        # Create referral
        new_referal = Referal(
            user_id=user.id,
            full_name=full_name,
            phone=formatted_phone,
            contact_method=contact_method
        )
        
        db.session.add(new_referal)
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
        return jsonify({
            'success': False,
            'message': 'Ошибка при добавлении реферала. Попробуйте еще раз.'
        })

@referal_bp.route('/my_referrals')
@require_permission('referal.referrals.view')
def my_referrals():
    """View user's referrals"""
    user = get_user()
    
    if not user:
        return redirect(url_for('referal.profile'))
    
    # Get user's referrals
    referrals = Referal.query.filter_by(user_id=user.id).all()
    
    return render_template('my_referrals.html', 
                         user=user, 
                         referrals=referrals)

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
        notification_service.send_notification(
            to=call_center_email,
            subject='Новый реферал добавлен',
            body=f'Пользователь {user.user_data.full_name if hasattr(user, "user_data") else user.full_name} добавил нового реферала: {full_name} ({phone}). Создайте встречу реферала с менеджером: {manager} для дальнейшего взаимодействия с клиентом.'
        )
        
    except Exception as e:
        print(f"Failed to send referral notification: {str(e)}")

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