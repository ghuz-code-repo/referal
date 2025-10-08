"""Утилиты для работы с разрешениями"""

from flask import request
from status_permissions import (
    can_view_status,
    can_edit_status, 
    can_move_to_status,
    can_move_from_status,
    can_change_status_detailed,
    get_viewable_statuses,
    get_editable_statuses,
    get_target_statuses,
    get_source_statuses,
    get_status_transitions,
    get_user_status_summary
)


def get_user_permissions():
    """Получает список разрешений пользователя из заголовков"""
    
    # Try service-specific permissions first
    permissions_str = request.headers.get('X-User-Service-Permissions', '')
    if not permissions_str:
        # Fallback to legacy header if needed
        permissions_str = request.headers.get('X-User-Permissions', '')
    
    permissions = permissions_str.split(',') if permissions_str else []
    return permissions


def has_permission(permission):
    """Проверяет, есть ли у пользователя конкретное разрешение"""
    user_permissions = get_user_permissions()
    return permission in user_permissions


def has_any_permission(permissions):
    """Проверяет, есть ли у пользователя любое из указанных разрешений"""
    user_permissions = get_user_permissions()
    return any(perm in user_permissions for perm in permissions)


def has_all_permissions(permissions):
    """Проверяет, есть ли у пользователя все указанные разрешения"""
    user_permissions = get_user_permissions()
    return all(perm in user_permissions for perm in permissions)


def get_user_role_type():
    """
    Определяет тип пользователя на основе разрешений и ролей из заголовков
    Возвращает один из: 'admin', 'manager', 'call-center', 'analytics', 'referer', 'none'
    """
    permissions = get_user_permissions()
    
    # Сначала проверяем роли из заголовков (более надежный способ)
    service_roles_str = request.headers.get('X-User-Service-Roles', '')
    global_roles_str = request.headers.get('X-User-Roles', '')
    
    # Проверяем сервисные роли
    if service_roles_str:
        service_roles = [role.strip() for role in service_roles_str.split(',')]
        if 'analytic' in service_roles or 'analytics' in service_roles:
            return 'analytics'
        if 'manager' in service_roles:
            return 'manager'
        if 'call-center' in service_roles:
            return 'call-center'
    
    # Проверяем глобальные роли
    if global_roles_str:
        global_roles = [role.strip() for role in global_roles_str.split(',')]
        if 'system.admin' in global_roles or 'admin' in global_roles:
            return 'admin'
        if 'analytic' in global_roles or 'analytics' in global_roles:
            return 'analytics'
    
    # Fallback: определяем по разрешениям (если роли в заголовках не найдены)
    
    # Проверяем системного администратора (имеет много разрешений)
    if (has_permission('referal.admin.panel') and 
        has_permission('referal.admin.change_status') and
        len(permissions) > 6):  # У админа больше разрешений
        return 'admin'
    
    # Проверяем менеджера (может изменять статусы)
    if has_permission('referal.admin.change_status'):
        return 'manager'
    
    # Проверяем колл-центр (может просматривать и обрабатывать рефералов)
    if has_any_permission(['referal.admin.reports', 'referal.admin.export']):
        return 'call-center'
    
    # Обычный пользователь (может добавлять рефералов)
    if has_permission('referal.referrals.add'):
        return 'referer'
    
    # Fallback: если разрешений нет, проверяем роли из заголовков
    print("DEBUG: Determined role type from permissions: none")
    service_roles_str = request.headers.get('X-User-Service-Roles', '')
    global_roles_str = request.headers.get('X-User-Roles', '')
    
    print(f"DEBUG: Fallback to legacy roles - X-User-Service-Roles: {service_roles_str}, X-User-Roles: {global_roles_str}")
    
    if service_roles_str:
        service_roles = [role.strip() for role in service_roles_str.split(',')]
        if 'referal-manager' in service_roles or 'manager' in service_roles:
            print("DEBUG: Final determined role: manager")
            return 'manager'
        if 'referal-call-center' in service_roles or 'call-center' in service_roles:
            print("DEBUG: Final determined role: call-center")
            return 'call-center'
        if 'referal-analytics' in service_roles or 'analytics' in service_roles or 'analytic' in service_roles:
            print("DEBUG: Final determined role: analytics")
            return 'analytics'
        if 'referal-admin' in service_roles:
            return 'admin'
    
    if global_roles_str:
        global_roles = [role.strip() for role in global_roles_str.split(',')]
        if 'system.admin' in global_roles or 'admin' in global_roles:
            return 'admin'
        if 'manager' in global_roles:
            return 'manager'
        if 'call-center' in global_roles:
            return 'call-center'
        if 'analytics' in global_roles or 'analytic' in global_roles:
            return 'analytics'
    
    return 'none'


