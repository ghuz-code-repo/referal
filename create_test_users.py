"""
Script to create test users in referal service with auth_user_id
"""

from models import User, UserData, db
from app import app

def create_test_users():
    with app.app_context():
        # Создаем таблицы если их нет
        db.create_all()
        
        # Проверяем, есть ли уже пользователь d.tolkunov
        existing_user = User.query.filter_by(login='d.tolkunov').first()
        if existing_user:
            print(f"User d.tolkunov already exists with ID: {existing_user.id}")
            # Обновляем auth_user_id если его нет
            if not existing_user.auth_user_id:
                existing_user.auth_user_id = '688216fa279b8a22aabeb26a'
                db.session.commit()
                print("Updated auth_user_id for existing user")
            return
        
        # Создаем нового пользователя
        user = User(
            login='d.tolkunov',
            auth_user_id='688216fa279b8a22aabeb26a',  # ID из auth-service
            role='user'
        )
        db.session.add(user)
        db.session.commit()
        
        print(f"Created user: {user.login} with auth_user_id: {user.auth_user_id}")
        
        # Создаем UserData для пользователя
        user_data = UserData(
            user_id=user.id,
            full_name='Толкунов Дмитрий Валерьевич',
            passport_number='',
            passport_giver='',
            passport_adress='',
            pinfl='',
            trans_schet='',
            card_number='',
            bank_name='',
            mfo='',
            phone='',
            e_mail=''
        )
        db.session.add(user_data)
        db.session.commit()
        
        print(f"Created UserData for user: {user.login}")

if __name__ == "__main__":
    create_test_users()