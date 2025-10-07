"""API для работы с документами пользователя из auth-service"""

from flask import Blueprint, request, jsonify, current_app
from .auth_routes import get_current_user
import requests

user_documents_api_bp = Blueprint('user_documents_api', __name__)


@user_documents_api_bp.route('/api/user_documents')
def get_user_documents_api():
    """API для получения документов пользователя (AJAX запросы)"""
    try:
        from auth_connector import require_permission
        # Проверяем разрешение на просмотр документов
        if not require_permission('profile.documents'):
            return jsonify({'success': False, 'error': 'Нет прав для просмотра документов'}), 403
    except ImportError:
        # Fallback если auth_connector недоступен
        pass
    
    current_user = get_current_user()
    if not current_user:
        return jsonify({'success': False, 'error': 'Пользователь не найден'}), 401
    
    try:
        # Получаем auth_user_id из локальной базы данных
        from models import User
        user = User.query.filter_by(login=current_user.login).first()
        if not user or not user.auth_user_id:
            return jsonify({'success': False, 'error': 'Пользователь не связан с auth-service'}), 404
        
        # Получаем список документов из auth-service используя прямой HTTP запрос
        auth_service_url = current_app.config.get('AUTH_SERVICE_URL', 'http://gateway-nginx-1')
        api_url = f"{auth_service_url}/api/users/{user.auth_user_id}/documents"
        
        # Копируем заголовки аутентификации из текущего запроса
        headers = {
            'X-Original-URI': request.path,
            'X-Real-IP': request.environ.get('HTTP_X_REAL_IP', request.remote_addr),
            'User-Agent': 'Referal-Service/1.0',
            'Accept': 'application/json'
        }
        
        # Копируем важные заголовки из текущего запроса
        for header_name in ['X-User-ID', 'X-User-Name', 'X-User-Permissions', 'Authorization']:
            if header_name in request.headers:
                headers[header_name] = request.headers[header_name]
        
        response = requests.get(api_url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            documents_data = response.json()
            documents = documents_data.get('documents', [])
            
            # Форматируем данные для frontend
            formatted_documents = []
            for doc in documents:
                formatted_documents.append({
                    'id': doc.get('id', ''),
                    'title': doc.get('title', 'Документ'),
                    'type': doc.get('type', 'document'),
                    'status': doc.get('status', 'unknown'),
                    'created_at': doc.get('created_at', ''),
                    'updated_at': doc.get('updated_at', ''),
                    'file_name': doc.get('file_name', ''),
                    'file_size': doc.get('file_size', 0)
                })
            
            return jsonify({
                'success': True, 
                'documents': formatted_documents,
                'total': len(formatted_documents)
            })
        else:
            print(f"Ошибка получения документов: HTTP {response.status_code}")
            return jsonify({'success': False, 'error': f'Ошибка сервера: {response.status_code}'}), response.status_code
            
    except Exception as e:
        print(f"Исключение при получении документов: {e}")
        return jsonify({'success': False, 'error': 'Внутренняя ошибка сервера'}), 500