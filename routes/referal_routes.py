"""Маршруты для работы с рефералами"""

import random
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from datetime import datetime
import re
from models import *
from .auth_routes import get_current_user
from services import referal_service, notification_service, data_sync_service, withdrawal_service
import utils
import os

referal_bp = Blueprint('referal', __name__)


@referal_bp.route('/', methods=['GET'])
def profile():
    print("Profile route accessed")
    user = get_current_user()
    print(f"User after get_current_user: {user}")
    
    if not user:
        print("No user found, redirecting to referal profile")
        return redirect(url_for('referal.profile'))
    
    if user.role == 'admin' or user.role == 'manager' or user.role == 'call-center':
        """Перенаправление на административную панель для администраторов."""
        return redirect(url_for('admin.admin_panel'))
    
    referal_service.update_deal_info(user)
    
    # Получаем общее количество рефералов пользователя (без фильтров)
    total_user_referals = Referal.query.filter_by(user_id=user.id).count()
    
    # Получаем параметры фильтрации, пагинации и сортировки
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 5, type=int)
    status_filter = request.args.get('status', '')
    name_filter = request.args.get('name', '')
    phone_filter = request.args.get('phone', '')
    contract_filter = request.args.get('contract', '')
    contact_id_filter = request.args.get('contact_id', '')
    
    # Получаем множественную сортировку как строку "field1:asc,field2:desc"
    sort_param = request.args.get('sort', '')
    
    # Парсим сортировку
    sort_fields = []
    if sort_param:
        for sort_item in sort_param.split(','):
            if ':' in sort_item:
                field, order = sort_item.split(':')
                sort_fields.append({'field': field, 'order': order})
    
    # Базовый запрос с единократным присоединением ReferalData
    query = Referal.query.filter_by(user_id=user.id)
    
    # Определяем, нужно ли присоединять ReferalData
    needs_referal_data_join = (name_filter or phone_filter or contract_filter)
    
    # Проверяем, есть ли сортировка по полям ReferalData
    if sort_fields:
        for sort_field in sort_fields:
            if sort_field['field'] in ['name', 'phone', 'contract']:
                needs_referal_data_join = True
                break
    
    if needs_referal_data_join:
        query = query.join(ReferalData)
    
    selected_statuses = []
    status_ids = []
    if status_filter:
        try:
            statuses = status_filter.split(',')
            for status in statuses:
                if status.isdigit():
                    # Если статус - это число, добавляем его в фильтр
                    status_ids.append(int(status))
                else:
                    flash(f'Неверный формат статуса: {status}', 'warning')
            query = query.filter(Referal.status_id.in_(status_ids))
            selected_statuses = status_ids
        except ValueError:
            # Если в параметре что-то не то, игнорируем его
            flash('Получен неверный формат статусов в фильтре.', 'warning')
            pass 
    else:
        # СТАНДАРТНОЕ ПОВЕДЕНИЕ: Показываем все, кроме "Оплачено" (300)
        # Убедитесь, что у вас есть эти ID в модели Status
        EXCLUDED_STATUSES = [300] 
        query = query.filter(Referal.status_id.notin_(EXCLUDED_STATUSES))
        selected_statuses = [s.id for s in Status.query.filter(Status.id.notin_(EXCLUDED_STATUSES)).all()]


    
    if name_filter:
        query = query.filter(ReferalData.full_name.ilike(f'%{name_filter}%'))
    
    if phone_filter:
        query = query.filter(ReferalData.phone_number.ilike(f'%{phone_filter}%'))
    
    if contract_filter:
        query = query.filter(ReferalData.contract_number.ilike(f'%{contract_filter}%'))
    
    if contact_id_filter:
        query = query.filter(Referal.contact_id.ilike(f'%{contact_id_filter}%'))
    
    # Применяем множественную сортировку
    if sort_fields:
        order_by_clauses = []
        for sort_field in sort_fields:
            field = sort_field['field']
            order = sort_field['order']
            
            if field == 'name':
                clause = ReferalData.full_name.desc() if order == 'desc' else ReferalData.full_name.asc()
            elif field == 'phone':
                clause = ReferalData.phone_number.desc() if order == 'desc' else ReferalData.phone_number.asc()
            elif field == 'contract':
                clause = ReferalData.contract_number.desc() if order == 'desc' else ReferalData.contract_number.asc()
            elif field == 'status':
                clause = Referal.status_id.desc() if order == 'desc' else Referal.status_id.asc()
            elif field == 'amount':
                clause = Referal.withdrawal_amount.desc() if order == 'desc' else Referal.withdrawal_amount.asc()
            else:
                continue
            
            order_by_clauses.append(clause)
        
        if order_by_clauses:
            query = query.order_by(*order_by_clauses)
    else:
        # Сортировка по умолчанию
        query = query.order_by(Referal.id.desc())
    
    # Пагинация
    pagination = query.paginate(
        page=page, 
        per_page=per_page, 
        error_out=False
    )
    referals = pagination.items
    
    # Обогащаем каждый реферал данными MacroContact
    for referal in referals:
        if referal.contact_id:
            referal.macro_contacts = MacroContact.query.filter_by(contacts_id=referal.contact_id).all()
            referal.macro_contact = referal.macro_contacts[0] if referal.macro_contacts else None
        else:
            referal.macro_contacts = []
            referal.macro_contact = None
    
    print(f"Found {len(referals)} referals for user {user.login}")


    return render_template('profile.html', 
                          current_user=user,
                          current_balance=user.current_balance,
                          pending_withdrawal=user.pending_withdrawal,
                          total_withdrawal=user.total_withdrawal,
                          referals=referals,
                          pagination=pagination,
                          statuses=Status.query.all(),
                          total_user_referals=total_user_referals,
                          current_filters={
                              'status': status_filter,
                              'name': name_filter,
                              'phone': phone_filter,
                              'contract': contract_filter,
                              'contact_id': contact_id_filter,
                              'per_page': per_page
                          },
                          selected_statuses=selected_statuses,
                          current_sort=sort_param,
                          sort_fields=sort_fields if sort_fields else [])


