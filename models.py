from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
import os

db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_data = db.relationship('UserData', backref='user', lazy=True, uselist=False)
    login = db.Column(db.String(80), unique=True, nullable=False)
    auth_user_id = db.Column(db.String(24), nullable=True)  # MongoDB ObjectId from auth-service
    role = db.Column(db.String(50), nullable=False, default='user')
    referals = db.relationship('Referal', backref='user', lazy=True)
    current_balance = db.Column(db.Integer, default=0)
    pending_withdrawal = db.Column(db.Integer, default=0)
    total_withdrawal = db.Column(db.Integer, default=0)
    
    def get_id(self):
        return str(self.id)

    @property 
    def full_name(self):
        """Получить полное имя пользователя из user_data"""
        if self.user_data and self.user_data.full_name:
            return self.user_data.full_name
        return None

    @property
    def short_name(self):
        """Получить короткое имя (Фамилия И.О.) из полного имени"""
        if not self.full_name:
            return None
        
        name_parts = self.full_name.strip().split()
        if len(name_parts) >= 3:
            # Фамилия Имя Отчество -> Фамилия И.О.
            surname = name_parts[0]
            name_initial = name_parts[1][0] + '.' if name_parts[1] else ''
            patronymic_initial = name_parts[2][0] + '.' if name_parts[2] else ''
            return f"{surname} {name_initial}{patronymic_initial}"
        elif len(name_parts) == 2:
            # Фамилия Имя -> Фамилия И.
            surname = name_parts[0]
            name_initial = name_parts[1][0] + '.' if name_parts[1] else ''
            return f"{surname} {name_initial}"
        else:
            # Если только одно слово, возвращаем как есть
            return self.full_name

    def __repr__(self):
        return f'<User {self.login}>'


class UserData(db.Model):
    #IDS
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    #Passport
    full_name = db.Column(db.String(120), nullable=False)
    passport_number = db.Column(db.String(50), nullable=True)
    passport_giver = db.Column(db.String(100), nullable=True)
    passport_date = db.Column(db.DateTime, nullable=True)
    passport_adress = db.Column(db.String(255), nullable=True)
    # mail_adress = db.Column(db.String(255), nullable=True)
    #Finance docs
    pinfl = db.Column(db.String(50), nullable=True)
    bank_name = db.Column(db.String(100), nullable=True)
    trans_schet = db.Column(db.String(50), nullable=True)
    card_number = db.Column(db.String(50), nullable=True)
    mfo = db.Column(db.String(50), nullable=True)
    #Contact data
    phone = db.Column(db.String(20), nullable=True)
    e_mail = db.Column(db.String(50), nullable=True)

