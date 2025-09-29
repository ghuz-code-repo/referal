"""
Migration script for moving from legacy role-based to permission-based authorization
This script helps migrate existing referal data and users to the new auth system
"""

import sys
import os
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

import requests
import json
from datetime import datetime
import pandas as pd
from models import User, db
from app import app

# Configuration
AUTH_SERVICE_URL = os.getenv('AUTH_SERVICE_URL', 'http://localhost:8080')
SERVICE_KEY = 'referal'

class AuthMigration:
    def __init__(self):
        self.auth_url = AUTH_SERVICE_URL
        self.service_key = SERVICE_KEY
        self.session = requests.Session()
        self.session.timeout = 30
    
    def sync_permissions_to_auth_service(self):
        """Step 1: Sync referal permissions to auth-service"""
        print("🔄 Syncing permissions to auth-service...")
        
        try:
            # Call our own sync endpoint to get permissions
            response = requests.get('http://localhost:5000/api/sync/permissions')
            if response.status_code != 200:
                print(f"❌ Failed to get permissions from referal service: {response.status_code}")
                return False
            
            permissions_data = response.json()
            
            # Send to auth-service
            sync_url = f"{self.auth_url}/services/{self.service_key}/permissions/sync"
            auth_response = requests.post(sync_url, json=permissions_data)
            
            if auth_response.status_code == 200:
                result = auth_response.json()
                print(f"✅ Successfully synced {result.get('synced_permissions', 0)} permissions")
                return True
            else:
                print(f"❌ Failed to sync to auth-service: {auth_response.status_code}")
                print(auth_response.text)
                return False
                
        except Exception as e:
            print(f"❌ Error syncing permissions: {e}")
            return False
    
    def create_default_roles(self):
        """Step 2: Create default roles in auth-service"""
        print("🔄 Creating default roles...")
        
        roles_to_create = [
            {
                'name': 'referer',
                'description': 'Обычный пользователь реферальной программы',
                'permissions': [
                    'referal.profile.view',
                    'referal.profile.edit',
                    'referal.referrals.create',
                    'referal.referrals.view',
                    'referal.payments.view',
                    'referal.payments.request'
                ]
            },
            {
                'name': 'manager',
                'description': 'Менеджер реферальной программы',
                'permissions': [
                    'referal.profile.view',
                    'referal.referrals.view',
                    'referal.referrals.approve',
                    'referal.users.manage',
                    'referal.payments.approve',
                    'referal.reports.view',
                    'referal.stats.view'
                ]
            },
            {
                'name': 'call-center',
                'description': 'Сотрудник call-центра',
                'permissions': [
                    'referal.leads.view',
                    'referal.leads.assign',
                    'referal.meetings.schedule',
                    'referal.reports.view'
                ]
            },
            {
                'name': 'admin',
                'description': 'Администратор реферальной программы',
                'permissions': [
                    'referal.profile.view',
                    'referal.referrals.create',
                    'referal.referrals.view',
                    'referal.referrals.approve',
                    'referal.users.manage',
                    'referal.payments.view',
                    'referal.payments.approve',
                    'referal.reports.view',
                    'referal.stats.view',
                    'referal.leads.view',
                    'referal.leads.assign',
                    'referal.admin.export_data',
                    'referal.admin.manage_settings',
                    'referal.admin.view_logs',
                    'referal.admin.manage_users',
                    'referal.documents.view',
                    'referal.documents.request'
                ]
            }
        ]
        
        created_roles = 0
        
        for role_data in roles_to_create:
            try:
                url = f"{self.auth_url}/services/{self.service_key}/roles"
                response = requests.post(url, data={
                    'role_name': role_data['name'],
                    'role_description': role_data['description'],
                    **{f"perm_{perm}": "on" for perm in role_data['permissions']}
                })
                
                if response.status_code in [200, 302]:  # 302 for redirect after success
                    print(f"✅ Created role: {role_data['name']}")
                    created_roles += 1
                else:
                    print(f"⚠️  Role {role_data['name']} might already exist or creation failed: {response.status_code}")
                    
            except Exception as e:
                print(f"❌ Failed to create role {role_data['name']}: {e}")
        
        print(f"✅ Created {created_roles} roles")
        return created_roles > 0
    
    def migrate_users(self):
        """Step 3: Migrate existing users to auth-service"""
        print("🔄 Migrating users...")
        
        with app.app_context():
            users = User.query.all()
            migrated_count = 0
            
            for user in users:
                try:
                    # Map legacy role to new role
                    legacy_role = getattr(user, 'role', 'referer')
                    new_role = self.map_legacy_role(legacy_role)
                    
                    # Prepare user data
                    user_data = {
                        'identifier': user.login,
                        'full_name': getattr(user, 'user_data', {}).get('full_name', user.login) if hasattr(user, 'user_data') else user.login,
                        'service_key': self.service_key,
                        'roles': [new_role]
                    }
                    
                    # Add user to auth-service
                    url = f"{self.auth_url}/services/{self.service_key}/users"
                    response = requests.post(url, json=user_data)
                    
                    if response.status_code in [200, 201]:
                        print(f"✅ Migrated user: {user.login} -> {new_role}")
                        migrated_count += 1
                    else:
                        print(f"⚠️  User {user.login} might already exist: {response.status_code}")
                        
                except Exception as e:
                    print(f"❌ Failed to migrate user {user.login}: {e}")
            
            print(f"✅ Migrated {migrated_count} users")
            return migrated_count
    
    def map_legacy_role(self, legacy_role):
        """Map legacy roles to new roles"""
        mapping = {
            'referer': 'referer',
            'user': 'referer',
            'manager': 'manager',
            'call-center': 'call-center',
            'admin': 'admin'
        }
        return mapping.get(legacy_role, 'referer')
    
    def generate_migration_report(self):
        """Step 4: Generate migration report"""
        print("📊 Generating migration report...")
        
        with app.app_context():
            # Collect statistics
            total_users = User.query.count()
            role_stats = {}
            
            for user in User.query.all():
                role = getattr(user, 'role', 'unknown')
                role_stats[role] = role_stats.get(role, 0) + 1
            
            report = {
                'migration_date': datetime.now().isoformat(),
                'total_users': total_users,
                'role_distribution': role_stats,
                'service_key': self.service_key,
                'auth_service_url': self.auth_url
            }
            
            # Save report
            report_file = f'migration_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            
            print(f"✅ Migration report saved: {report_file}")
            print(f"📈 Total users: {total_users}")
            print(f"📊 Role distribution: {role_stats}")
            
            return report
    
    def verify_migration(self):
        """Step 5: Verify migration was successful"""
        print("🔍 Verifying migration...")
        
        try:
            # Check if service exists in auth-service
            url = f"{self.auth_url}/services/{self.service_key}"
            response = requests.get(url)
            
            if response.status_code == 200:
                print("✅ Service exists in auth-service")
            else:
                print("❌ Service not found in auth-service")
                return False
            
            # Test permissions endpoint
            try:
                # This would require a real user ID, so we'll skip for now
                print("⚠️  Permission verification skipped (requires real user ID)")
            except:
                pass
            
            return True
            
        except Exception as e:
            print(f"❌ Verification failed: {e}")
            return False
    
    def run_full_migration(self):
        """Run complete migration process"""
        print("🚀 Starting full migration process...")
        print(f"Auth Service: {self.auth_url}")
        print(f"Service Key: {self.service_key}")
        print("-" * 50)
        
        success_steps = 0
        
        # Step 1: Sync permissions
        if self.sync_permissions_to_auth_service():
            success_steps += 1
        
        # Step 2: Create roles
        if self.create_default_roles():
            success_steps += 1
        
        # Step 3: Migrate users
        user_count = self.migrate_users()
        if user_count > 0:
            success_steps += 1
        
        # Step 4: Generate report
        self.generate_migration_report()
        success_steps += 1
        
        # Step 5: Verify
        if self.verify_migration():
            success_steps += 1
        
        print("-" * 50)
        print(f"✅ Migration completed: {success_steps}/5 steps successful")
        
        if success_steps == 5:
            print("🎉 Full migration completed successfully!")
            print("Next steps:")
            print("1. Update referal service to use auth-connector")
            print("2. Test permission-based authorization")
            print("3. Monitor logs for any issues")
        else:
            print("⚠️  Migration completed with some issues. Please check the logs.")
        
        return success_steps == 5

def main():
    """Main migration entry point"""
    print("🔧 Referal Service Migration Tool")
    print("=" * 50)
    
    migration = AuthMigration()
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == 'sync':
            migration.sync_permissions_to_auth_service()
        elif command == 'roles':
            migration.create_default_roles()
        elif command == 'users':
            migration.migrate_users()
        elif command == 'report':
            migration.generate_migration_report()
        elif command == 'verify':
            migration.verify_migration()
        else:
            print(f"Unknown command: {command}")
            print("Available commands: sync, roles, users, report, verify")
    else:
        # Run full migration
        migration.run_full_migration()

if __name__ == '__main__':
    main()