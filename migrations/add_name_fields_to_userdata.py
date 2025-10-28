"""
Миграция для добавления полей first_name, last_name, middle_name в таблицу UserData
Дата: 2025-10-28
"""

from app_with_auth_connector import app, db
from models import UserData

def migrate():
    """Добавляет поля first_name, last_name, middle_name в таблицу user_data"""
    with app.app_context():
        print("🔄 Starting migration: add name fields to UserData")
        
        # Проверяем существование столбцов
        inspector = db.inspect(db.engine)
        columns = [col['name'] for col in inspector.get_columns('user_data')]
        
        fields_to_add = []
        if 'first_name' not in columns:
            fields_to_add.append('first_name')
        if 'last_name' not in columns:
            fields_to_add.append('last_name')
        if 'middle_name' not in columns:
            fields_to_add.append('middle_name')
        
        if not fields_to_add:
            print("✅ All name fields already exist in user_data table")
            return
        
        print(f"📝 Adding fields: {', '.join(fields_to_add)}")
        
        # Добавляем поля через SQL
        with db.engine.connect() as conn:
            if 'first_name' in fields_to_add:
                conn.execute(db.text('ALTER TABLE user_data ADD COLUMN first_name VARCHAR(100)'))
                print("✅ Added first_name column")
            
            if 'last_name' in fields_to_add:
                conn.execute(db.text('ALTER TABLE user_data ADD COLUMN last_name VARCHAR(100)'))
                print("✅ Added last_name column")
            
            if 'middle_name' in fields_to_add:
                conn.execute(db.text('ALTER TABLE user_data ADD COLUMN middle_name VARCHAR(100)'))
                print("✅ Added middle_name column")
            
            conn.commit()
        
        print("✅ Migration completed successfully!")
        print("📝 Note: Run sync_user_profile_always() to populate these fields from auth-service")

if __name__ == '__main__':
    migrate()
