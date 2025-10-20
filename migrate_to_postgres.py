#!/usr/bin/env python3
"""
Скрипт миграции данных из SQLite в PostgreSQL
Использование: python migrate_to_postgres.py
"""

import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from datetime import datetime

# SQLite source
SQLITE_PATH = os.path.join('instance', 'referal_program.db')
SQLITE_URI = f'sqlite:///{SQLITE_PATH}'

# PostgreSQL target (from environment)
POSTGRES_USER = os.getenv('POSTGRES_USER', 'referal_user')
POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD', 'referal_password')
POSTGRES_HOST = os.getenv('POSTGRES_HOST', 'localhost')
POSTGRES_PORT = os.getenv('POSTGRES_PORT', '5432')
POSTGRES_DB = os.getenv('POSTGRES_DB', 'referal_db')

POSTGRES_URI = f'postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}'


def backup_sqlite():
    """Создать резервную копию SQLite базы"""
    if not os.path.exists(SQLITE_PATH):
        print(f"❌ SQLite database not found at {SQLITE_PATH}")
        return False
    
    backup_dir = 'backups'
    os.makedirs(backup_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = os.path.join(backup_dir, f'referal_program_backup_{timestamp}.db')
    
    import shutil
    shutil.copy2(SQLITE_PATH, backup_path)
    print(f"✅ SQLite backup created: {backup_path}")
    return True


def get_table_list(engine):
    """Получить список всех таблиц"""
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT name FROM sqlite_master 
            WHERE type='table' 
            AND name NOT LIKE 'sqlite_%'
            ORDER BY name
        """))
        return [row[0] for row in result]


def convert_boolean_fields(table_name, row_dict):
    """Конвертировать INTEGER в BOOLEAN для специфичных полей"""
    boolean_fields = {
        'status': ['is_final', 'is_start'],
        'referal': ['initial_approval', 'analytics_approval', 'cc_approval', 'cd_approval',
                   'balance_updated', 'balance_pending_withdrawal', 'balance_withdrawn'],
        'referal_deal': ['is_within_window', 'payment_processed'],
        'macro_deal': ['payment_calculated']
    }
    
    if table_name in boolean_fields:
        for field in boolean_fields[table_name]:
            if field in row_dict and row_dict[field] is not None:
                # Конвертируем 0/1 в False/True
                row_dict[field] = bool(row_dict[field])
    
    # Конвертируем -1 в NULL для nullable foreign keys
    if table_name == 'macro_deal' and 'referal_id' in row_dict:
        if row_dict['referal_id'] == -1:
            row_dict['referal_id'] = None
    
    return row_dict


def migrate_table(sqlite_engine, postgres_engine, table_name):
    """Мигрировать одну таблицу"""
    print(f"\n📋 Migrating table: {table_name}")
    
    try:
        # Читаем данные из SQLite
        with sqlite_engine.connect() as sqlite_conn:
            result = sqlite_conn.execute(text(f"SELECT * FROM {table_name}"))
            rows = result.fetchall()
            columns = result.keys()
            
            if not rows:
                print(f"   ⚠️  Table {table_name} is empty, skipping")
                return True
            
            print(f"   📊 Found {len(rows)} rows")
            
            # Подготавливаем данные для вставки
            data = []
            for row in rows:
                row_dict = dict(zip(columns, row))
                # Конвертируем boolean поля
                row_dict = convert_boolean_fields(table_name, row_dict)
                data.append(row_dict)
            
            # Вставляем данные в PostgreSQL
            with postgres_engine.connect() as postgres_conn:
                # Очищаем таблицу (если нужно) - используем двойные кавычки для зарезервированных слов
                truncate_table = f'"{table_name}"' if table_name == 'user' else table_name
                postgres_conn.execute(text(f"TRUNCATE TABLE {truncate_table} CASCADE"))
                postgres_conn.commit()
                
                # Вставляем данные батчами по 100 записей
                batch_size = 100
                for i in range(0, len(data), batch_size):
                    batch = data[i:i+batch_size]
                    
                    # Формируем INSERT запрос - используем двойные кавычки для зарезервированных слов
                    insert_table = f'"{table_name}"' if table_name == 'user' else table_name
                    columns_str = ', '.join(columns)
                    placeholders = ', '.join([f':{col}' for col in columns])
                    insert_query = f"INSERT INTO {insert_table} ({columns_str}) VALUES ({placeholders})"
                    
                    postgres_conn.execute(text(insert_query), batch)
                    postgres_conn.commit()
                    
                    print(f"   ✅ Inserted {min(i+batch_size, len(data))}/{len(data)} rows")
                
                # Обновляем sequence для автоинкремента (если есть id)
                if 'id' in columns:
                    seq_table = f'"{table_name}"' if table_name == 'user' else table_name
                    postgres_conn.execute(text(f"""
                        SELECT setval(
                            pg_get_serial_sequence('{seq_table}', 'id'),
                            COALESCE(MAX(id), 1)
                        ) FROM {seq_table}
                    """))
                    postgres_conn.commit()
                    print(f"   ✅ Updated sequence for {table_name}")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Error migrating {table_name}: {e}")
        import traceback
        traceback.print_exc()
        return False


def verify_migration(sqlite_engine, postgres_engine):
    """Проверить корректность миграции"""
    print("\n" + "="*50)
    print("🔍 VERIFICATION")
    print("="*50)
    
    sqlite_tables = get_table_list(sqlite_engine)
    
    with sqlite_engine.connect() as sqlite_conn:
        with postgres_engine.connect() as postgres_conn:
            for table in sqlite_tables:
                try:
                    sqlite_count = sqlite_conn.execute(
                        text(f"SELECT COUNT(*) FROM {table}")
                    ).scalar()
                    
                    postgres_count = postgres_conn.execute(
                        text(f"SELECT COUNT(*) FROM {table}")
                    ).scalar()
                    
                    status = "✅" if sqlite_count == postgres_count else "❌"
                    print(f"{status} {table}: SQLite={sqlite_count}, PostgreSQL={postgres_count}")
                    
                except Exception as e:
                    print(f"⚠️  {table}: Error - {e}")


def main():
    print("="*50)
    print("🔄 SQLite to PostgreSQL Migration")
    print("="*50)
    
    # Проверяем наличие SQLite базы
    if not os.path.exists(SQLITE_PATH):
        print(f"❌ SQLite database not found at {SQLITE_PATH}")
        print("   Please ensure the database file exists before running migration.")
        sys.exit(1)
    
    print(f"\n📁 SQLite database: {SQLITE_PATH}")
    print(f"🐘 PostgreSQL: {POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}")
    
    # Создаем резервную копию
    print("\n📦 Creating backup...")
    if not backup_sqlite():
        print("❌ Failed to create backup")
        sys.exit(1)
    
    # Подключаемся к базам
    print("\n🔌 Connecting to databases...")
    try:
        sqlite_engine = create_engine(SQLITE_URI)
        postgres_engine = create_engine(POSTGRES_URI)
        
        # Проверяем подключения
        with sqlite_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("✅ SQLite connection OK")
        
        with postgres_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("✅ PostgreSQL connection OK")
        
    except Exception as e:
        print(f"❌ Failed to connect to databases: {e}")
        sys.exit(1)
    
    # Получаем список таблиц
    print("\n📋 Getting table list...")
    tables = get_table_list(sqlite_engine)
    print(f"Found {len(tables)} tables: {', '.join(tables)}")
    
    # Определяем правильный порядок миграции (сначала таблицы без foreign key)
    table_order = [
        'status',          # Независимая таблица
        'user',            # Независимая таблица
        'user_data',       # Зависит от user
        'macro_contact',   # Независимая таблица
        'macro_deal',      # Зависит от macro_contact
        'manager',         # Независимая таблица (может быть пустой)
        'referal',         # Зависит от user, status
        'referal_data',    # Зависит от referal
        'referal_deal',    # Зависит от referal
    ]
    
    # Используем только те таблицы, которые есть в базе
    ordered_tables = [t for t in table_order if t in tables]
    # Добавляем таблицы, которых нет в нашем списке (на случай новых)
    remaining_tables = [t for t in tables if t not in table_order]
    ordered_tables.extend(remaining_tables)
    
    print(f"Migration order: {', '.join(ordered_tables)}")
    
    # Мигрируем каждую таблицу
    print("\n" + "="*50)
    print("📦 MIGRATION PROCESS")
    print("="*50)
    
    # Отключаем foreign key проверку ГЛОБАЛЬНО для всей миграции
    print("\n⚙️  Disabling foreign key checks...")
    with postgres_engine.connect() as conn:
        conn.execute(text("SET session_replication_role = replica;"))
        conn.commit()
    print("✅ Foreign key checks disabled")
    
    success_count = 0
    failed_tables = []
    
    for table in ordered_tables:
        if migrate_table(sqlite_engine, postgres_engine, table):
            success_count += 1
        else:
            failed_tables.append(table)
    
    # Включаем foreign key проверку обратно
    print("\n⚙️  Re-enabling foreign key checks...")
    with postgres_engine.connect() as conn:
        conn.execute(text("SET session_replication_role = DEFAULT;"))
        conn.commit()
    print("✅ Foreign key checks re-enabled")
    
    # Проверяем результаты
    verify_migration(sqlite_engine, postgres_engine)
    
    # Итоговый отчет
    print("\n" + "="*50)
    print("📊 MIGRATION SUMMARY")
    print("="*50)
    print(f"✅ Successfully migrated: {success_count}/{len(tables)} tables")
    
    if failed_tables:
        print(f"❌ Failed tables: {', '.join(failed_tables)}")
        sys.exit(1)
    else:
        print("\n🎉 Migration completed successfully!")
        print("\n📝 Next steps:")
        print("1. Update your .env file with PostgreSQL connection string")
        print("2. Restart the application: docker compose down && docker compose up -d")
        print("3. Verify the application works correctly")
        print("4. Keep the SQLite backup in backups/ directory")


if __name__ == '__main__':
    main()
