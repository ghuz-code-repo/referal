#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тестовый маршрут для диагностики авторизации
"""
from flask import Blueprint, jsonify, request
from routes.auth_routes import get_current_user

debug_bp = Blueprint('debug', __name__, url_prefix='/debug')

@debug_bp.route('/current-user', methods=['GET'])
def debug_current_user():
    """Отладочный маршрут для проверки текущего пользователя"""
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