"""
Детализированная система разрешений для статусов рефералов
Позволяет создавать роли с точными разрешениями на просмотр и изменение конкретных статусов
"""

from flask import request


# Детализированные разрешения для каждого статуса
STATUS_PERMISSIONS = {
    # Статус "Ждет проверки" (ID: 0)
    0: {
        'view': 'referal.status.pending.view',           # Просмотр заявок в ожидании
        'edit': 'referal.status.pending.edit',           # Изменение заявок в ожидании
        'move_to': 'referal.status.pending.move_to',     # Перевод В этот статус
        'move_from': 'referal.status.pending.move_from'  # Перевод ИЗ этого статуса
    },
    
    # Статус "Проверка отделом аналитики" (ID: 1)  
    1: {
        'view': 'referal.status.analytics_review.view',
        'edit': 'referal.status.analytics_review.edit',
        'move_to': 'referal.status.analytics_review.move_to',
        'move_from': 'referal.status.analytics_review.move_from'
    },
    
    # Статус "Проверка колл центром" (ID: 10)
    10: {
        'view': 'referal.status.callcenter_review.view',
        'edit': 'referal.status.callcenter_review.edit', 
        'move_to': 'referal.status.callcenter_review.move_to',
        'move_from': 'referal.status.callcenter_review.move_from'
    },
    
    # Статус "Проверка Коммерческим Директором" (ID: 20)
    20: {
        'view': 'referal.status.director_review.view',
        'edit': 'referal.status.director_review.edit',
        'move_to': 'referal.status.director_review.move_to', 
        'move_from': 'referal.status.director_review.move_from'
    },
    
    # Статус "Акцептовано к оплате" (ID: 200)
    200: {
        'view': 'referal.status.accepted.view',
        'edit': 'referal.status.accepted.edit',
        'move_to': 'referal.status.accepted.move_to',
        'move_from': 'referal.status.accepted.move_from'
    },
    
    # Статус "Оплачено" (ID: 300)
    300: {
        'view': 'referal.status.paid.view',
        'edit': 'referal.status.paid.edit',
        'move_to': 'referal.status.paid.move_to',
        'move_from': 'referal.status.paid.move_from'
    }
}

# Дополнительные статусы, которые могут быть добавлены
ADDITIONAL_STATUS_PERMISSIONS = {
    # Статус "Отклонено" (ID: 500) - если будет добавлен
    500: {
        'view': 'referal.status.rejected.view',
        'edit': 'referal.status.rejected.edit',
        'move_to': 'referal.status.rejected.move_to',
        'move_from': 'referal.status.rejected.move_from'
    }
}

# Объединяем все разрешения
ALL_STATUS_PERMISSIONS = {**STATUS_PERMISSIONS, **ADDITIONAL_STATUS_PERMISSIONS}


def can_view_status(status_id):
    """Проверяет, может ли пользователь видеть реферралов с определенным статусом"""
    from permission_utils import has_permission
    
    if status_id not in ALL_STATUS_PERMISSIONS:
        return False
    
    view_permission = ALL_STATUS_PERMISSIONS[status_id]['view']
    return has_permission(view_permission)


def can_edit_status(status_id):
    """Проверяет, может ли пользователь редактировать реферралов с определенным статусом"""
    from permission_utils import has_permission
    
    if status_id not in ALL_STATUS_PERMISSIONS:
        return False
    
    edit_permission = ALL_STATUS_PERMISSIONS[status_id]['edit']
    return has_permission(edit_permission)


def can_move_to_status(status_id):
    """Проверяет, может ли пользователь переводить реферралов В определенный статус"""
    from permission_utils import has_permission
    
    if status_id not in ALL_STATUS_PERMISSIONS:
        return False
    
    move_to_permission = ALL_STATUS_PERMISSIONS[status_id]['move_to']
    return has_permission(move_to_permission)


