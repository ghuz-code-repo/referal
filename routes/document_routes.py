"""Маршруты для работы с документами и актами"""

import math
from flask import Blueprint, request, redirect, url_for, flash, send_file, current_app
from datetime import datetime, date
import os
from decimal import Decimal, ROUND_HALF_UP
from .auth_routes import get_current_user
from models import *
from macro_data import get_property_details
import utils
from utils import month_name_genitive
from docx import Document
import io
import re

document_bp = Blueprint('document', __name__)


@document_bp.route('/get_agreement/<int:user_id>', methods=['GET'])
def get_agreement(user_id):
    """Генерация соглашения для пользователя"""
    try:
        # Получаем данные пользователя из базы
        user = User.query.get_or_404(user_id)
        
        # Автоматически синхронизируем данные пользователя из auth-service
        from utils import sync_user_data_from_auth_service
        from flask import request
        sync_user_data_from_auth_service(user, force_sync=True, headers=request.headers)
        
        user_data = user.user_data  # Получаем связанные данные пользователя
        
        if not user_data:
            flash('Не найдены данные пользователя', 'error')
            return redirect(url_for('referal.profile'))

        # Определяем путь к шаблону
        template_path = os.path.join(current_app.root_path, 'documents', f"{os.getenv('AGREEMENT_DOC_NAME')}.docx")

        
        # Загружаем шаблон
        doc = Document(template_path)
        
        # Подготавливаем данные для замены (используем данные из UserData)
        current_date = datetime.now()
        formatted_date = f"{current_date.day} {month_name_genitive(current_date.month)} {current_date.year}"
        
        replacements = {
            #Дата в шапке (возможно не будет использоваться)
            'day': current_date.day,
            'month': month_name_genitive(current_date.month),
            'year': current_date.year,
            
            #Данные пользователя 1я страница
            'full_name': user_data.full_name or '',
            'passport_number': user_data.passport_number or '',
            'passport_giver': user_data.passport_giver or '',
            'passport_date': user_data.passport_date.strftime('%d.%m.%Y') if user_data.passport_date else '',
            'passport_address': user_data.passport_adress or '',
            
            #Подвал (паспорт адрес и имя тоже юзаются)
            'pinfl': user_data.pinfl.replace(' ','') or '',
            'trans_schet': user_data.trans_schet.replace(' ','') or '',
            'card_number': user_data.card_number.replace(' ','') or '',
            'bank': user_data.bank_name or '',
            'mfo': user_data.mfo or '',
            'phone': user_data.phone.replace(' ','') or '',
            'e_mail': user_data.e_mail or '',

        }

        required_fields = {
            'full_name': 'Полное имя пользователя',
            'passport_number': 'Паспортный номер',
            'passport_giver': 'Кем выдан паспорт',
            'passport_date': 'Дата выдачи паспорта',
            'passport_address': 'Прописка по паспорту',
            'pinfl': 'ПИНФЛ',
            'trans_schet': 'Расчетный счет',
            'card_number': 'Номер карты',
            'bank': 'Название банка',
            'mfo': 'МФО Банка',
            'phone': 'Телефон',
        }

        missing_fields = []
        for field_key, field_name in required_fields.items():
            value = replacements.get(field_key, '')
            if not value or str(value).strip() == '' or str(value).strip() == '0':
                missing_fields.append(field_name)
        
        if missing_fields:
            error_message = f"Невозможно сгенерировать акт. Отсутствуют обязательные поля: {', '.join(missing_fields)}"
            flash(error_message, 'error')
            return redirect(url_for('referal.profile'))


        # Заменяем плейсхолдеры в документе
        _replace_text_in_document(doc, replacements)

        # Сохраняем документ в память
        file_stream = io.BytesIO()
        doc.save(file_stream)
        file_stream.seek(0)

        # Генерируем имя файла
        safe_name = re.sub(r'[^\w\s-]', '', user_data.full_name or 'user').strip()
        filename = f"agreement_{safe_name}_{current_date.strftime('%Y%m%d')}.docx"

        return send_file(
            file_stream,
            as_attachment=True,
            download_name=filename,
            mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        )

    except Exception as e:
        current_app.logger.error(f"Error generating agreement: {str(e)}")
        flash('Ошибка при генерации соглашения', 'error')
        return redirect(url_for('referal.profile'))