def get_allowed_statuses_for_user():
    """
    Возвращает список ID статусов, которые пользователь может видеть
    на основе его детализированных разрешений
    """
    # Получаем права пользователя для отладки
    user_permissions = get_user_permissions()
    
    # Используем новую систему детализированных разрешений
    viewable_statuses = get_viewable_statuses()
    
    if viewable_statuses:
        return viewable_statuses
    
    # Fallback к старой системе ролей, если детализированных разрешений нет
    print(f"⚠️ No detailed status permissions | All permissions: {user_permissions}")
    role_type = get_user_role_type()
    print(f"📋 Using legacy role-based access | Detected role: {role_type}")
    
    if role_type == 'admin':
        # Админ может видеть все статусы
        from models import Status
        return [s.id for s in Status.query.all()]
    
    elif role_type == 'manager':
        # Менеджер видит: проверено аналитикой, оплачено, отклонено
        return [200, 300, 500]
    
    elif role_type == 'call-center':
        # Колл-центр видит: на проверке колл-центром, отклонено, проверено колл-центром
        return [10, 500, 20]
    
    elif role_type == 'analytics':
        # Аналитики видят: новые, поданные на проверку, проверенные колл-центром
        return [0, 1, 20]
    
    elif role_type == 'referer':
        # Обычный пользователь видит все свои рефералов
        from models import Status
        return [s.id for s in Status.query.all()]
    
    return []


def get_default_status_filter():
    """
    Возвращает статус по умолчанию для фильтрации на основе роли пользователя
    """
    role_type = get_user_role_type()
    
    if role_type == 'manager':
        return '200'  # Проверено аналитикой - менеджеры работают с этим статусом
    elif role_type == 'call-center':
        return '10'   # На проверке колл-центром
    elif role_type == 'analytics':
        return '0'    # Новые рефералы - аналитики работают с новыми заявками
    elif role_type == 'admin':
        return '1'    # Создан
    
    return ''


def can_change_status_to(status_id):
    """
    Проверяет, может ли пользователь изменить статус на указанный
    Использует новую детализированную систему разрешений
    """
    # Используем новую систему детализированных разрешений
    can_move = can_move_to_status(status_id)
    
    if can_move:
        print(f"DEBUG: User can move to status {status_id} via detailed permissions")
        return True
    
    # Fallback к старой системе ролей, если детализированных разрешений нет
    print(f"DEBUG: No detailed permissions, checking legacy role-based access for status {status_id}")
    
    role_type = get_user_role_type()
    
    # Проверяем конкретные разрешения для изменения статусов
    if role_type == 'admin':
        # Админ может изменять на любой статус
        return True
    
    elif role_type == 'manager':
        # Менеджер может изменять только на определенные статусы и только если текущий статус 200
        allowed_statuses = [0, 300, 500]  # создан, оплачено, отклонено (только с 200)
        return status_id in allowed_statuses
    
    elif role_type == 'call-center':
        # Колл-центр может изменять только на свои статусы
        allowed_statuses = [20, 500]  # проверено колл-центром, отклонено
        return status_id in allowed_statuses
    
    elif role_type == 'analytics':
        # Аналитики могут изменять только на определенные статусы
        allowed_statuses = [10, 200]  # на проверке в колл-центре, проверено аналитикой
        return status_id in allowed_statuses
    
    return False