def can_move_from_status(status_id):
    """Проверяет, может ли пользователь переводить реферралов ИЗ определенного статуса"""
    from permission_utils import has_permission
    
    if status_id not in ALL_STATUS_PERMISSIONS:
        return False
    
    move_from_permission = ALL_STATUS_PERMISSIONS[status_id]['move_from']
    return has_permission(move_from_permission)


def can_change_status_detailed(from_status_id, to_status_id):
    """
    Детализированная проверка возможности изменения статуса с учетом 
    разрешений на перевод ИЗ и В конкретные статусы
    """
    # Проверяем, может ли пользователь переводить ИЗ исходного статуса
    if not can_move_from_status(from_status_id):
        return False
    
    # Проверяем, может ли пользователь переводить В целевой статус
    if not can_move_to_status(to_status_id):
        return False
    
    return True


def get_viewable_statuses():
    """Возвращает список ID статусов, которые пользователь может просматривать"""
    from permission_utils import get_user_permissions
    
    viewable_statuses = []
    user_perms = get_user_permissions()
    
    # Отладка: проверяем первый статус детально
    if 0 in ALL_STATUS_PERMISSIONS:
        first_perm = ALL_STATUS_PERMISSIONS[0]['view']
        has_it = first_perm in user_perms
        if not viewable_statuses:  # Логируем только один раз
            print(f"🔍 Checking status permissions | Looking for: {first_perm} | Has: {has_it} | Total perms: {len(user_perms)}")
    
    for status_id in ALL_STATUS_PERMISSIONS:
        if can_view_status(status_id):
            viewable_statuses.append(status_id)
    
    return viewable_statuses


def get_editable_statuses():
    """Возвращает список ID статусов, которые пользователь может редактировать"""
    editable_statuses = []
    
    for status_id in ALL_STATUS_PERMISSIONS:
        if can_edit_status(status_id):
            editable_statuses.append(status_id)
    
    return editable_statuses


def get_target_statuses():
    """Возвращает список ID статусов, В которые пользователь может переводить реферралов"""
    target_statuses = []
    
    for status_id in ALL_STATUS_PERMISSIONS:
        if can_move_to_status(status_id):
            target_statuses.append(status_id)
    
    return target_statuses


def get_source_statuses():
    """Возвращает список ID статусов, ИЗ которых пользователь может переводить реферралов"""
    source_statuses = []
    
    for status_id in ALL_STATUS_PERMISSIONS:
        if can_move_from_status(status_id):
            source_statuses.append(status_id)
    
    return source_statuses


def get_status_transitions():
    """
    Возвращает словарь доступных переходов между статусами для текущего пользователя
    Формат: {from_status_id: [список доступных to_status_id]}
    """
    transitions = {}
    
    # Получаем статусы, из которых можно переводить
    source_statuses = get_source_statuses()
    
    for from_status in source_statuses:
        transitions[from_status] = []
        
        # Для каждого исходного статуса находим доступные целевые статусы
        for to_status in ALL_STATUS_PERMISSIONS:
            if can_change_status_detailed(from_status, to_status):
                transitions[from_status].append(to_status)
    
    return transitions


def get_user_status_summary():
    """
    Возвращает подробную сводку о разрешениях пользователя на статусы
    Полезно для отладки и администрирования
    """
    from permission_utils import get_user_permissions
    
    permissions = get_user_permissions()
    
    summary = {
        'user_permissions': permissions,
        'viewable_statuses': get_viewable_statuses(),
        'editable_statuses': get_editable_statuses(),
        'source_statuses': get_source_statuses(),
        'target_statuses': get_target_statuses(),
        'available_transitions': get_status_transitions()
    }
    
    return summary


