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
@referal_bp.route('/list', methods=['GET']) 
def referal_list():
    """Главная страница рефералки - список рефералов пользователя"""
    user = get_current_user()
    
    if not user:
        from flask import render_template_string
        return render_template_string("""
        <html>
        <body>
        <h1>Authentication Required</h1>
        <p>Please log in to access the referal system.</p>
        <a href="/login">Login</a>
        </body>
        </html>
        """), 401
    
    if user.role == 'admin' or user.role == 'manager' or user.role == 'call-center':
        """Перенаправление на административную панель для администраторов."""
        return redirect(url_for('admin.admin_panel'))
    
    # Автоматически синхронизируем данные пользователя из auth-service
    from utils import sync_user_data_from_auth_service
    sync_user_data_from_auth_service(user, force_sync=True, headers=request.headers)
    
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
    """Добавление нового реферала с проверкой истории CRM и привязкой договоров"""
    
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
        
        # Проверяем, не существует ли уже реферал с таким именем 
        existing_referal_by_name = Referal.query.join(ReferalData).filter(
            ReferalData.full_name == full_name
        ).first()
        if existing_referal_by_name:
            flash(f'Реферал с именем {full_name} уже добавлен', 'error')
            return redirect(url_for('referal.profile'))
        
        # НОВАЯ ЛОГИКА: Проверяем историю взаимодействий с CRM за последние 45 дней
        days_threshold = int(os.getenv('REFERAL_DAYS_THRESHOLD', 45))
        check_result = referal_service.check_contact_history_before_adding(
            formatted_phone, full_name, days_threshold
        )
        
        if not check_result['can_add']:
            # ЗАПРЕЩЕНО добавление
            flash(f'❌ Данный клиент не может быть добавлен как реферал: {check_result["reason"]}', 'error')
            return redirect(url_for('referal.profile'))
        
        # Создаем реферала с валидацией (использует новую логику с created_at)
        new_referal, error = referal_service.create_new_referal_with_validation(
            full_name, formatted_phone, user, days_threshold
        )
        
        if error:
            flash(f'Ошибка при создании реферала: {error}', 'error')
            return redirect(url_for('referal.profile'))
        
        # Сохраняем реферала
        db.session.add(new_referal)
        db.session.commit()
        db.session.flush()
        
        # Добавляем дополнительные паспортные данные из формы
        referal_data = new_referal.referal_data
        passport_number = request.form.get('passport_number', '').strip()
        passport_date = request.form.get('passport_date', '').strip()
        passport_giver = request.form.get('passport_giver', '').strip()
        
        if passport_number:
            referal_data.passport_number = passport_number
        if passport_date:
            referal_data.passport_date = datetime.strptime(passport_date, '%Y-%m-%d')
        if passport_giver:
            referal_data.passport_giver = passport_giver
        
        db.session.commit()
        
        # НОВАЯ ЛОГИКА: Ищем и привязываем все договора в пределах 45 дней
        linked_deals = referal_service.find_and_link_deals_for_referal(new_referal)
        
        if linked_deals:
            # Обновляем баланс на основе найденных договоров
            total_added = referal_service.update_balance_for_referal(new_referal, user)
            db.session.commit()
            
            flash(
                f'✅ Реферал {full_name} добавлен! Найдено и привязано {len(linked_deals)} договоров. '
                f'К балансу добавлено: {total_added} сум.', 
                'success'
            )
        else:
            flash(f'✅ Реферал {full_name} успешно добавлен!', 'success')
        
        # Случайный выбор менеджера для назначения встречи
        managers = [
            """Zairov Odil Kamildjanovich""",
            """Yulchiyev Ramazon""",
            """Rustamov Azizbek""",
            """Miraxmad Mirboboev""",
            """Djumabayev Akbar""",
            """Lyovkin Dmitriy""",
            """Abdukhalikova Jasmina""",
            """Bekov Abbosbek Alisher ogli""",
            """Mukhsinov Sukhrob""",
            """Parpiyeva Nasibaxon"""
        ]
        manager = managers[random.randint(0, len(managers) - 1)]
        
        # Отправляем уведомление менеджеру call-центра
        try:
            # Получаем пользователей с ролью call-center из auth-service
            call_center_users = utils.get_call_center_users_from_auth()
            
            if call_center_users:
                # Берем первого пользователя из списка
                first_cc_user = call_center_users[0]
                call_center_email = first_cc_user.get('email')
                call_center_name = first_cc_user.get('full_name', first_cc_user.get('username', 'Call-center менеджер'))
                
                if call_center_email:
                    utils.send_email(
                        call_center_email,
                        subject='Новый реферал для обзвона',
                        body=f'Пользователь {user.user_data.full_name if user.user_data else user.login} добавил нового реферала:\n\n'
                             f'Имя: {full_name}\n'
                             f'Телефон: {formatted_phone}\n\n'
                             f'Пожалуйста, свяжитесь с рефералом для дальнейшего взаимодействия.'
                    )
                    print(f"📧 Email notification sent to call-center manager: {call_center_name} ({call_center_email})")
                else:
                    print(f"⚠️ Call-center user found but has no email: {first_cc_user}")
            else:
                print(f"⚠️ No call-center users found in auth-service, skipping notification")
        except Exception as email_error:
            print(f"❌ Failed to send email notification: {email_error}")
            import traceback
            traceback.print_exc()
        
        print(f"✅ Successfully added referal: {full_name} ({formatted_phone}) for user {user.login} with {len(linked_deals)} linked deals")
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error adding referal: {e}")
        import traceback
        traceback.print_exc()
        flash(f'Произошла ошибка при добавлении реферала: {str(e)}', 'error')
    
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
        
        # Форматируем номер телефона через utils функцию
        formatted_phone = None
        if phone_number:
            # Если есть запятые, берем только первый номер
            first_phone = phone_number.split(',')[0].strip()
            formatted_phone = utils.format_phone_number(first_phone)
        
        # Обновляем поля реферала
        referal.referal_data.full_name = full_name if full_name else None
        referal.referal_data.phone_number = formatted_phone if formatted_phone else phone_number if phone_number else None
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
        if phone_number and not formatted_phone:
            flash('Неверный формат телефона. Введите корректный номер телефона', 'error')
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