def can_change_status_from_to(current_status_id, new_status_id):
    """
    Проверяет, может ли пользователь изменить статус с текущего на новый
    Использует новую детализированную систему разрешений
    """
    # Используем новую систему детализированных разрешений
    can_change = can_change_status_detailed(current_status_id, new_status_id)
    
    if can_change:
        print(f"DEBUG: User can change status {current_status_id} -> {new_status_id} via detailed permissions")
        return True
    
    # Fallback к старой системе ролей, если детализированных разрешений нет
    print(f"DEBUG: No detailed permissions, checking legacy role-based access for {current_status_id} -> {new_status_id}")
    
    role_type = get_user_role_type()
    
    # Проверяем конкретные разрешения для изменения статусов
    if role_type == 'admin':
        # Админ может изменять любой статус на любой
        return True
    
    elif role_type == 'manager':
        # Менеджер может изменять только если текущий статус 200 и новый статус в разрешенных
        if current_status_id != 200:
            return False
        allowed_statuses = [0, 300, 500]  # создан, оплачено, отклонено
        return new_status_id in allowed_statuses
    
    elif role_type == 'call-center':
        # Колл-центр может изменять только если текущий статус 10 и новый статус в разрешенных
        if current_status_id != 10:
            return False
        allowed_statuses = [20, 500]  # проверено колл-центром, отклонено
        return new_status_id in allowed_statuses
    
    elif role_type == 'analytics':
        # Аналитики могут изменять статус если текущий статус 0, 1, или 20 и новый статус в разрешенных
        if current_status_id not in [0, 1, 20]:
            return False
        allowed_statuses = [10, 200]  # на проверке в колл-центре, проверено аналитикой
        return new_status_id in allowed_statuses
    
    return False


def get_allowed_status_changes_for_user():
    """
    Возвращает список ID статусов, на которые пользователь может изменить
    на основе его детализированных разрешений
    """
    # Используем новую систему детализированных разрешений
    target_statuses = get_target_statuses()
    
    if target_statuses:
        print(f"DEBUG: User has detailed target status permissions: {target_statuses}")
        return target_statuses
    
    # Fallback к старой системе ролей, если детализированных разрешений нет
    print("DEBUG: No detailed permissions found, using legacy role-based target statuses")
    role_type = get_user_role_type()
    
    if role_type == 'admin':
        # Админ может изменять на любой статус
        from models import Status
        return [s.id for s in Status.query.all()]
    
    elif role_type == 'manager':
        # Менеджер может изменять только на определенные статусы
        return [0, 300, 500]  # создан, оплачено, отклонено
    
    elif role_type == 'call-center':
        # Колл-центр может изменять только на свои статусы
        return [20, 500]  # проверено колл-центром, отклонено
    
    elif role_type == 'analytics':
        # Аналитики могут изменять только на определенные статусы
        return [10, 200]  # на проверке в колл-центре, проверено аналитикой
    
    return []


def requires_admin_access():
    """Проверяет, есть ли у пользователя доступ к админ панели"""
    # Сначала пробуем проверить разрешения
    has_permissions = has_any_permission([
        'referal.admin.panel',
        'referal.admin.change_status', 
        'referal.admin.reports',
        'referal.admin.export'
    ])
    
    if has_permissions:
        print("DEBUG: Access granted via permissions")
        return True
    
    # Fallback: если разрешений нет, используем старую логику ролей из заголовков
    print("DEBUG: No permissions found, checking legacy roles")
    
    # Получаем роли напрямую из заголовков для fallback
    service_roles_str = request.headers.get('X-User-Service-Roles', '')
    global_roles_str = request.headers.get('X-User-Roles', '')
    
    print(f"DEBUG: Fallback to legacy roles - X-User-Service-Roles: {service_roles_str}, X-User-Roles: {global_roles_str}")
    
    # Проверяем service-specific роли
    if service_roles_str:
        service_roles = [role.strip() for role in service_roles_str.split(',')]
        legacy_admin_roles = ['referal-manager', 'referal-admin', 'admin', 'manager', 'call-center', 'analytics']
        if any(role in legacy_admin_roles for role in service_roles):
            print(f"DEBUG: Access granted via service role: {service_roles}")
            return True
    
    # Проверяем глобальные роли
    if global_roles_str:
        global_roles = [role.strip() for role in global_roles_str.split(',')]
        legacy_admin_roles = ['system.admin', 'admin', 'manager']
        if any(role in legacy_admin_roles for role in global_roles):
            print(f"DEBUG: Access granted via global role: {global_roles}")
            return True
    
    print("DEBUG: Access denied - no permissions and no valid role")
    return False