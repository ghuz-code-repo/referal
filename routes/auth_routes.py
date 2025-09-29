"""Маршруты для аутентификации и работы с пользователями"""

from flask import Blueprint, request, g, jsonify
from header_utils import decode_header_full_name
from models import User, UserData, db

auth_bp = Blueprint('auth', __name__)


def get_current_user():
    """Get current user information from request headers"""
    username = request.headers.get('X-User-Name')
    print(f"DEBUG get_current_user: X-User-Name = {username}")
    
    # Log ALL headers for debugging
    print("DEBUG: ALL HEADERS:")
    for header_name, header_value in request.headers.items():
        if header_name.lower().startswith('x-user'):
            print(f"  {header_name}: {header_value}")
    
    user = User.query.filter_by(login=username).first()
    
    is_admin = request.headers.get('X-User-Admin', 'false').lower() == 'true'
    full_name = decode_header_full_name(request)

    # Try service-specific roles first, fallback to legacy roles
    service_role_str = request.headers.get('X-User-Service-Roles')
    legacy_role_str = request.headers.get('X-User-Roles')
    role_str = service_role_str if service_role_str else legacy_role_str
    roles = str.split(role_str, ',') if role_str else []
    role = ''
    
    print(f"DEBUG: Headers - X-User-Service-Roles: {service_role_str}, X-User-Roles: {legacy_role_str}, parsed roles: {roles}")
    print(f"DEBUG: is_admin from header: {is_admin}")

    if 'referal' in roles or 'referal-user' in roles or 'referer' in roles :
        role = 'referer'
    if 'referal-manager' in roles:
        role = 'manager' 
    if 'referal-call-center' in roles:
        role = 'call-center' 
    if 'admin' in roles or 'referal-admin' in roles:
        role = 'admin'
        
    print(f"DEBUG: Final determined role: {role}")  
    if user:
        print(f"DEBUG: User found: {user.login}, current role: {user.role}, determined role: {role}, is_admin: {is_admin}")
        if user.role != 'admin' and is_admin:
            user.role = 'admin'
            db.session.commit()
    else:
        print(f"DEBUG: No user found with username: {username}")

    # Создание нового пользователя если не найден
    if not user and username:
        full_name = decode_header_full_name(request)
        
        # Получаем auth_user_id из заголовка
        auth_user_id = request.headers.get('X-User-ID')
        
        user = User(
            login=username,
            auth_user_id=auth_user_id,
            role=role,
            current_balance=0,
            pending_withdrawal=0,
            total_withdrawal=0
        )
        
        db.session.add(user)
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"Error creating user first time: {str(e)}")
        
        user_data = UserData(
            user_id=user.id,
            full_name=full_name
        )

        user.user_data = user_data
        db.session.add(user)
    
    if user and not user.user_data:
        user.user_data = UserData(user_id=user.id, full_name=full_name)

    # if user and (user.user_data.full_name != full_name):
    #     user.user_data.full_name = full_name
    if user and (user.role != role):
        user.role = role
        
    # Обновляем auth_user_id если он не установлен, но есть в заголовках
    if user and not user.auth_user_id:
        auth_user_id = request.headers.get('X-User-ID')
        if auth_user_id:
            user.auth_user_id = auth_user_id
            
    try:
        print(f"User {user.login} updated with full_name: {user.user_data.full_name}, role: {user.role}")
        db.session.commit()
        
        # Синхронизируем данные с auth-service если есть auth_user_id
        if user and user.auth_user_id:
            try:
                from utils import sync_user_data_from_auth_service
                sync_user_data_from_auth_service(user, force_sync=False)
            except Exception as e:
                print(f"Warning: Failed to sync user data from auth-service: {e}")
                
    except Exception as e:
        db.session.rollback()
        print(f"Error creating user: {str(e)}")
    return user


@auth_bp.route('/debug-headers')
def debug_headers():
    """Отладочный маршрут для проверки заголовков"""
    headers = {key: value for key, value in request.headers.items()}
    decoded_name = decode_header_full_name(request)
    
    return jsonify({
        'headers': headers,
        'decoded_full_name': decoded_name,
        'encoding_header': request.headers.get('X-User-Full-Name-Encoding', 'not-set')
    })
