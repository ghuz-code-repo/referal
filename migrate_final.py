#!/usr/bin/env python3
"""Финальная миграция данных из SQLite в PostgreSQL с правильной обработкой constraints"""

import os
import psycopg2
import sqlite3
from datetime import datetime

# Настройки
SQLITE_PATH = 'instance/referal_program.db'
PG_CONN_STRING = f"host={os.getenv('POSTGRES_HOST', 'postgres')} " \
                 f"port={os.getenv('POSTGRES_PORT', '5432')} " \
                 f"dbname={os.getenv('POSTGRES_DB', 'referal_db')} " \
                 f"user={os.getenv('POSTGRES_USER', 'referal_user')} " \
                 f"password={os.getenv('POSTGRES_PASSWORD', 'ghref_2025_secure!')}"

# Конвертация boolean полей
BOOLEAN_FIELDS = {
    'status': ['is_final', 'is_start'],
    'referal': ['initial_approval', 'analytics_approval', 'cc_approval', 'cd_approval',
               'balance_updated', 'balance_pending_withdrawal', 'balance_withdrawn'],
    'referal_deal': ['is_within_window', 'payment_processed'],
    'macro_deal': ['payment_calculated']
}

# Правильный порядок миграции таблиц (учитываем зависимости)
TABLE_ORDER = [
    'status',           # Независимая
    'user',             # Независимая  
    'user_data',        # Зависит от user
    'macro_contact',    # Независимая
    'referal',          # Зависит от user, status
    'referal_data',     # Зависит от referal
    'macro_deal',       # Зависит от referal (nullable FK)
    'referal_deal',     # Зависит от referal И macro_deal
    'manager'           # Независимая
]


def convert_row(table_name, row, columns):
    """Конвертирует значения строки для PostgreSQL"""
    converted = list(row)
    
    # Конвертируем 0/1 в boolean для указанных полей
    if table_name in BOOLEAN_FIELDS:
        for i, col_name in enumerate(columns):
            if col_name in BOOLEAN_FIELDS[table_name] and converted[i] is not None:
                converted[i] = bool(converted[i])
    
    # Конвертируем -1 в NULL для macro_deal.referal_id
    if table_name == 'macro_deal' and 'referal_id' in columns:
        referal_id_idx = columns.index('referal_id')
        if converted[referal_id_idx] == -1:
            converted[referal_id_idx] = None
    
    return converted


def migrate():
    print("="*60)
    print("🔄 ФИНАЛЬНАЯ МИГРАЦИЯ SQLite → PostgreSQL")
    print("="*60)
    
    # Создаем бэкап
    if os.path.exists(SQLITE_PATH):
        backup_dir = 'backups'
        os.makedirs(backup_dir, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = os.path.join(backup_dir, f'sqlite_backup_{timestamp}.db')
        
        import shutil
        shutil.copy2(SQLITE_PATH, backup_path)
        print(f"\n✅ Backup created: {backup_path}")
    
    # Подключаемся
    print("\n🔌 Connecting to databases...")
    sqlite_conn = sqlite3.connect(SQLITE_PATH)
    pg_conn = psycopg2.connect(PG_CONN_STRING)
    
    try:
        sqlite_cur = sqlite_conn.cursor()
        pg_cur = pg_conn.cursor()
        
        print("✅ Connected successfully")
        
        # КЛЮЧЕВОЙ МОМЕНТ: Отключаем constraint checking для всей транзакции
        print("\n⚙️  Disabling constraint checks...")
        pg_cur.execute("SET CONSTRAINTS ALL DEFERRED;")
        print("✅ Constraints will be checked only at commit")
        
        # Миграция таблиц
        print("\n" + "="*60)
        print("📦 MIGRATING TABLES")
        print("="*60)
        
        migrated_count = 0
        
        for table_name in TABLE_ORDER:
            print(f"\n📋 Table: {table_name}")
            
            # Читаем из SQLite
            try:
                sqlite_cur.execute(f"SELECT * FROM {table_name}")
                rows = sqlite_cur.fetchall()
            except sqlite3.OperationalError:
                print(f"   ⚠️  Table {table_name} not found in SQLite, skipping")
                continue
            
            if not rows:
                print(f"   ⚠️  Table is empty, skipping")
                continue
            
            print(f"   📊 Found {len(rows)} rows")
            
            # Получаем названия колонок
            columns = [desc[0] for desc in sqlite_cur.description]
            
            # Очищаем таблицу в PostgreSQL
            table_esc = f'"{table_name}"' if table_name == 'user' else table_name
            pg_cur.execute(f"TRUNCATE TABLE {table_esc} RESTART IDENTITY CASCADE")
            
            # Вставляем данные батчами
            placeholders = ','.join(['%s'] * len(columns))
            columns_str = ','.join(columns)
            insert_query = f"INSERT INTO {table_esc} ({columns_str}) VALUES ({placeholders})"
            
            batch_size = 500
            inserted = 0
            
            for i in range(0, len(rows), batch_size):
                batch = rows[i:i+batch_size]
                
                for row in batch:
                    converted = convert_row(table_name, row, columns)
                    pg_cur.execute(insert_query, converted)
                    inserted += 1
                
                # Показываем прогресс для больших таблиц
                if len(rows) > 1000 and (inserted % 5000 == 0 or inserted >= len(rows)):
                    print(f"   ⏳ Inserted {inserted}/{len(rows)} rows...")
            
            print(f"   ✅ Inserted all {inserted} rows")
            
            # Обновляем sequence если есть id
            if 'id' in columns:
                pg_cur.execute(f"""
                    SELECT setval(
                        pg_get_serial_sequence('{table_esc}', 'id'), 
                        COALESCE((SELECT MAX(id) FROM {table_esc}), 1),
                        true
                    )
                """)
                print(f"   ✅ Updated sequence")
            
            migrated_count += 1
        
        # ВАЖНО: Коммит проверит все constraints один раз в конце
        print("\n" + "="*60)
        print("💾 Committing transaction...")
        print("   (checking all constraints now...)")
        pg_conn.commit()
        print("✅ Transaction committed successfully!")
        
        # Verification
        print("\n" + "="*60)
        print("🔍 VERIFICATION")
        print("="*60)
        
        all_match = True
        
        for table_name in TABLE_ORDER:
            table_esc = f'"{table_name}"' if table_name == 'user' else table_name
            
            try:
                sqlite_cur.execute(f"SELECT COUNT(*) FROM {table_name}")
                sqlite_count = sqlite_cur.fetchone()[0]
            except:
                continue
            
            pg_cur.execute(f"SELECT COUNT(*) FROM {table_esc}")
            pg_count = pg_cur.fetchone()[0]
            
            match = sqlite_count == pg_count
            status = "✅" if match else "❌"
            print(f"{status} {table_name:20s} SQLite: {sqlite_count:6d}  PostgreSQL: {pg_count:6d}")
            
            if not match:
                all_match = False
        
        print("\n" + "="*60)
        if all_match:
            print("🎉 MIGRATION COMPLETED SUCCESSFULLY!")
            print(f"✅ All {migrated_count} tables migrated and verified")
        else:
            print("⚠️  MIGRATION COMPLETED WITH WARNINGS")
            print("Some tables have mismatched counts - please review")
        print("="*60)
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        print("\n🔄 Rolling back transaction...")
        pg_conn.rollback()
        print("✅ Rollback completed")
        raise
    finally:
        sqlite_conn.close()
        pg_conn.close()


if __name__ == '__main__':
    migrate()
