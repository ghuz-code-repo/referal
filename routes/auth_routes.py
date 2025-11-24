"""Маршруты для аутентификации и работы с пользователями"""

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
    
    is_admin = request.headers.get('X-User-Admin', 'false').lower() == 'true'
    full_name = decode_header_full_name(request)

    # Get user permissions and determine role type based on permissions
    permissions_str = request.headers.get('X-User-Service-Permissions', '')
    if not permissions_str:
        permissions_str = request.headers.get('X-User-Permissions', '')
    permissions = permissions_str.split(',') if permissions_str else []
    
    # Determine role type based on permissions instead of hardcoded roles
    role = get_user_role_type()
    
    # Legacy fallback: Try service-specific roles if no permissions found
    if role == 'none':
        service_role_str = request.headers.get('X-User-Service-Roles')
        legacy_role_str = request.headers.get('X-User-Roles')
        role_str = service_role_str if service_role_str else legacy_role_str
        roles = str.split(role_str, ',') if role_str else []

        if 'referal' in roles or 'referal-user' in roles or 'referer' in roles:
            role = 'referer'
        if 'referal-manager' in roles:
            role = 'manager' 
        if 'referal-call-center' in roles:
            role = 'call-center' 
        if 'admin' in roles or 'referal-admin' in roles:
            role = 'admin'
        
    if user:
        if user.role != 'admin' and is_admin:
            user.role = 'admin'
            db.session.commit()
    
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


@auth_bp.route('/debug-documents')
def debug_documents():
    """Отладочный маршрут для проверки получения документов из auth-service"""
    from flask import current_app
    import requests
    
    user_id = request.headers.get('X-User-ID')
    username = request.headers.get('X-User-Name')
    
    result = {
        'user_id': user_id,
        'username': username,
        'auth_service_url': current_app.config.get('AUTH_SERVICE_URL', 'NOT_SET'),
        'documents_from_headers': {},
        'documents_from_api': {},
        'api_request_details': {},
        'errors': []
    }
    
    # 1. Документы из заголовков
    result['documents_from_headers'] = {
        'passport_number': request.headers.get('X-User-Passport-Number'),
        'passport_giver': request.headers.get('X-User-Passport-Giver'),
        'passport_date': request.headers.get('X-User-Passport-Date'),
        'passport_address': request.headers.get('X-User-Passport-Address'),
        'pinfl': request.headers.get('X-User-PINFL'),
        'bank_name': request.headers.get('X-User-Bank-Name'),
        'bank_card': request.headers.get('X-User-Bank-Card'),
        'bank_account': request.headers.get('X-User-Bank-Account'),
        'bank_mfo': request.headers.get('X-User-Bank-MFO'),
    }
    
    # 2. Документы через API
    if user_id:
        try:
            auth_service_url = current_app.config.get('AUTH_SERVICE_URL', 'http://gateway-nginx-1')
            api_url = f"{auth_service_url}/api/users/{user_id}/documents/for-service/referal"
            
            result['api_request_details']['url'] = api_url
            result['api_request_details']['method'] = 'GET'
            result['api_request_details']['timeout'] = 5
            
            response = requests.get(api_url, timeout=5)
            result['api_request_details']['status_code'] = response.status_code
            result['api_request_details']['response_headers'] = dict(response.headers)
            
            if response.status_code == 200:
                data = response.json()
                result['documents_from_api'] = data
            else:
                result['errors'].append(f"API returned status {response.status_code}")
                result['api_request_details']['response_text'] = response.text[:500]
                
        except requests.RequestException as e:
            result['errors'].append(f"Network error: {str(e)}")
        except Exception as e:
            result['errors'].append(f"General error: {str(e)}")
    else:
        result['errors'].append('No X-User-ID header found')
    
    return jsonify(result)