@document_bp.route('/get_referal_act/<int:referal_id>', methods=['GET'])
@document_bp.route('/get_deal_act/<int:referal_deal_id>', methods=['GET'])
def get_referal_act(referal_id=None, referal_deal_id=None):
    """Генерация акта для реферала или конкретного договора"""
    current_user = get_current_user()
    if not current_user:
        flash('Пользователь не найден', 'error')
        return redirect(url_for('referal.profile'))
    
    # Проверяем права админа
    from permission_utils import has_permission
    is_admin = has_permission('referal.admin.panel')
    
    try:
        # Определяем какой endpoint вызван
        if referal_deal_id:
            # Новая логика: генерация для конкретного договора
            referal_deal = ReferalDeal.query.get_or_404(referal_deal_id)
            referal = referal_deal.referal
            deal = referal_deal.deal
            
            # Проверяем доступ: либо владелец, либо админ
            if not is_admin and referal.user_id != current_user.id:
                flash('Доступ запрещен', 'error')
                return redirect(url_for('referal.profile'))
            
            user = referal.user
            
            # ПРИНУДИТЕЛЬНО синхронизируем данные пользователя из auth-service
            from utils import sync_user_data_from_auth_service
            from flask import request
            sync_user_data_from_auth_service(user, force_sync=True, headers=request.headers)
            
            user_data = user.user_data if user else None
            referal_data = referal.referal_data
            
            if not user or not user_data:
                flash('Не найдены данные пользователя для данного реферала', 'error')
                return redirect(url_for('referal.profile'))
            
            # Проверяем наличие паспортных данных реферера (из документа паспорта)
            if not user_data.full_name or not user_data.passport_number:
                flash('❌ Отсутствуют паспортные данные реферера. Пожалуйста, заполните ФИО и номер паспорта в профиле перед генерацией акта.', 'error')
                return redirect(url_for('referal.profile'))
                
            if not referal_data:
                flash('Не найдены данные реферала', 'error')
                return redirect(url_for('referal.profile'))
            
            if not deal:
                flash('Договор не найден', 'error')
                return redirect(url_for('referal.profile'))
            
            real_deal = deal
            withdrawal_amount = referal_deal.withdrawal_amount
            
            # Проверяем что withdrawal_amount не None
            if withdrawal_amount is None:
                flash('Сумма выплаты не рассчитана для данного договора. Обратитесь к администратору.', 'error')
                return redirect(url_for('referal.profile'))
            
        else:
            # Старая логика: генерация для первого найденного договора (для обратной совместимости)
            referal = Referal.query.get_or_404(referal_id)
            
            # Проверяем доступ: либо владелец, либо админ
            if not is_admin and referal.user_id != current_user.id:
                flash('Доступ запрещен', 'error')
                return redirect(url_for('referal.profile'))
            
            user = referal.user
            
            # ПРИНУДИТЕЛЬНО синхронизируем данные пользователя из auth-service
            from utils import sync_user_data_from_auth_service
            from flask import request
            sync_user_data_from_auth_service(user, force_sync=True, headers=request.headers)
            
            user_data = user.user_data if user else None
            referal_data = referal.referal_data
            
            if not user or not user_data:
                flash('Не найдены данные пользователя для данного реферала', 'error')
                return redirect(url_for('referal.profile'))
                
            if not referal_data:
                flash('Не найдены данные реферала', 'error')
                return redirect(url_for('referal.profile'))

            deals = MacroDeal.query.filter_by(contacts_buy_id=referal.contact_id)
            if not deals:
                flash('Deal not found', 'error')
                return redirect(url_for('referal.profile'))
        
            # Находим подходящую сделку (приоритет - проведенная, иначе любая с валидным платежом)
            real_deal = None
            for deal in deals:
                if deal.deal_status_name == "Сделка проведена":
                    real_deal = deal
                    break
            
            # Если нет проведенной сделки, берем первую с валидным платежом
            if not real_deal:
                for deal in deals:
                    if deal.has_valid_payment():
                        real_deal = deal
                        break
            
            # Если все еще нет сделки, берем первую
            if not real_deal:
                real_deal = deals[0]
            
            withdrawal_amount = referal.withdrawal_amount
            
            # Проверяем что withdrawal_amount не None
            if withdrawal_amount is None:
                flash('Сумма выплаты не рассчитана для данного реферала. Обратитесь к администратору.', 'error')
                return redirect(url_for('referal.profile'))
        
        # Определяем путь к шаблону
        template_path = os.path.join(current_app.root_path, 'documents', f"{os.getenv('ACT_DOC_NAME')}.docx")

        # Проверяем тип agreement_date и конвертируем если нужно
        # Теперь используем данные из локальной базы (MacroDeal)
        agreement_date_raw = real_deal.agreement_date
        
        # Проверяем что дата договора заполнена
        if agreement_date_raw is None:
            flash('❌ Дата договора не заполнена. Невозможно сгенерировать акт без даты договора.', 'error')
            return redirect(url_for('referal.profile'))
        
        if isinstance(agreement_date_raw, str):
            if agreement_date_raw:
                # Пытаемся распарсить строку в datetime (пробуем разные форматы)
                try:
                    # Пробуем ISO формат
                    agreement_date = datetime.strptime(agreement_date_raw, '%Y-%m-%d').date()
                except ValueError:
                    try:
                        # Пробуем формат с временем
                        agreement_date = datetime.strptime(agreement_date_raw, '%Y-%m-%d %H:%M:%S').date()
                    except ValueError:
                        # Если не получилось, показываем ошибку
                        flash(f'❌ Неверный формат даты договора: {agreement_date_raw}. Обратитесь к администратору.', 'error')
                        return redirect(url_for('referal.profile'))
            else:
                # Пустая строка
                flash('❌ Дата договора пустая. Невозможно сгенерировать акт без даты договора.', 'error')
                return redirect(url_for('referal.profile'))
        elif hasattr(agreement_date_raw, 'date'):
            # Это datetime/pandas Timestamp объект
            agreement_date = agreement_date_raw.date()
        elif isinstance(agreement_date_raw, date):
            # Это уже date объект
            agreement_date = agreement_date_raw
        else:
            # Неизвестный тип
            flash(f'❌ Неизвестный тип даты договора: {type(agreement_date_raw)}. Обратитесь к администратору.', 'error')
            return redirect(url_for('referal.profile'))
            
        print(f"Agreement date: {agreement_date}")
        # Загружаем шаблон
        doc = Document(template_path)
        # Подготавливаем данные для замены (используем данные из UserData и ReferalData)
        current_date = datetime.now()
        print(f"Current date: {month_name_genitive(current_date.month)}")
        print(f"Current date: {month_name_genitive(int(agreement_date.month))}")
        # Форматируем дату паспорта (может быть date, datetime или str)
        referal_passport_date_str = ''
        if referal_data.passport_date:
            if isinstance(referal_data.passport_date, str):
                referal_passport_date_str = referal_data.passport_date
            elif hasattr(referal_data.passport_date, 'strftime'):
                referal_passport_date_str = referal_data.passport_date.strftime('%d.%m.%Y')
        
        # Форматируем дату для замены - используем дату договора из MacroDeal
        replacements = {
            'day': agreement_date.day,
            'month': month_name_genitive(int(agreement_date.month)),
            'year': agreement_date.year,
            
            'full_name': (user_data.full_name or '').upper(),
            'referal_name': (referal_data.full_name or '').upper(),
            'referal_passport_number': referal_data.passport_number or '',
            'referal_passport_date': referal_passport_date_str,
            'referal_passport_giver': referal_data.passport_giver or '',
            'contract_number': real_deal.agreement_number or '',  # Берём из MacroDeal, а не из ReferalData
            
            'contract_day': agreement_date.day,
            'contract_month': month_name_genitive(int(agreement_date.month)),
            'contract_year': agreement_date.year,
            
            # Используем данные из локальной базы (MacroDeal)
            'project_name': real_deal.project_name or '',
            'house_address': real_deal.house_address or '',
            'house_number': real_deal.house_number or '',
            'appartment_number': real_deal.apartment_number or '',
            'apartment_number': real_deal.apartment_number or '',  # Оба варианта написания для совместимости
            'rooms': real_deal.rooms or '',
            'entrance': real_deal.entrance or '',
            'floor': real_deal.floor or '',
            'max_floor': real_deal.max_floor or '',
            'appartment_area': real_deal.deal_metr,
            'contract_price': '{:,}'.format(int(float(real_deal.agreement_price or 0))).replace(',', ' ') if real_deal.agreement_price else '',
            'withdrawal_amount': '{:,}'.format(
                int(round((withdrawal_amount or 0)/(1-float(os.getenv('NDS_PERCENT'))/100) + float(os.getenv('NDS_ROUNDING_ADJUSTMENT', '1'))))
            ).replace(',', ' '),
            
            'referer_name': (user_data.full_name or '').upper(),
            'passport_address': user_data.passport_adress or '',
            'pinfl': user_data.pinfl.replace(' ','') or '',
            'referer_phone': user_data.phone.replace(' ','') or '',
            'referer_email': user_data.e_mail or '',
        }

        # Проверяем наличие всех обязательных полей с указанием источника данных
        required_fields = {
            # Данные реферера (из профиля пользователя)
            'full_name': ('Полное имя реферера (ФИО)', 'Профиль пользователя'),
            'referer_name': ('Имя реферера', 'Профиль пользователя'),
            'passport_address': ('Адрес прописки реферера', 'Профиль пользователя → Паспорт'),
            'pinfl': ('ПИНФЛ реферера', 'Профиль пользователя → Документ ПИНФЛ'),
            'referer_phone': ('Телефон реферера', 'Профиль пользователя'),
            
            # Данные реферала (клиента)
            'referal_name': ('Полное имя реферала (клиента)', 'Данные реферала'),
            'referal_passport_number': ('Номер паспорта реферала', 'Данные реферала → Паспорт'),
            'referal_passport_date': ('Дата выдачи паспорта реферала', 'Данные реферала → Паспорт'),
            'referal_passport_giver': ('Орган выдачи паспорта реферала', 'Данные реферала → Паспорт'),
            
            # Данные сделки (из MacroCRM)
            'contract_number': ('Номер договора', 'Данные сделки из MacroCRM'),
            'project_name': ('Название проекта (ЖК)', 'Данные недвижимости из MacroCRM'),
            'house_address': ('Адрес дома', 'Данные недвижимости из MacroCRM'),
            'house_number': ('Номер дома', 'Данные недвижимости из MacroCRM'),
            'appartment_number': ('Номер квартиры', 'Данные недвижимости из MacroCRM'),
            'appartment_area': ('Площадь квартиры', 'Данные недвижимости из MacroCRM'),
            'withdrawal_amount': ('Сумма к выводу', 'Расчет выплаты'),
        }
        
        missing_fields = []
        for field_key, (field_name, source) in required_fields.items():
            value = replacements.get(field_key, '')
            if not value or str(value).strip() == '' or str(value).strip() == '0':
                missing_fields.append(f"• {field_name} (источник: {source})")
        
        if missing_fields:
            error_message = "❌ Невозможно сгенерировать акт. Отсутствуют обязательные данные:\n" + '\n'.join(missing_fields)
            error_message += "\n\nПожалуйста, заполните недостающие данные в профиле или обратитесь к администратору для проверки данных сделки."
            flash(error_message, 'error')
            return redirect(url_for('referal.profile'))

        # Заменяем плейсхолдеры в документе
        _replace_text_in_document(doc, replacements)

        # Сохраняем документ в память
        file_stream = io.BytesIO()
        doc.save(file_stream)
        file_stream.seek(0)

        # Генерируем имя файла
        safe_referal_name = re.sub(r'[^\w\s-]', '', referal_data.full_name or 'referal').strip()
        filename = f"act_{safe_referal_name}_{current_date.strftime('%Y%m%d')}.docx"

        return send_file(
            file_stream,
            as_attachment=True,
            download_name=filename,
            mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        )

    except Exception as e:
        current_app.logger.error(f"Error generating referal act: {str(e)}")
        flash(f'Ошибка при генерации акта {e}', 'error')
        return redirect(url_for('referal.profile'))