class Referal(db.Model):
    #IDS
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    contact_id = db.Column(db.Integer, nullable=True)
    referal_data = db.relationship('ReferalData', backref='referal', lazy=True, uselist=False)
    deals = db.relationship('MacroDeal', backref='referal', lazy=True)
    
    # NEW: Поля для отслеживания 45-дневного окна
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    days_window = db.Column(db.Integer, nullable=False, default=45)
    
    #Status
    status_id = db.Column(db.Integer, db.ForeignKey('status.id'), nullable=False, default=0)
    status_name = db.Column(db.String(50), nullable=True, default='Не начата')
    rejection_reason = db.Column(db.String(1024), nullable=True)
    rejecter_name = db.Column(db.String(100), nullable=True)
    #Approvals
    initial_approval = db.Column(db.Boolean, default=False)
    analytics_approval = db.Column(db.Boolean, default=False)
    cc_approval = db.Column(db.Boolean, default=False)
    cd_approval = db.Column(db.Boolean, default=False)
    payment_amount = db.Column(db.Float, nullable=True)
    #Balance
    balance_updated = db.Column(db.Boolean, default=False)  # New field
    balance_pending_withdrawal = db.Column(db.Boolean, default=False)  # New field
    balance_withdrawn = db.Column(db.Boolean, default=False)  # New field
    withdrawal_amount = db.Column(db.Integer, default=0, nullable=True)  # New field
    
    def get_macro_contact(self):
        """Возвращает связанный MacroContact, если есть contact_id"""
        if self.contact_id:
            return MacroContact.query.filter_by(contacts_id=self.contact_id).first()
        return None
    
    def get_deals_summary(self):
        """Возвращает список всех договоров с их данными для UI"""
        deals_info = []
        for referal_deal in self.referal_deals.all():
            deal = referal_deal.deal
            if deal:
                # Проверяем что это реальный договор:
                # 1. Есть номер договора
                # 2. ЛИБО есть оплата >= 3млн, ЛИБО уже рассчитана сумма выплаты
                # 3. Статус НЕ "Сделка отменена", "Не понравилось" или "Не определен"
                has_agreement_number = deal.agreement_number and deal.agreement_number.strip()
                has_payment = deal.total_payments and deal.total_payments >= 3000000
                has_withdrawal = referal_deal.withdrawal_amount and referal_deal.withdrawal_amount > 0
                
                # Только реальные договора: "Сделка проведена" и "Сделка в работе"
                valid_statuses = ['Сделка проведена', 'Сделка в работе']
                is_valid_status = deal.deal_status_name in valid_statuses
                
                # Показываем если есть номер И (есть оплата ИЛИ есть рассчитанная выплата) И статус валидный
                if has_agreement_number and (has_payment or has_withdrawal) and is_valid_status:
                    deals_info.append({
                        'referal_deal_id': referal_deal.id,
                        'deal_id': deal.id,
                        'agreement_number': deal.agreement_number,
                        'deal_status_name': deal.deal_status_name,
                        'withdrawal_amount': referal_deal.withdrawal_amount,
                        'deal_status': referal_deal.deal_status,
                        'payment_processed': referal_deal.payment_processed,
                        'is_within_window': referal_deal.is_within_window,
                        'days_from_creation': referal_deal.days_from_referal_creation,
                        'linked_at': referal_deal.linked_at,
                        'project_name': deal.project_name,
                        'apartment_number': deal.apartment_number,
                        'agreement_date': deal.agreement_date,
                        'status_id': referal_deal.status_id,
                        'status_name': referal_deal.status_name
                    })
        return deals_info
    
    def get_total_withdrawal_amount(self):
        """Возвращает общую сумму к выводу по всем реальным договорам"""
        total = 0
        for referal_deal in self.referal_deals.all():
            deal = referal_deal.deal
            if deal and referal_deal.withdrawal_amount:
                # Считаем только договоры с номером И (есть оплата >= 3млн ИЛИ есть рассчитанная выплата) И валидным статусом
                has_agreement_number = deal.agreement_number and deal.agreement_number.strip()
                has_payment = deal.total_payments and deal.total_payments >= 3000000
                has_withdrawal = referal_deal.withdrawal_amount > 0
                
                # Только реальные договора: "Сделка проведена" и "Сделка в работе"
                valid_statuses = ['Сделка проведена', 'Сделка в работе']
                is_valid_status = deal.deal_status_name in valid_statuses
                
                if has_agreement_number and (has_payment or has_withdrawal) and is_valid_status:
                    total += referal_deal.withdrawal_amount
        return total
    
    def get_deals_count(self):
        """Возвращает количество реальных связанных договоров"""
        count = 0
        for referal_deal in self.referal_deals.all():
            deal = referal_deal.deal
            if deal:
                has_agreement_number = deal.agreement_number and deal.agreement_number.strip()
                has_payment = deal.total_payments and deal.total_payments >= 3000000
                has_withdrawal = referal_deal.withdrawal_amount and referal_deal.withdrawal_amount > 0
                
                # Только реальные договора: "Сделка проведена" и "Сделка в работе"
                valid_statuses = ['Сделка проведена', 'Сделка в работе']
                is_valid_status = deal.deal_status_name in valid_statuses
                
                if has_agreement_number and (has_payment or has_withdrawal) and is_valid_status:
                    count += 1
        return count
    
    def get_pending_deals_count(self):
        """Возвращает количество реальных договоров ожидающих отправки"""
        count = 0
        for referal_deal in self.referal_deals.filter_by(deal_status='pending').all():
            deal = referal_deal.deal
            if deal:
                has_agreement_number = deal.agreement_number and deal.agreement_number.strip()
                has_payment = deal.total_payments and deal.total_payments >= 3000000
                has_withdrawal = referal_deal.withdrawal_amount and referal_deal.withdrawal_amount > 0
                
                # Только реальные договора: "Сделка проведена" и "Сделка в работе"
                valid_statuses = ['Сделка проведена', 'Сделка в работе']
                is_valid_status = deal.deal_status_name in valid_statuses
                
                if has_agreement_number and (has_payment or has_withdrawal) and is_valid_status:
                    count += 1
        return count
    
    def get_approved_deals_count(self):
        """Возвращает количество реальных одобренных договоров"""
        count = 0
        for referal_deal in self.referal_deals.filter_by(deal_status='approved').all():
            deal = referal_deal.deal
            if deal:
                has_agreement_number = deal.agreement_number and deal.agreement_number.strip()
                has_payment = deal.total_payments and deal.total_payments >= 3000000
                has_withdrawal = referal_deal.withdrawal_amount and referal_deal.withdrawal_amount > 0
                
                # Только реальные договора: "Сделка проведена" и "Сделка в работе"
                valid_statuses = ['Сделка проведена', 'Сделка в работе']
                is_valid_status = deal.deal_status_name in valid_statuses
                
                if has_agreement_number and (has_payment or has_withdrawal) and is_valid_status:
                    count += 1
        return count

    def __repr__(self):
        return f'<Referal {self.full_name}>'

