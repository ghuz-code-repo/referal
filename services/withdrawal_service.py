"""Сервис для работы с выводом средств"""

import os
from models import *
import utils


def request_withdrawal(referal_id, user):
    """Обрабатывает запрос на вывод средств от пользователя."""
    user_full_name = user.user_data.full_name
    referal = Referal.query.filter_by(id=referal_id).first()
    if not referal.balance_pending_withdrawal and referal.withdrawal_amount > 0:
        user.pending_withdrawal += referal.withdrawal_amount
        user.current_balance -= referal.withdrawal_amount
        referal.status_id = 1
        referal.status_name = Status.query.filter_by(id=1).first().name
        referal.balance_pending_withdrawal = True
        db.session.commit()
        
        recipient_email = os.getenv('MAIN_ADMIN_EMAIL')
        subject = "Запрос на вывод средств по реферальной программе"
        body = f"Сотрудник {user_full_name} сделал запрос на вывод средств в размере {referal.withdrawal_amount} за счет реферала {referal.referal_data.full_name}"
        return utils.send_email(recipient_email, subject, body)

