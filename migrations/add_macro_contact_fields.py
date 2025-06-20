"""
Миграция для добавления полей в MacroContact
"""
from sqlalchemy import text
from models import db

def upgrade():
    """Добавляет новые поля в таблицу macro_contact"""
    try:
        # Добавляем поля паспортных данных
        db.engine.execute(text("""
            ALTER TABLE macro_contact 
            ADD COLUMN passport_number VARCHAR(50),
            ADD COLUMN passport_giver VARCHAR(255),
            ADD COLUMN passport_date DATE,
            ADD COLUMN passport_address TEXT,
            ADD COLUMN email VARCHAR(255)
        """))
        
        print("Successfully added new fields to macro_contact table")
    except Exception as e:
        print(f"Error adding fields to macro_contact: {e}")
        raise

def downgrade():
    """Удаляет добавленные поля"""
    try:
        db.engine.execute(text("""
            ALTER TABLE macro_contact 
            DROP COLUMN passport_number,
            DROP COLUMN passport_giver,
            DROP COLUMN passport_date,
            DROP COLUMN passport_address,
            DROP COLUMN email
        """))
        
        print("Successfully removed fields from macro_contact table")
    except Exception as e:
        print(f"Error removing fields from macro_contact: {e}")
        raise

if __name__ == "__main__":
    # Запуск миграции
    upgrade()
