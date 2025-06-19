"""Маршруты для аутентификации и работы с пользователями"""

from flask import Blueprint, request, g, jsonify
from header_utils import decode_header_full_name
from models import User, UserData, db

auth_bp = Blueprint('auth', __name__)


def get_current_user():
    """Get current user information from request headers"""
    username = request.headers.get('X-User-Name')
    user = User.query.filter_by(login=username).first()
    
    is_admin = request.headers.get('X-User-Admin', 'false').lower() == 'true'
    full_name = decode_header_full_name(request)

    role_str = request.headers.get('X-User-Roles')
    roles = str.split(role_str, ',') if role_str else []
    role = ''

    if 'referal' in roles:
        role = 'referal'
    if 'referal-manager' in roles:
        role = 'manager' 
    if 'admin' in roles or 'referal-admin' in roles:
        role = 'admin'  
    if user:
        if user.role != 'admin' and is_admin:
            user.role = 'admin'
            db.session.commit()
    print(f"User found: {user}, is_admin: {is_admin}")
    
    # Создание нового пользователя если не найден
    if not user and username:
        full_name = decode_header_full_name(request)
        
        user = User(
            login=username,
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

    if user and (user.user_data.full_name != full_name):
        user.user_data.full_name = full_name
    if user and (user.role != role):
        user.role = role
    try:
        db.session.commit()
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
