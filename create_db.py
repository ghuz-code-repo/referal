"""
Simple database creation script
"""

from models import User, UserData, db
from app import app

def create_database():
    with app.app_context():
        print("Creating database tables...")
        # Удаляем все таблицы и создаем заново
        db.drop_all()
        db.create_all()
        print("Database tables created successfully")
        
        # Создаем тестового пользователя
        user = User(
            login='d.tolkunov',
            auth_user_id='688216fa279b8a22aabeb26a',
            role='user'
        )
        db.session.add(user)
        db.session.commit()
        print(f"Created user: {user.login}")
        
        # Создаем UserData
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
    create_database()