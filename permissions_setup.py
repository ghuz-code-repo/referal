"""
Referal service permissions setup
Defines all permissions needed for referal management
"""

from auth_connector import PermissionRegistry

def setup_referal_permissions():
    """Setup all permissions for referal service"""
    registry = PermissionRegistry('referal')
    
    # Profile management permissions
    registry.register('profile.view', 'View Profile', 'View user profile and personal data', 'profile')
    registry.register('profile.edit', 'Edit Profile', 'Edit user profile and personal data', 'profile')
    registry.register('profile.documents', 'View Documents', 'View user documents and attachments', 'profile')
    registry.register('profile.documents.download', 'Download Documents', 'Download user document attachments', 'profile')
    
    # Referal management permissions
    registry.register('referals.view', 'View Referals', 'View own referals and their status', 'referals')
    registry.register('referals.create', 'Create Referals', 'Create new referals', 'referals')
    registry.register('referals.edit', 'Edit Referals', 'Edit own referals data', 'referals')
    registry.register('referals.delete', 'Delete Referals', 'Delete own referals', 'referals')
    
    # Status management permissions (for admins/managers)
    registry.register('referals.status.view', 'View All Statuses', 'View all referal statuses', 'status')
    registry.register('referals.status.update', 'Update Status', 'Update referal status (approve/reject)', 'status')
    registry.register('referals.status.approve', 'Approve Referals', 'Approve pending referals', 'status')
    registry.register('referals.status.reject', 'Reject Referals', 'Reject referals with reason', 'status')
    
    # Payment management permissions
    registry.register('payments.view', 'View Payments', 'View own payment history and balance', 'payments')
    registry.register('payments.request', 'Request Payment', 'Request payment withdrawal', 'payments')
    registry.register('payments.approve', 'Approve Payments', 'Approve payment requests', 'payments')
    registry.register('payments.manage', 'Manage Payments', 'Full payment management access', 'payments')
    
    # User management permissions (for admins)
    registry.register('users.view', 'View Users', 'View all users and their data', 'users')
    registry.register('users.edit', 'Edit Users', 'Edit user data and settings', 'users')
    registry.register('users.delete', 'Delete Users', 'Delete users from system', 'users')
    registry.register('users.roles', 'Manage User Roles', 'Manage user roles and permissions', 'users')
    
    # Reports permissions
    registry.register('reports.view', 'View Reports', 'View referal reports and statistics', 'reports')
    registry.register('reports.export', 'Export Reports', 'Export reports to Excel/CSV', 'reports')
    registry.register('reports.advanced', 'Advanced Reports', 'Access to advanced reporting features', 'reports')
    
    # Admin permissions
    registry.register('admin.panel', 'Admin Panel', 'Access to administration panel', 'admin')
    registry.register('admin.settings', 'System Settings', 'Manage system settings and configuration', 'admin')
    registry.register('admin.logs', 'View Logs', 'View system logs and audit trails', 'admin')
    
    return registry

# Create the registry instance
permissions_registry = setup_referal_permissions()