@referal_bp.route('/add', methods=['POST'])
def add_referal():
    """Добавление нового реферала через модальную форму"""
    
    managers = ["""Mamatov A'zam""",
                """Buaxunov Baxtiyor""",
                """Magovskiy Aleksandr""",
                """RU Saytxalilov Alisher""",
                """Komilov Sunnatilla""",
                """Dayanova Aida""",
                """Mirvosikov Mirazim""",
                """Suleymanov Artur""",
                """Krubayev Enver""",
                """Xolidova Asal""",
                """Raximberdiyev Raxmonberdi""",
                """Kadirov Timur""",
                """Kaxarov Sherzod Yuldashevich""",
                """Mirzaolimov Nurmuhammad""",
                """Atamatov Davron""",
                """Nikiforova Kseniya""",
                """Yulchiyev Umidjon""",
                """Zairov Odil Kamildjanovich""",
                """Yulchiyev Ramazon""",
                """Rustamov Azizbek""",
                """Miraxmad Mirboboev""",
                """Djumabayev Akbar""",
                """Lyovkin Dmitriy""",
                """Abdukhalikova Jasmina""",
                """Bekov Abbosbek Alisher ogli""",
                """Mukhsinov Sukhrob""",
                """Parpiyeva Nasibaxon"""]
    
    
    manager = managers[random.randint(0, len(managers) - 1)]
    
    
    user = get_current_user()
    if not user:
        flash('Необходимо войти в систему', 'error')
        return redirect(url_for('auth.login'))
    
    try:
        # Получаем данные из формы
        full_name = request.form.get('full_name', '').strip()
        phone_number = request.form.get('phone_number', '').strip()
        
        # Валидация обязательных полей
        if not full_name:
            flash('Имя реферала обязательно для заполнения', 'error')
            return redirect(url_for('referal.profile'))
        
        if not phone_number:
            flash('Телефон реферала обязателен для заполнения', 'error')
            return redirect(url_for('referal.profile'))
        
        # Форматируем номер телефона
        formatted_phone = utils.format_phone_number(phone_number)
        if not formatted_phone:
            flash('Неверный формат номера телефона', 'error')
            return redirect(url_for('referal.profile'))
        
        # Проверяем, не существует ли уже реферал с таким телефоном 
        existing_referal = Referal.query.join(ReferalData).filter(
            ReferalData.phone_number == formatted_phone
        ).first()
        if existing_referal:
            flash(f'Реферал с номером {formatted_phone} уже добавлен', 'error')
            return redirect(url_for('referal.profile'))
        
                # Проверяем, не существует ли уже реферал с таким телефоном 
        existing_referal = Referal.query.join(ReferalData).filter(
            ReferalData.full_name == full_name
        ).first()
        if existing_referal:
            flash(f'Реферал с именем {full_name} уже добавлен', 'error')
            return redirect(url_for('referal.profile'))
        
        # Пытаемся найти соответствующий MacroContact
        macro_contact = MacroContact.query.filter_by(phone_number=formatted_phone).first()
        if macro_contact:
            new_referal.contact_id = macro_contact.contacts_id
            print(f"Found matching MacroContact for {formatted_phone}: {macro_contact.contacts_id}")
            flash('Данный человек не может являться рефералом', 'error')
            return redirect(url_for('referal.profile'))

        # Создаем новый реферал
        print(user.id)
        new_referal = Referal(user_id=user.id)
        db.session.add(new_referal)
        db.session.commit()
        db.session.flush()  # Получаем ID реферала
        
        # Создаем данные реферала
        referal_data = ReferalData(
            referal_id=new_referal.id,
            full_name=full_name,
            phone_number=formatted_phone
        )

        passport_number = request.form.get('passport_number', '').strip()
        passport_date = request.form.get('passport_date', '').strip()
        passport_giver = request.form.get('passport_giver', '').strip()

        
        if passport_number and passport_number != '':
            referal_data.passport_number = passport_number
        if passport_date and passport_date != '':
            referal_data.passport_date = datetime.strptime(passport_date, '%Y-%m-%d')
        if passport_giver and passport_giver != '':
            referal_data.passport_giver = passport_giver

        
        db.session.add(referal_data)
        db.session.commit()
        db.session.flush()
        flash(f'Реферал {full_name} успешно добавлен', 'success')
        utils.send_email(
            os.getenv('CALL_CENTER_MANAGER_EMAIL'),
            subject='Назначение встречи для реферала',
            body=f'Пользователь {user.user_data.full_name} добавил нового реферала: {full_name} ({formatted_phone}). Создайте встречу реферала с менеджером: {manager} для дальнейшего взаимодействия с клиентом.'
        )
        print(f"Successfully added referal: {full_name} ({formatted_phone}) for user {user.login}")
        
    except Exception as e:
        db.session.rollback()
        print(f"Error adding referal: {e}")
        flash('Произошла ошибка при добавлении реферала', 'error')
    
    return redirect(url_for('referal.profile'))