@referal_bp.route('/get_referal_deals/<int:referal_id>', methods=['GET'])
def get_referal_deals(referal_id):
    """API endpoint для получения списка договоров реферала"""
    print(f"🔍 get_referal_deals called with referal_id={referal_id}")
    try:
        user = get_current_user()
        print(f"🔍 Current user: {user.login if user else 'None'}")
        
        if not user:
            print(f"❌ User not authorized")
            return jsonify({'success': False, 'message': 'Пользователь не авторизован'}), 401
        
        print(f"🔍 Looking for referal with id={referal_id}")
        referal = Referal.query.get_or_404(referal_id)
        print(f"✅ Referal found: {referal.id}, user_id={referal.user_id}")
        
        # Проверяем права доступа: либо это владелец реферала, либо админ
        from permission_utils import requires_admin_access
        is_admin = requires_admin_access()
        print(f"🔍 Is admin: {is_admin}, referal.user_id={referal.user_id}, current user.id={user.id}")
        
        if not is_admin and referal.user_id != user.id:
            print(f"❌ Access denied: not admin and not owner")
            return jsonify({'success': False, 'message': 'Доступ запрещен'}), 403
        
        print(f"🔍 Getting deals summary...")
        deals_summary = referal.get_deals_summary()
        print(f"✅ Deals summary retrieved: {len(deals_summary)} deals")
        
        result = {
            'success': True,
            'referal_name': referal.referal_data.full_name if referal.referal_data else 'Неизвестно',
            'total_deals': referal.get_deals_count(),
            'pending_deals': referal.get_pending_deals_count(),
            'approved_deals': referal.get_approved_deals_count(),
            'total_withdrawal': referal.get_total_withdrawal_amount(),
            'deals': deals_summary
        }
        print(f"✅ Returning success response")
        return jsonify(result)
    except Exception as e:
        print(f"❌ ERROR in get_referal_deals: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Ошибка: {str(e)}'}), 500


@referal_bp.route('/request_withdrawal_deal/<int:referal_deal_id>', methods=['POST'])
def request_withdrawal_deal(referal_deal_id):
    """Отправка конкретного договора на проверку"""
    try:
        user = get_current_user()
        if not user:
            return jsonify({'success': False, 'message': 'Пользователь не авторизован'}), 401
        
        referal_deal = ReferalDeal.query.get_or_404(referal_deal_id)
        referal = referal_deal.referal
        
        # Проверяем что реферал принадлежит текущему пользователю
        if referal.user_id != user.id:
            return jsonify({'success': False, 'message': 'Доступ запрещен'}), 403
        
        # Проверяем что договор еще не отправлен
        if referal_deal.deal_status != 'pending':
            return jsonify({
                'success': False, 
                'message': f'Договор уже был отправлен (статус: {referal_deal.deal_status})'
            }), 400
        
        # Проверяем наличие паспортных данных
        if not referal.referal_data:
            return jsonify({'success': False, 'message': 'Отсутствуют данные реферала'}), 400
            
        if not referal.referal_data.passport_number or not referal.referal_data.passport_giver:
            return jsonify({
                'success': False, 
                'message': 'Необходимо заполнить паспортные данные реферала'
            }), 400
        
        # Обновляем статус договора на "Проверка отделом аналитики" (status_id = 1)
        referal_deal.status_id = 1
        referal_deal.deal_status = 'sent_for_review'
        db.session.commit()
        
        # Обновляем объект после коммита чтобы подгрузить связанный статус
        db.session.refresh(referal_deal)
        
        # Отправляем уведомление (можно добавить позже)
        # notification_service.notify_deal_sent_for_review(referal_deal)
        
        return jsonify({
            'success': True,
            'message': f'Договор {referal_deal.deal.agreement_number} отправлен на проверку',
            'new_status': 'sent_for_review',
            'new_status_id': 1,
            'new_status_name': referal_deal.status_name
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Ошибка: {str(e)}'}), 500


@referal_bp.route('/add_referal_deal/<int:referal_id>', methods=['POST'])
def add_referal_deal(referal_id):
    """Добавление нового договора к рефералу"""
    try:
        user = get_current_user()
        if not user:
            return jsonify({'success': False, 'message': 'Пользователь не авторизован'}), 401
        
        referal = Referal.query.get_or_404(referal_id)
        
        # Проверяем доступ
        if not check_referal_access(referal):
            return jsonify({'success': False, 'message': 'Доступ запрещен'}), 403
        
        data = request.get_json()
        contact_id = data.get('contact_id')
        deal_status = data.get('deal_status', 'active')
        
        if not contact_id:
            return jsonify({'success': False, 'message': 'ID контакта обязателен'}), 400
        
        # Ищем договор по contact_id
        deal = MacroDeal.query.filter_by(contacts_buy_id=contact_id).first()
        if not deal:
            return jsonify({'success': False, 'message': f'Договор с contact_id {contact_id} не найден'}), 404
        
        # Проверяем, не существует ли уже такая связь
        existing = ReferalDeal.query.filter_by(referal_id=referal_id, deal_id=deal.id).first()
        if existing:
            return jsonify({'success': False, 'message': 'Этот договор уже связан с рефералом'}), 400
        
        # Создаем новую связь
        referal_deal = ReferalDeal(
            referal_id=referal_id,
            deal_id=deal.id,
            deal_status=deal_status
        )
        
        db.session.add(referal_deal)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Договор {deal.agreement_number} успешно добавлен'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Ошибка: {str(e)}'}), 500


@referal_bp.route('/update_deal_status/<int:referal_deal_id>', methods=['POST'])
def update_deal_status(referal_deal_id):
    """Обновление статуса связи реферал-договор"""
    try:
        user = get_current_user()
        if not user:
            return jsonify({'success': False, 'message': 'Пользователь не авторизован'}), 401
        
        referal_deal = ReferalDeal.query.get_or_404(referal_deal_id)
        referal = referal_deal.referal
        
        # Проверяем доступ
        if not check_referal_access(referal):
            return jsonify({'success': False, 'message': 'Доступ запрещен'}), 403
        
        data = request.get_json()
        new_status = data.get('deal_status')
        
        if not new_status:
            return jsonify({'success': False, 'message': 'Статус обязателен'}), 400
        
        valid_statuses = ['active', 'completed', 'cancelled']
        if new_status not in valid_statuses:
            return jsonify({'success': False, 'message': f'Неверный статус. Допустимые: {", ".join(valid_statuses)}'}), 400
        
        referal_deal.deal_status = new_status
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Статус успешно обновлен'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Ошибка: {str(e)}'}), 500


@referal_bp.route('/remove_referal_deal/<int:referal_deal_id>', methods=['DELETE'])
def remove_referal_deal(referal_deal_id):
    """Удаление связи между рефералом и договором"""
    try:
        user = get_current_user()
        if not user:
            return jsonify({'success': False, 'message': 'Пользователь не авторизован'}), 401
        
        referal_deal = ReferalDeal.query.get_or_404(referal_deal_id)
        referal = referal_deal.referal
        
        # Проверяем доступ
        if not check_referal_access(referal):
            return jsonify({'success': False, 'message': 'Доступ запрещен'}), 403
        
        db.session.delete(referal_deal)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Связь успешно удалена'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Ошибка: {str(e)}'}), 500



