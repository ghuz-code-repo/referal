"""
Миграция для добавления полей в MacroContact
"""
from sqlalchemy import text
from models import db

def upgrade():
    """Добавляет новые поля в таблицу macro_contact"""
    try:
        # PostgreSQL требует отдельный ALTER TABLE для каждой колонки
        # Проверяем какая БД используется
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        existing_columns = [col['name'] for col in inspector.get_columns('macro_contact')]
        
        fields_to_add = [
            ('passport_number', 'VARCHAR(50)'),
            ('passport_giver', 'VARCHAR(255)'),
            ('passport_date', 'DATE'),
            ('passport_address', 'TEXT'),
            ('email', 'VARCHAR(255)')
        ]
        
        for field_name, field_type in fields_to_add:
            if field_name not in existing_columns:
                db.engine.execute(text(f"""
                    ALTER TABLE macro_contact 
                    ADD COLUMN {field_name} {field_type}
                """))
                print(f"Added column {field_name} to macro_contact table")
            else:
                print(f"Column {field_name} already exists in macro_contact table")
        
        print("Successfully processed all fields for macro_contact table")
    except Exception as e:
        print(f"Error adding fields to macro_contact: {e}")
        raise

def downgrade():
    """Удаляет добавленные поля"""
    try:
        # PostgreSQL требует отдельный DROP COLUMN для каждой колонки
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        existing_columns = [col['name'] for col in inspector.get_columns('macro_contact')]
        
        fields_to_remove = ['passport_number', 'passport_giver', 'passport_date', 'passport_address', 'email']
        
        for field_name in fields_to_remove:
            if field_name in existing_columns:
                db.engine.execute(text(f"""
                    ALTER TABLE macro_contact 
                    DROP COLUMN {field_name}
                """))
                print(f"Removed column {field_name} from macro_contact table")
            else:
                print(f"Column {field_name} does not exist in macro_contact table")
        
        print("Successfully processed all fields removal from macro_contact table")
    except Exception as e:
        print(f"Error removing fields from macro_contact: {e}")
        raise

if __name__ == "__main__":
    # Запуск миграции
    upgrade()