@referal_bp.route('/update_deal_info', methods=['POST'])
def update_deal_info_route():
    """Маршрут для обновления информации о сделке."""
    user = get_current_user()
    if not user:
        flash('User not found', 'error')
        return redirect(url_for('referal.profile'))
        
    try:
        referal_service.update_deal_info(user)
        flash('Информация о сделке обновлена', 'success')
    except Exception as e:
        flash(f'Ошибка при обновлении информации о сделке: {e}', 'error')
    return redirect(url_for('referal.profile'))


@referal_bp.route('/request_withdrawal/<int:referal_id>', methods=['POST'])
def request_withdrawal(referal_id):
    """Маршрут для запроса на вывод средств."""
    user = get_current_user()
    try:
        withdrawal_service.request_withdrawal(referal_id, user=user)
    except Exception as e:
        flash(f'Ошибка при запросе на вывод средств: {e}', 'error')
    return redirect(url_for('referal.profile'))


@referal_bp.route('/update_referal_documents/<int:referal_id>', methods=['POST'])
def update_referal_documents(referal_id):
    """Маршрут для обновления документов реферала."""
    user = get_current_user()
    if not user:
        flash('Пожалуйста, войдите в систему', 'error')
        return redirect(url_for('referal.profile'))
    
    referal = Referal.query.filter_by(id=referal_id, user_id=user.id).first()
    if not referal:
        flash('Реферал не найден', 'error')
        return redirect(url_for('referal.profile'))
    
    try:
        # Если у реферала нет данных, создаем их
        if not referal.referal_data:
            referal.referal_data = ReferalData(referal_id=referal_id)
            db.session.add(referal.referal_data)
            db.session.flush()
        
        # Получаем данные из формы
        full_name = request.form.get('full_name', '').strip()
        phone_number = request.form.get('phone_number', '').strip()
        passport_number = request.form.get('passport_number', '').strip()
        passport_giver = request.form.get('passport_giver', '').strip()
        passport_adress = request.form.get('passport_adress', '').strip()
        mail_adress = request.form.get('mail_adress', '').strip()
        passport_date_str = request.form.get('passport_date', '').strip()
        
        # Обновляем поля реферала
        referal.referal_data.full_name = full_name if full_name else None
        referal.referal_data.phone_number = phone_number if phone_number else None
        referal.referal_data.passport_number = passport_number if passport_number else None
        referal.referal_data.passport_giver = passport_giver if passport_giver else None
        referal.referal_data.passport_adress = passport_adress if passport_adress else None
        referal.referal_data.mail_adress = mail_adress if mail_adress else None
        
        # Обработка passport_date с преобразованием строки в datetime
        if passport_date_str:
            try:
                passport_date = datetime.strptime(passport_date_str, '%Y-%m-%d')
                referal.referal_data.passport_date = passport_date
            except ValueError:
                try:
                    passport_date = datetime.strptime(passport_date_str, '%d.%m.%Y')
                    referal.referal_data.passport_date = passport_date
                except ValueError:
                    try:
                        passport_date = datetime.strptime(passport_date_str, '%d/%m/%Y')
                        referal.referal_data.passport_date = passport_date
                    except ValueError:
                        flash('Неверный формат даты выдачи паспорта. Используйте формат ДД.ММ.ГГГГ', 'error')
                        return redirect(url_for('referal.profile'))
        else:
            referal.referal_data.passport_date = None
        
        # Валидация ФИО
        if full_name and not re.match(r'^[A-Za-z`‘]+(?: [A-Za-z`‘]+){2,}$', full_name) or '  ' in full_name:
            flash('Неверно введено ФИО. Используйте латиницу и минимум 3 слова', 'error')
            return redirect(url_for('referal.profile'))
        
        # Валидация телефона
        if phone_number and not re.match(r'^\+998 \d{2} \d{3} \d{2} \d{2}$', phone_number):
            flash('Неверный формат телефона. Используйте формат +998 XX XXX XX XX', 'error')
            return redirect(url_for('referal.profile'))
        
        db.session.commit()
        flash('Данные реферала успешно обновлены', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при обновлении данных: {e}', 'error')
    
    return redirect(url_for('referal.profile'))


@referal_bp.route('/referal_profile/<int:referal_id>', methods=['GET'])
def referal_profile(referal_id):
    """Маршрут для отображения профиля реферала."""
    user = get_current_user()
    if not user:
        flash('Пожалуйста, войдите в систему', 'error')
        return redirect(url_for('referal.profile'))
    
    referal = Referal.query.filter_by(id=referal_id, user_id=user.id).first()
    if not referal:
        flash('Реферал не найден', 'error')
        return redirect(url_for('referal.profile'))
    
    return render_template('referal_profile.html', 
                          current_user=user,
                          referal=referal)


@referal_bp.route('/update_macro_data')
def update_macro_data():
    """Force update macro data including email fields"""
    try:
        # Используем правильную функцию
        result = data_sync_service.fetch_and_process_contacts(days_back=180)
        
        if result and result.get('success'):
            return jsonify({
                'success': True,
                'message': f"Данные обновлены. Обработано контактов: {result.get('processed_count', 0)}"
            })
        else:
            return jsonify({
                'success': False,
                'message': f"Ошибка обновления: {result.get('error', 'Unknown error') if result else 'No result returned'}"
            })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f"Ошибка: {str(e)}"
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f"Ошибка: {str(e)}"
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f"Ошибка: {str(e)}"
        })