# Предустановленные наборы разрешений для типичных ролей
ROLE_PERMISSION_PRESETS = {
    'analytics': {
        'name': 'Аналитик',
        'description': 'Может просматривать новые заявки и переводить их на проверку',
        'permissions': [
            'referal.status.pending.view',                    # Просмотр ожидающих
            'referal.status.pending.move_from',               # Перевод из ожидающих
            'referal.status.analytics_review.view',          # Просмотр на аналитике
            'referal.status.analytics_review.edit',          # Редактирование на аналитике
            'referal.status.analytics_review.move_from',     # Перевод из аналитики
            'referal.status.callcenter_review.move_to',      # Перевод в колл-центр
            'referal.status.director_review.move_to'         # Перевод к директору
        ]
    },
    
    'call_center': {
        'name': 'Колл-центр',
        'description': 'Может работать с заявками на проверке в колл-центре',
        'permissions': [
            'referal.status.callcenter_review.view',         # Просмотр в колл-центре
            'referal.status.callcenter_review.edit',         # Редактирование в колл-центре
            'referal.status.callcenter_review.move_from',    # Перевод из колл-центра
            'referal.status.director_review.move_to',        # Перевод к директору
            'referal.status.rejected.move_to'                # Отклонение
        ]
    },
    
    'commercial_director': {
        'name': 'Коммерческий директор',
        'description': 'Может принимать решения по заявкам и переводить к оплате',
        'permissions': [
            'referal.status.director_review.view',           # Просмотр у директора
            'referal.status.director_review.edit',           # Редактирование у директора
            'referal.status.director_review.move_from',      # Перевод от директора
            'referal.status.accepted.move_to',               # Акцепт к оплате
            'referal.status.rejected.move_to'                # Отклонение
        ]
    },
    
    'payment_manager': {
        'name': 'Менеджер по платежам',
        'description': 'Может работать с принятыми к оплате заявками',
        'permissions': [
            'referal.status.accepted.view',                  # Просмотр принятых
            'referal.status.accepted.edit',                  # Редактирование принятых
            'referal.status.accepted.move_from',             # Перевод из принятых
            'referal.status.paid.move_to',                   # Перевод в оплачено
            'referal.status.paid.view'                       # Просмотр оплаченных
        ]
    },
    
    'admin': {
        'name': 'Администратор',
        'description': 'Полный доступ ко всем статусам и операциям',
        'permissions': [permission for permissions_dict in ALL_STATUS_PERMISSIONS.values() 
                       for permission in permissions_dict.values()]
    },
    
    'viewer': {
        'name': 'Наблюдатель',
        'description': 'Может только просматривать заявки во всех статусах',
        'permissions': [permissions_dict['view'] for permissions_dict in ALL_STATUS_PERMISSIONS.values()]
    }
}


def get_role_preset(role_name):
    """Возвращает предустановленный набор разрешений для роли"""
    return ROLE_PERMISSION_PRESETS.get(role_name, {})


def get_all_status_permissions():
    """Возвращает список всех возможных разрешений для статусов"""
    all_permissions = []
    for permissions_dict in ALL_STATUS_PERMISSIONS.values():
        all_permissions.extend(permissions_dict.values())
    return list(set(all_permissions))  # Убираем дубликаты


def format_permission_name(permission):
    """Форматирует название разрешения для отображения"""
    # referal.status.pending.view -> "Статус: Ожидание - Просмотр"
    parts = permission.split('.')
    if len(parts) >= 4 and parts[0] == 'referal' and parts[1] == 'status':
        status_name = parts[2]
        action = parts[3]
        
        status_names = {
            'pending': 'Ожидание проверки',
            'analytics_review': 'Проверка аналитикой',
            'callcenter_review': 'Проверка колл-центром',
            'director_review': 'Проверка директором',
            'accepted': 'Принято к оплате',
            'paid': 'Оплачено',
            'rejected': 'Отклонено'
        }
        
        action_names = {
            'view': 'Просмотр',
            'edit': 'Редактирование',
            'move_to': 'Перевод В статус',
            'move_from': 'Перевод ИЗ статуса'
        }
        
        status_display = status_names.get(status_name, status_name)
        action_display = action_names.get(action, action)
        
        return f"Статус: {status_display} - {action_display}"
    
    return permission