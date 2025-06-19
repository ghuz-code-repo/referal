from .referal_service import *
from .data_sync_service import *
from .notification_service import *
from .withdrawal_service import *

# Экспортируем все функции для обратной совместимости
__all__ = [
    'create_new_referal', 'update_deal_and_balance', 'update_deal_info',
    'fetch_data_from_mysql', 'sync_referals_with_macro_contacts',
    'create_macro_task', 'request_withdrawal'
]
