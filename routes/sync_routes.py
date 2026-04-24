"""
Permission sync routes for referal service
Provides endpoints for auth-service to discover and sync permissions
"""

from flask import Blueprint, jsonify, request
from auth_connector import PermissionRegistry

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
    
    # Разрешения на работу с рефералами
    registry.register("referal.referrals.create", "Создание рефералов", "Создание/добавление новых рефералов в систему", "referrals")
    registry.register("referal.referrals.add", "Добавление рефералов", "Добавление новых рефералов в систему (устаревшее)", "referrals")
    registry.register("referal.referrals.view", "Просмотр рефералов", "Просмотр своих рефералов", "referrals")
    registry.register("referal.referrals.list", "Список рефералов", "Просмотр списка своих рефералов", "referrals")
    registry.register("referal.referrals.edit", "Редактирование рефералов", "Редактирование информации о рефералах", "referrals")
    
    # Разрешения на платежи
    registry.register("referal.payments.view", "Просмотр платежей", "Просмотр истории платежей и балансов", "payments")
    registry.register("referal.payments.request", "Запрос выплат", "Запрос вывода средств", "payments")
    
    # Разрешения на уведомления
    # Общие уведомления
    registry.register("referal.notifications.all", "Все уведомления сервиса", "Получение ВСЕХ email уведомлений от сервиса рефералов (глобальное)", "notifications")
    registry.register("referal.notifications.new_referral", "Уведомления о новых рефералах", "Получение email уведомлений при создании новых рефералов", "notifications")
    registry.register("referal.notifications.payment", "Уведомления о платежах", "Получение уведомлений о платежах и выплатах", "notifications")
    registry.register("referal.notifications.admin", "Административные уведомления", "Получение административных уведомлений и алертов", "notifications")
    
    # Уведомления по статусам - при переходе В конкретный статус
    registry.register("referal.notifications.status.pending", "Уведомление: Ожидает проверки", "Получение уведомлений при переходе реферала в статус 'Ждёт проверки'", "notifications_status")
    registry.register("referal.notifications.status.analytics_review", "Уведомление: Проверка аналитики", "Получение уведомлений при переходе реферала в статус 'Проверка отделом аналитики'", "notifications_status")
    registry.register("referal.notifications.status.callcenter_review", "Уведомление: Проверка КЦ", "Получение уведомлений при переходе реферала в статус 'Проверка колл центром'", "notifications_status")
    registry.register("referal.notifications.status.director_review", "Уведомление: Проверка директора", "Получение уведомлений при переходе реферала в статус 'Проверка Коммерческим Директором'", "notifications_status")
    registry.register("referal.notifications.status.accepted", "Уведомление: Принято к оплате", "Получение уведомлений при переходе реферала в статус 'Акцептовано к оплате'", "notifications_status")
    registry.register("referal.notifications.status.paid", "Уведомление: Оплачено", "Получение уведомлений при переходе реферала в статус 'Оплачено'", "notifications_status")
    registry.register("referal.notifications.status.rejected", "Уведомление: Отклонено", "Получение уведомлений при переходе реферала в статус 'Отклонено'", "notifications_status")
    
    # Административные функции
    registry.register("referal.admin.panel", "Админ панель", "Доступ к административной панели", "admin")
    registry.register("referal.admin.change_status", "Изменение статусов", "Изменение статусов вывода средств рефералов", "admin")
    registry.register("referal.admin.view_reports", "Просмотр отчетов", "Просмотр административных отчетов", "admin")
    registry.register("referal.admin.export_data", "Экспорт данных", "Экспорт данных в Excel", "admin")
    registry.register("referal.admin.export_database_excel", "Полный экспорт БД в Excel", "Скачивание полного дампа базы данных referal в формате Excel (.xlsx, по листу на таблицу)", "admin")
    registry.register("referal.admin.manual_db_backup", "Ручной бэкап БД (pg_dump)", "Создание ручного несжимаемого бэкапа PostgreSQL в backups/manual/ (никогда не очищается автоматически)", "admin")
    registry.register("referal.admin.force_update", "Принудительная синхронизация", "Запуск принудительной синхронизации с MacroData", "admin")
    registry.register("referal.admin.manage_users", "Управление пользователями", "Управление пользователями сервиса", "admin")
    
    # Отчёты и статистика
    registry.register("referal.reports.view", "Просмотр отчётов", "Просмотр детализированных отчётов", "reports")
    registry.register("referal.stats.view", "Просмотр статистики", "Просмотр полной статистики системы", "reports")


    # Детализированные разрешения для статусов
    # Статус "Ждет проверки" (ID: 0)
    registry.register("referal.status.pending.view", "Просмотр ожидающих", "Просмотр рефералов в статусе ожидания проверки", "status_pending")
    registry.register("referal.status.pending.edit", "Редактирование ожидающих", "Редактирование рефералов в статусе ожидания", "status_pending")
    registry.register("referal.status.pending.move_to", "Перевод В ожидание", "Перевод рефералов в статус ожидания", "status_pending")
    registry.register("referal.status.pending.move_from", "Перевод ИЗ ожидания", "Перевод рефералов из статуса ожидания", "status_pending")
    
    # Статус "Проверка отделом аналитики" (ID: 1)
    registry.register("referal.status.analytics_review.view", "Просмотр на аналитике", "Просмотр рефералов на проверке в аналитике", "status_analytics")
    registry.register("referal.status.analytics_review.edit", "Редактирование на аналитике", "Редактирование рефералов на проверке в аналитике", "status_analytics")
    registry.register("referal.status.analytics_review.move_to", "Перевод НА аналитику", "Перевод рефералов на проверку в аналитику", "status_analytics")
    registry.register("referal.status.analytics_review.move_from", "Перевод С аналитики", "Перевод рефералов с проверки в аналитике", "status_analytics")
    
    # Статус "Проверка колл центром" (ID: 10)
    registry.register("referal.status.callcenter_review.view", "Просмотр в колл-центре", "Просмотр рефералов на проверке в колл-центре", "status_callcenter")
    registry.register("referal.status.callcenter_review.edit", "Редактирование в колл-центре", "Редактирование рефералов в колл-центре", "status_callcenter")
    registry.register("referal.status.callcenter_review.move_to", "Перевод В колл-центр", "Перевод рефералов на проверку в колл-центр", "status_callcenter")
    registry.register("referal.status.callcenter_review.move_from", "Перевод ИЗ колл-центра", "Перевод рефералов с проверки в колл-центре", "status_callcenter")
    
    # Статус "Проверка Коммерческим Директором" (ID: 20)
    registry.register("referal.status.director_review.view", "Просмотр у директора", "Просмотр рефералов на проверке у директора", "status_director")
    registry.register("referal.status.director_review.edit", "Редактирование у директора", "Редактирование рефералов у директора", "status_director")
    registry.register("referal.status.director_review.move_to", "Перевод К директору", "Перевод рефералов на проверку к директору", "status_director")
    registry.register("referal.status.director_review.move_from", "Перевод ОТ директора", "Перевод рефералов от директора", "status_director")
    
    # Статус "Акцептовано к оплате" (ID: 200)
    registry.register("referal.status.accepted.view", "Просмотр принятых", "Просмотр рефералов принятых к оплате", "status_accepted")
    registry.register("referal.status.accepted.edit", "Редактирование принятых", "Редактирование рефералов принятых к оплате", "status_accepted")
    registry.register("referal.status.accepted.move_to", "Принятие к оплате", "Перевод рефералов в статус принято к оплате", "status_accepted")
    registry.register("referal.status.accepted.move_from", "Перевод ИЗ принятых", "Перевод рефералов из статуса принято к оплате", "status_accepted")
    
    # Статус "Оплачено" (ID: 300)
    registry.register("referal.status.paid.view", "Просмотр оплаченных", "Просмотр оплаченных рефералов", "status_paid")
    registry.register("referal.status.paid.edit", "Редактирование оплаченных", "Редактирование оплаченных рефералов", "status_paid")
    registry.register("referal.status.paid.move_to", "Перевод В оплачено", "Перевод рефералов в статус оплачено", "status_paid")
    registry.register("referal.status.paid.move_from", "Перевод ИЗ оплаченных", "Перевод рефералов из статуса оплачено", "status_paid")
    
    # Статус "Отклонено" (ID: 500) - дополнительный
    registry.register("referal.status.rejected.view", "Просмотр отклоненных", "Просмотр отклоненных рефералов", "status_rejected")
    registry.register("referal.status.rejected.edit", "Редактирование отклоненных", "Редактирование отклоненных рефералов", "status_rejected")
    registry.register("referal.status.rejected.move_to", "Отклонение", "Перевод рефералов в статус отклонено", "status_rejected")
    registry.register("referal.status.rejected.move_from", "Перевод ИЗ отклоненных", "Перевод рефералов из статуса отклонено", "status_rejected")

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