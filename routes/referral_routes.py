# Импорт необходимых модулей и классов
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from datetime import datetime
import re
from models import *
from .auth_routes import get_current_user
from services import referal_service, notification_service, data_sync_service, withdrawal_service
import utils
import os

referal_bp = Blueprint('referal', __name__)

# ...existing code...

@referal_bp.route('/fetch_macro_field/<int:contact_id>/<field_name>', methods=['GET'])
def fetch_macro_field(contact_id, field_name):
    """Получает отдельное поле клиента из MacroCRM по contact_id"""
    user = get_current_user()
    if not user:
        return jsonify({'success': False, 'error': 'Необходима авторизация'})
    
    try:
        # Получаем данные клиента из MacroCRM
        client_data = referal_service.fetch_client_data_from_macro(contact_id)
        
        if not client_data:
            return jsonify({'success': False, 'error': 'Клиент не найден в MacroCRM'})
        
        # Получаем запрошенное поле
        field_value = client_data.get(field_name)
        
        if field_value is None:
            return jsonify({'success': False, 'error': f'Поле {field_name} не найдено'})
        
        return jsonify({
            'success': True,
            'value': field_value,
            'field_name': field_name
        })
        
    except Exception as e:
        print(f"Error fetching macro field: {e}")
        return jsonify({'success': False, 'error': f'Ошибка при получении данных: {str(e)}'})


@referal_bp.route('/fetch_client_data/<int:contact_id>', methods=['GET'])
def fetch_client_data(contact_id):
    """Получает все данные клиента из MacroCRM по contact_id"""
    user = get_current_user()
    if not user:
        return jsonify({'success': False, 'error': 'Необходима авторизация'})
    
    try:
        # Получаем данные клиента из MacroCRM
        client_data = referal_service.fetch_client_data_from_macro(contact_id)
        
        if not client_data:
            return jsonify({'success': False, 'error': 'Клиент не найден в MacroCRM'})
        
        return jsonify({
            'success': True,
            'client_data': client_data,
            'contact_id': contact_id
        })
        
    except Exception as e:
        print(f"Error fetching client data: {e}")
        return jsonify({'success': False, 'error': f'Ошибка при получении данных: {str(e)}'})

# ...existing code...