class ReferalData(db.Model):
    #IDS
    id = db.Column(db.Integer, primary_key=True)
    referal_id = db.Column(db.Integer, db.ForeignKey('referal.id'), nullable=False)
    #Agreement
    contract_date = db.Column(db.DateTime, nullable=True)
    contract_number = db.Column(db.String(50), nullable=True)
    #Personal
    full_name = db.Column(db.String(100), nullable=True, unique=True)
    passport_number = db.Column(db.String(50), nullable=True)
    passport_date = db.Column(db.DateTime, nullable=True)
    passport_giver = db.Column(db.String(100), nullable=True)
    passport_adress = db.Column(db.String(255), nullable=True)
    #Contact
    phone_number = db.Column(db.String(20), nullable=True, unique=True)
    # mail_adress = db.Column(db.String(255), nullable=True)

class MacroDeal(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    deal_status_name = db.Column(db.String(100), nullable=False)
    agreement_number = db.Column(db.String(50), nullable=False)
    contacts_buy_id = db.Column(db.Integer, nullable=False)
    deal_metr = db.Column(db.Float, nullable=True)  # площадь сделки
    total_payments = db.Column(db.Float, nullable=True, default=0)  # общая сумма оплат
    referal_id = db.Column(db.Integer, db.ForeignKey('referal.id'), nullable=True)  # CHANGED: nullable=True
    
    # NEW: Поля для отслеживания выплат по конкретному договору
    payment_calculated = db.Column(db.Boolean, default=False)
    withdrawal_amount = db.Column(db.Integer, default=0)
    
    # Поля недвижимости для генерации актов
    project_name = db.Column(db.String(200), nullable=True)  # название проекта
    house_address = db.Column(db.String(200), nullable=True)  # адрес дома
    house_number = db.Column(db.String(50), nullable=True)  # номер дома
    apartment_number = db.Column(db.String(50), nullable=True)  # номер квартиры
    agreement_price = db.Column(db.Float, nullable=True)  # цена договора
    agreement_date = db.Column(db.Date, nullable=True)  # дата договора
    
    def has_valid_payment(self):
        """Проверяет есть ли оплата больше чем бронь (3млн)"""
        BOOKING_PAYMENT = 3000000
        return self.total_payments and self.total_payments > BOOKING_PAYMENT
    
    def __repr__(self):
        return f'<MacroDeal {self.agreement_number}>'

class MacroContact(db.Model):
    __tablename__ = 'macro_contact'
    
    id = db.Column(db.Integer, primary_key=True)
    contacts_id = db.Column(db.Integer, nullable=False)
    full_name = db.Column(db.String(255), nullable=False)
    phone_number = db.Column(db.String(20), unique=True, nullable=False)
    
    # Поля для паспортных данных
    passport_number = db.Column(db.String(50), nullable=True)
    passport_giver = db.Column(db.String(255), nullable=True)
    passport_date = db.Column(db.Date, nullable=True)
    passport_address = db.Column(db.Text, nullable=True)#УБРАТЬ
    email = db.Column(db.String(255), nullable=True)#УБРАТЬ
    
    # Добавляем поле номер договора
    agreement_number = db.Column(db.String(100), nullable=True)
    
    # NEW: Поля для отслеживания взаимодействий с CRM
    first_interaction_date = db.Column(db.DateTime, nullable=True)
    last_interaction_date = db.Column(db.DateTime, nullable=True)
    date_modified = db.Column(db.DateTime, nullable=True)  # Из синхронизации MacroCRM
    last_deal_date = db.Column(db.Date, nullable=True)  # Дата последней сделки/заявки клиента
    
    def __repr__(self):
        return f'<MacroContact {self.full_name}>'


class Manager(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    macro_id = db.Column(db.Integer, nullable=False)
    department_id = db.Column(db.Integer, nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    phone_number = db.Column(db.String(20), nullable=False, unique=True)
    office_name = db.Column(db.String(100), nullable=False)

class Status(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    is_final = db.Column(db.Boolean, default=False)
    is_start = db.Column(db.Boolean, default=False)


class ReferalDeal(db.Model):
    """Связь между рефералом и сделкой (Many-to-Many) с метаданными"""
    __tablename__ = 'referal_deal'
    
    id = db.Column(db.Integer, primary_key=True)
    referal_id = db.Column(db.Integer, db.ForeignKey('referal.id'), nullable=False)
    deal_id = db.Column(db.Integer, db.ForeignKey('macro_deal.id'), nullable=False)
    
    # НОВОЕ: Статус договора (теперь статус на уровне договора, а не реферала)
    status_id = db.Column(db.Integer, db.ForeignKey('status.id'), nullable=True, default=0)
    # 0 - Заполнить данные
    # 100 - На проверке у call-center
    # 200 - Готов к выплате
    # 300 - Выплачен
    # 500 - Отклонен
    
    # Метаданные связи
    linked_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    # Когда договор был привязан к рефералу
    
    is_within_window = db.Column(db.Boolean, default=True)
    # Попадает ли в 45-дневное окно
    
    withdrawal_amount = db.Column(db.Integer, default=0)
    # Сумма выплаты за эту конкретную связь
    
    payment_processed = db.Column(db.Boolean, default=False)
    # Была ли обработана выплата
    
    # Связи
    status = db.relationship('Status', foreign_keys=[status_id])
    
    days_from_referal_creation = db.Column(db.Integer, nullable=True)
    # Сколько дней прошло от создания реферала до создания договора
    
    deal_status = db.Column(db.String(50), default='pending')
    # Статус обработки договора: pending, sent_for_review, approved, rejected, paid
    
    rejection_reason = db.Column(db.Text, nullable=True)
    # Причина отказа (обязательно при status_id = 500)
    
    # Relationships для удобного доступа
    referal = db.relationship('Referal', backref=db.backref('referal_deals', lazy='dynamic'))
    deal = db.relationship('MacroDeal', backref=db.backref('referal_links', lazy='dynamic'))
    
    @property
    def status_name(self):
        """Возвращает название статуса договора"""
        if self.status:
            return self.status.name
        return 'Не указан'
    
    def __repr__(self):
        return f'<ReferalDeal referal_id={self.referal_id} deal_id={self.deal_id} status={self.status_id}>'
    
    # Уникальность: один договор не может быть привязан к одному рефералу дважды
    __table_args__ = (
        db.UniqueConstraint('referal_id', 'deal_id', name='unique_referal_deal'),
    )
    
    def __repr__(self):
        return f'<ReferalDeal referal_id={self.referal_id} deal_id={self.deal_id} amount={self.withdrawal_amount}>'


