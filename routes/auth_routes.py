"""Маршруты для аутентификации и работы с пользователями"""

import os
from flask import Blueprint, request, g, jsonify
from header_utils import decode_header_full_name
from models import User, UserData, db
from permission_utils import get_user_role_type

auth_bp = Blueprint('auth', __name__)


def get_current_user():
    """Get current user information from request headers"""
    username = request.headers.get('X-User-Name')
    auth_user_id = request.headers.get('X-User-ID')
    
    # First try to find user by auth_user_id (more reliable after migration)
    user = None
    if auth_user_id:
        user = User.query.filter_by(auth_user_id=auth_user_id).first()
    
    # Fallback to username search if not found by auth_user_id
    if not user and username:
        user = User.query.filter_by(login=username).first()
    
    full_name = decode_header_full_name(request)
    
    # Determine role type based on permissions and roles from headers
    role = get_user_role_type()
    
    # Создание нового пользователя если не найден
    if not user and username and auth_user_id:
        full_name = decode_header_full_name(request)
        
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
    # DEPRECATED: Не обновляем user.role - роли теперь управляются через permissions в auth-service
    # if user and (user.role != role):
    #     user.role = role
        
    # Обновляем auth_user_id если он не установлен, но есть в заголовках
    if user and not user.auth_user_id:
        auth_user_id = request.headers.get('X-User-ID')
        if auth_user_id:
            user.auth_user_id = auth_user_id
            
    try:
        db.session.commit()
        
        # Синхронизируем данные с auth-service если есть auth_user_id
        if user and user.auth_user_id:
            try:
                from utils import sync_user_data_from_auth_service
                sync_user_data_from_auth_service(user, force_sync=True, headers=request.headers)
            except Exception as e:
                print(f"Warning: Failed to sync user data from auth-service: {e}")
                
    except Exception as e:
        db.session.rollback()
        print(f"Error creating user: {str(e)}")
    return user