def _replace_text_in_document(doc, replacements):
    """Заменяет плейсхолдеры в документе"""
    # Замена в параграфах
    for paragraph in doc.paragraphs:
        for placeholder, replacement in replacements.items():
            if placeholder in paragraph.text:
                paragraph.text = paragraph.text.replace(f'{{{placeholder}}}', str(replacement))
    
    # Замена в таблицах
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for placeholder, replacement in replacements.items():
                    if placeholder in cell.text:
                        cell.text = cell.text.replace(f'{{{placeholder}}}', str(replacement))
    
    # Замена в колонтитулах
    for section in doc.sections:
        # Верхний колонтитул
        if section.header:
            for paragraph in section.header.paragraphs:
                for placeholder, replacement in replacements.items():
                    if placeholder in paragraph.text:
                        paragraph.text = paragraph.text.replace(f'{{{placeholder}}}', str(replacement))
        
        # Нижний колонтитул
        if section.footer:
            for paragraph in section.footer.paragraphs:
                for placeholder, replacement in replacements.items():
                    if placeholder in paragraph.text:
                        paragraph.text = paragraph.text.replace(f'{{{placeholder}}}', str(replacement))
            if placeholder in paragraph.text:
                paragraph.text = paragraph.text.replace(f'{{{placeholder}}}', str(replacement))
    
    # Замена в таблицах
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for placeholder, replacement in replacements.items():
                    if placeholder in cell.text:
                        cell.text = cell.text.replace(f'{{{placeholder}}}', str(replacement))
    
    # Замена в колонтитулах
    for section in doc.sections:
        # Верхний колонтитул
        if section.header:
            for paragraph in section.header.paragraphs:
                for placeholder, replacement in replacements.items():
                    if placeholder in paragraph.text:
                        paragraph.text = paragraph.text.replace(f'{{{placeholder}}}', str(replacement))
        
        # Нижний колонтитул
        if section.footer:
            for paragraph in section.footer.paragraphs:
                for placeholder, replacement in replacements.items():
                    if placeholder in paragraph.text:
                        paragraph.text = paragraph.text.replace(f'{{{placeholder}}}', str(replacement))