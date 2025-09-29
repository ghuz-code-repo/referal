"""
Permission sync routes for referal service
Provides endpoints for auth-service to discover and sync permissions
"""

from flask import Blueprint, jsonify, request
from auth_connector import PermissionRegistry, CommonPermissions

sync_bp = Blueprint('sync', __name__)

# Initialize permission registry for referal service  
permission_registry = PermissionRegistry("referal")

# Register all referal service permissions
def register_referal_permissions():
    """Register all permissions for referal service"""
    
    registry = permission_registry
    
    # Базовые функции системы
    registry.register("referal.profile.view", "Просмотр профиля", "Просмотр своего реферального профиля", "profile")
    registry.register("referal.profile.documents", "Просмотр документов", "Просмотр документов пользователя", "profile")
    registry.register("referal.profile.documents.download", "Скачивание документов", "Скачивание файлов документов", "profile")
    registry.register("referal.referrals.add", "Добавление рефералов", "Добавление новых рефералов в систему", "referrals")
    registry.register("referal.referrals.list", "Список рефералов", "Просмотр списка своих рефералов", "referrals")
    registry.register("referal.payments.view", "Просмотр платежей", "Просмотр истории платежей и балансов", "payments")
    registry.register("referal.payments.request", "Запрос выплат", "Запрос вывода средств", "payments")
    
    # Административные функции
    registry.register("referal.admin.panel", "Админ панель", "Доступ к административной панели", "admin")
    registry.register("referal.admin.change_status", "Изменение статусов", "Изменение статусов вывода средств рефералов", "admin")
    registry.register("referal.admin.reports", "Отчеты", "Просмотр административных отчетов", "admin")
    registry.register("referal.admin.export", "Экспорт данных", "Экспорт данных в Excel", "admin")

# Register permissions on import
register_referal_permissions()

@sync_bp.route('/permissions', methods=['GET', 'POST'])  
def get_service_permissions():
    """
    Get all available permissions for this service
    Used by auth-service to sync permissions
    """
    try:
        return jsonify({
            "success": True,
            "service_key": "referal",
            "permissions": permission_registry.to_dict()["permissions"],
            "total_permissions": len(permission_registry.get_all_permissions()),
            "categories": list(set(p.category for p in permission_registry.get_all_permissions() if p.category))
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@sync_bp.route('/permissions/validate', methods=['POST'])
def validate_permissions():
    """
    Validate if given permissions exist in this service
    """
    try:
        data = request.get_json()
        permissions_to_check = data.get('permissions', [])
        
        valid_permissions = [p.name for p in permission_registry.get_all_permissions()]
        
        results = {}
        for perm in permissions_to_check:
            results[perm] = perm in valid_permissions
        
        return jsonify({
            "success": True,
            "validation_results": results,
            "valid_count": sum(results.values()),
            "total_count": len(permissions_to_check)
        })
    
    except Exception as e:
        return jsonify({
            "success": False, 
            "error": str(e)
        }), 500

@sync_bp.route('/permissions/by-category/<category>', methods=['GET'])
def get_permissions_by_category(category):
    """
    Get permissions by category
    """
    try:
        permissions = permission_registry.get_permissions_by_category(category)
        return jsonify({
            "success": True,
            "category": category,
            "permissions": [
                {
                    "name": p.name,
                    "displayName": p.display_name,
                    "description": p.description
                }
                for p in permissions
            ],
            "count": len(permissions)
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)  
        }), 500

@sync_bp.route('/health', methods=['GET'])
def sync_health():
    """Health check for sync endpoints"""
    return jsonify({
        "status": "healthy",
        "service": "referal",
        "permissions_count": len(permission_registry.get_all_permissions())
    })